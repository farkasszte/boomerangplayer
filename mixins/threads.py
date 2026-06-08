import os
import subprocess
import tempfile
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QPixmap, QPainter, QColor
from utils import get_resource_path

class FrameExtractionThread(QThread):
    finished_extraction = pyqtSignal(dict, str, int, int)
    
    def __init__(self, video_path, start_frame, num_frames, fps, temp_dir=None, parent=None, gpu_enabled=False, player_idx=1, start_number=None, video_codec=None, qv_value=2):
        super().__init__(parent)
        self.video_path = video_path
        self.start_frame = start_frame
        self.num_frames = num_frames
        self.fps = fps if fps > 0 else 30.0
        self.process = None
        self._is_cancelled = False
        self.gpu_enabled = gpu_enabled
        self.player_idx = player_idx
        self.start_number = start_number if start_number is not None else start_frame
        self.temp_dir = temp_dir
        self.video_codec = video_codec
        self.qv_value = qv_value

    def _extract_from_pipe(self, cmd, creationflags):
        if self._is_cancelled:
            return {}

        self.process = subprocess.Popen(
            cmd,
            creationflags=creationflags,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )

        if self._is_cancelled:
            try:
                self.process.kill()
            except OSError:
                pass
            self.process.wait()
            return {}
        
        frame_bytes = {}
        buffer = bytearray()
        frame_idx = self.start_number
        
        while not self._is_cancelled:
            
            chunk = self.process.stdout.read(65536)
            if not chunk:
                break
            buffer.extend(chunk)
            
            while True:
                start_idx = buffer.find(b'\xff\xd8')
                if start_idx == -1:
                    if len(buffer) > 0:
                        buffer = buffer[-1:]
                    break
                
                end_idx = buffer.find(b'\xff\xd9', start_idx)
                if end_idx == -1:
                    if start_idx > 0:
                        buffer = buffer[start_idx:]
                    break
                
                img_data = bytes(buffer[start_idx : end_idx + 2])
                frame_bytes[frame_idx] = img_data
                frame_idx += 1
                
                buffer = buffer[end_idx + 2:]
                
        if self._is_cancelled:
            try:
                self.process.kill()
            except OSError:
                pass

        self.process.wait()
        return frame_bytes

    def run(self):
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            ffmpeg_path = os.path.join(base_dir, "..", "ffmpeg.exe" if os.name == 'nt' else "ffmpeg")
            ffmpeg_path = os.path.normpath(ffmpeg_path)
            if not os.path.exists(ffmpeg_path):
                ffmpeg_path = "ffmpeg"
                
            start_time = self.start_frame / self.fps
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            
            # Calculate combined seek parameters (approximate fast input seek + exact output seek)
            # We seek to 0.5 seconds before the target time, then decode and discard the remaining 0.5 seconds
            # This is much faster for heavy codecs like AV1 than the previous 5.0s margin.
            approx_time = max(0.0, start_time - 0.5)
            exact_delta = start_time - approx_time
            
            def build_cmd(gpu=False, fallback_output_only=False):
                c = [ffmpeg_path, "-y"]
                use_cuvid = False
                if gpu and self.video_codec:
                    cuvid_decoders = {
                        'av1': 'av1_cuvid',
                        'h264': 'h264_cuvid',
                        'hevc': 'hevc_cuvid',
                        'h265': 'hevc_cuvid',
                        'vp9': 'vp9_cuvid',
                        'mpeg4': 'mpeg4_cuvid',
                        'mpeg2video': 'mpeg2_cuvid',
                        'vc1': 'vc1_cuvid'
                    }
                    codec = self.video_codec.lower()
                    if codec in cuvid_decoders:
                        c.extend(["-c:v", cuvid_decoders[codec]])
                        use_cuvid = True
                
                if gpu and not use_cuvid:
                    c.extend(["-hwaccel", "auto"])
                
                # Use all available CPU threads for decoding/encoding
                c.extend(["-threads", "0"])
                
                if fallback_output_only:
                    # Full output seeking (100% accurate, no input seeking)
                    c.extend(["-i", self.video_path])
                    if start_time > 0:
                        c.extend(["-ss", f"{start_time:.6f}"])
                else:
                    # Combined seeking (fast input seek + accurate output seek)
                    if approx_time > 0:
                        c.extend(["-ss", f"{approx_time:.6f}"])
                    c.extend(["-i", self.video_path])
                    if exact_delta > 0:
                        c.extend(["-ss", f"{exact_delta:.6f}"])
                
                c.extend([
                    "-vframes", str(self.num_frames),
                    "-f", "image2pipe",
                    "-vcodec", "mjpeg",
                    "-q:v", str(self.qv_value), 
                    "-"
                ])
                return c

            # Layer 1: GPU enabled (if requested) + Combined seeking
            cmd = build_cmd(gpu=self.gpu_enabled)
            frame_bytes = self._extract_from_pipe(cmd, creationflags)
            
            # Layer 2 Fallback: If GPU failed, retry in software mode + Combined seeking
            if not frame_bytes and self.gpu_enabled and not self._is_cancelled:
                print(f"[FrameExtractionThread] GPU extraction failed. Retrying in software mode + combined seeking.")
                cmd = build_cmd(gpu=False)
                frame_bytes = self._extract_from_pipe(cmd, creationflags)
                
            # Layer 3 Fallback: If combined seeking failed, retry with full software output seeking
            if not frame_bytes and self.start_frame > 0 and not self._is_cancelled:
                print(f"[FrameExtractionThread] Combined seeking failed. Retrying with full software output seeking.")
                cmd = build_cmd(gpu=False, fallback_output_only=True)
                frame_bytes = self._extract_from_pipe(cmd, creationflags)

            self.finished_extraction.emit(frame_bytes, self.temp_dir or "", self.start_frame, self.num_frames)
        except Exception as e:
            print(f"Extraction error: {e}")
            self.finished_extraction.emit({}, self.temp_dir or "", self.start_frame, self.num_frames)

    def cancel(self):
        self._is_cancelled = True
        if self.process:
            try:
                self.process.kill()
            except OSError:
                pass

class ThumbnailThread(QThread):
    finished = pyqtSignal(str, QPixmap)

    def __init__(self, filePath, parent=None):
        super().__init__(parent)
        self.filePath = filePath
        self._is_cancelled = False
        self.process = None

    def run(self):
        try:
            # Native image handling
            image_exts = ('.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff')
            if self.filePath.lower().endswith(image_exts):
                pixmap = QPixmap(self.filePath)
                if not pixmap.isNull():
                    thumb = pixmap.scaled(160, 160, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                    final_thumb = QPixmap(160, 160)
                    final_thumb.fill(Qt.GlobalColor.transparent)
                    painter = QPainter(final_thumb)
                    x = (160 - thumb.width()) // 2
                    y = (160 - thumb.height()) // 2
                    painter.drawPixmap(x, y, thumb)
                    painter.end()
                    
                    if not self._is_cancelled:
                        self.finished.emit(self.filePath, final_thumb)
                    return

            # Video handling via FFmpeg
            import uuid
            temp_dir = tempfile.gettempdir()
            thumb_name = f"thumb_{uuid.uuid4().hex}.jpg"
            thumb_path = os.path.join(temp_dir, thumb_name)
            
            ffmpeg_path = get_resource_path("ffmpeg.exe" if os.name == 'nt' else "ffmpeg")
            if not os.path.exists(ffmpeg_path):
                ffmpeg_path = "ffmpeg"

            cmd = [
                ffmpeg_path, "-y",
                "-ss", "1.0",
                "-i", self.filePath,
                "-vframes", "1",
                "-vf", "setsar=1,scale=160:160:force_original_aspect_ratio=increase,crop=160:160",
                thumb_path
            ]
            
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            self.process = subprocess.Popen(cmd, creationflags=creationflags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                if self.process:
                    try: self.process.kill()
                    except OSError: pass
                try: os.remove(thumb_path)
                except OSError: pass
                if not self._is_cancelled:
                    self.finished.emit(self.filePath, QPixmap())
                return

            if self._is_cancelled:
                try: os.remove(thumb_path)
                except OSError: pass
                return

            thumbnail_emitted = False
            if os.path.exists(thumb_path):
                pixmap = QPixmap(thumb_path)
                if not pixmap.isNull():
                    if not self._is_cancelled:
                        self.finished.emit(self.filePath, pixmap)
                        thumbnail_emitted = True
                try: os.remove(thumb_path)
                except OSError: pass

            if not thumbnail_emitted and not self._is_cancelled:
                self.finished.emit(self.filePath, QPixmap())
        except Exception as e:
            print(f"Thumbnail error for {self.filePath}: {e}")
            if not self._is_cancelled:
                self.finished.emit(self.filePath, QPixmap())

    def cancel(self):
        self._is_cancelled = True
        if self.process:
            try:
                self.process.kill()
            except OSError:
                pass
