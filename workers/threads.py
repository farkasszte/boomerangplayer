import os
import subprocess
import json
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QPainter, QImage
from utils import get_resource_path, get_ffmpeg_path, get_ffprobe_path

class FrameExtractionThread(QThread):
    finished_extraction = pyqtSignal(dict, str, int, int)
    
    def __init__(self, video_path, start_frame, num_frames, fps, temp_dir=None, parent=None, gpu_enabled=False, player_idx=1, start_number=None, video_codec=None, qv_value=2, is_hdr=False, color_transfer=""):
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
        self.is_hdr = is_hdr
        self.color_transfer = color_transfer

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
                    if len(buffer) > 1:
                        del buffer[:-1]
                    break
                
                end_idx = buffer.find(b'\xff\xd9', start_idx)
                if end_idx == -1:
                    if start_idx > 0:
                        del buffer[:start_idx]
                    break
                
                img_data = bytes(buffer[start_idx : end_idx + 2])
                frame_bytes[frame_idx] = img_data
                frame_idx += 1
                
                del buffer[:end_idx + 2]
                
        if self._is_cancelled:
            try:
                self.process.kill()
            except OSError:
                pass

        self.process.wait()
        return frame_bytes

    def run(self):
        try:
            ffmpeg_path = get_ffmpeg_path()
                
            start_time = self.start_frame / self.fps
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            
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
                    hwaccel = 'auto'
                    if self.parent() and hasattr(self.parent(), 'config'):
                        hwaccel = self.parent().config.get('detected_hwaccel', 'auto')
                    c.extend(["-hwaccel", hwaccel])
                
                c.extend(["-threads", "0"])
                
                if fallback_output_only:
                    c.extend(["-i", self.video_path])
                    if start_time > 0:
                        c.extend(["-ss", f"{start_time:.6f}"])
                else:
                    if approx_time > 0:
                        c.extend(["-ss", f"{approx_time:.6f}"])
                    c.extend(["-i", self.video_path])
                    if exact_delta > 0:
                        c.extend(["-ss", f"{exact_delta:.6f}"])
                
                if self.is_hdr:
                    transfer_in = "arib-std-b67" if self.color_transfer == "arib-std-b67" else "smpte2084"
                    c.extend(["-vf", f"zscale=matrixin=bt2020nc:transferin={transfer_in}:primariesin=bt2020:matrix=bt709:transfer=linear:primaries=bt709,tonemap=tonemap=mobius:desat=0,zscale=transfer=bt709,format=yuv420p"])

                c.extend([
                    "-vframes", str(self.num_frames),
                    "-f", "image2pipe",
                    "-vcodec", "mjpeg",
                    "-q:v", str(self.qv_value), 
                    "-"
                ])
                return c

            cmd = build_cmd(gpu=self.gpu_enabled)
            frame_bytes = self._extract_from_pipe(cmd, creationflags)
            
            if not frame_bytes and self.gpu_enabled and not self._is_cancelled:
                print(f"[FrameExtractionThread] GPU extraction failed. Retrying in software mode + combined seeking.")
                cmd = build_cmd(gpu=False)
                frame_bytes = self._extract_from_pipe(cmd, creationflags)
                
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
    thumbnail_ready = pyqtSignal(str, QImage)
    finished = thumbnail_ready

    def __init__(self, filePath, parent=None):
        super().__init__(parent)
        self.filePath = filePath
        self._is_cancelled = False
        self.process = None

    def run(self):
        try:
            image_exts = ('.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff')
            if self.filePath.lower().endswith(image_exts):
                image = QImage(self.filePath)
                if not image.isNull():
                    thumb = image.scaled(160, 160, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                    final_thumb = QImage(160, 160, QImage.Format.Format_ARGB32_Premultiplied)
                    final_thumb.fill(Qt.GlobalColor.transparent)
                    painter = QPainter(final_thumb)
                    x = (160 - thumb.width()) // 2
                    y = (160 - thumb.height()) // 2
                    painter.drawImage(x, y, thumb)
                    painter.end()
                    
                    if not self._is_cancelled:
                        self.thumbnail_ready.emit(self.filePath, final_thumb)
                    return

            ffmpeg_path = get_ffmpeg_path()

            is_hdr = False
            color_transfer = ""
            seek_time = "1.0"
            try:
                ffprobe_path = get_ffprobe_path()
                probe_cmd = [
                    ffprobe_path, "-v", "error",
                    "-show_entries", "stream=codec_type,color_transfer,color_primaries:format=duration",
                    "-of", "json", self.filePath
                ]
                creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                probe_proc = subprocess.run(probe_cmd, creationflags=creationflags, capture_output=True, text=True, timeout=4)
                if probe_proc.returncode == 0 and probe_proc.stdout:
                    probe_data = json.loads(probe_proc.stdout)
                    duration_str = probe_data.get('format', {}).get('duration')
                    if duration_str:
                        try:
                            dur = float(duration_str)
                            if dur < 1.0:
                                seek_time = "0.0"
                        except ValueError:
                            pass
                    for s in probe_data.get('streams', []):
                        if s.get('codec_type') == 'video':
                            transfer = s.get('color_transfer', '')
                            primaries = s.get('color_primaries', '')
                            if transfer in ('smpte2084', 'arib-std-b67') or primaries == 'bt2020':
                                is_hdr = True
                                color_transfer = transfer
                            break
            except Exception as e:
                print(f"ffprobe color check failed in ThumbnailThread: {e}")

            if self._is_cancelled:
                return

            vf_filter = "setsar=1,scale=160:160:force_original_aspect_ratio=increase,crop=160:160"
            if is_hdr:
                transfer_in = "arib-std-b67" if color_transfer == "arib-std-b67" else "smpte2084"
                vf_filter = f"zscale=matrixin=bt2020nc:transferin={transfer_in}:primariesin=bt2020:matrix=bt709:transfer=linear:primaries=bt709,tonemap=tonemap=mobius:desat=0,zscale=transfer=bt709,format=yuv420p,{vf_filter}"

            cmd = [
                ffmpeg_path, "-y",
                "-ss", seek_time,
                "-i", self.filePath,
                "-vframes", "1",
                "-vf", vf_filter,
                "-f", "image2pipe",
                "-vcodec", "mjpeg",
                "-"
            ]
            
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            self.process = subprocess.Popen(
                cmd,
                creationflags=creationflags,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )
            
            try:
                stdout_data, _ = self.process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                if self.process:
                    try: self.process.kill()
                    except OSError: pass
                if not self._is_cancelled:
                    self.thumbnail_ready.emit(self.filePath, QImage())
                return

            if self._is_cancelled:
                return

            thumbnail_emitted = False
            if stdout_data:
                img = QImage.fromData(stdout_data)
                if not img.isNull():
                    if not self._is_cancelled:
                        self.thumbnail_ready.emit(self.filePath, img)
                        thumbnail_emitted = True

            if not thumbnail_emitted and not self._is_cancelled:
                self.thumbnail_ready.emit(self.filePath, QImage())
        except Exception as e:
            print(f"Thumbnail error for {self.filePath}: {e}")
            if not self._is_cancelled:
                self.thumbnail_ready.emit(self.filePath, QImage())

    def cancel(self):
        self._is_cancelled = True
        if self.process:
            try:
                self.process.kill()
            except OSError:
                pass


class AudioExtractionThread(QThread):
    finished_extraction = pyqtSignal(str, float, float)

    def __init__(self, video_path, ffmpeg_path, output_path, track_index=0, start_time=0.0, duration=300.0):
        super().__init__()
        self.video_path = video_path
        self.ffmpeg_path = ffmpeg_path
        self.output_path = output_path
        self.track_index = track_index
        self.start_time = start_time
        self.duration = duration
        self._is_cancelled = False
        self.process = None

    def run(self):
        try:
            if os.path.exists(self.output_path):
                try:
                    os.remove(self.output_path)
                except OSError:
                    pass

            cmd = [
                self.ffmpeg_path, "-y",
                "-ss", f"{self.start_time:.3f}",
                "-i", self.video_path,
                "-t", f"{self.duration:.3f}",
                "-map", f"0:a:{self.track_index}",
                "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
                self.output_path
            ]
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            self.process = subprocess.Popen(
                cmd,
                creationflags=creationflags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            self.process.wait()

            if self._is_cancelled:
                if os.path.exists(self.output_path):
                    try:
                        os.remove(self.output_path)
                    except OSError:
                        pass
                return

            if self.process.returncode == 0:
                self.finished_extraction.emit(self.output_path, self.start_time, self.duration)
            else:
                self.finished_extraction.emit("", self.start_time, self.duration)
        except Exception as e:
            print(f"[AudioExtractionThread] Error extracting audio track {self.track_index} at {self.start_time}s: {e}")
            if not self._is_cancelled:
                self.finished_extraction.emit("", self.start_time, self.duration)

    def cancel(self):
        self._is_cancelled = True
        if self.process:
            try:
                self.process.kill()
            except OSError:
                pass



class ProcessMonitorThread(QThread):
    finished_export = pyqtSignal(str, bool, str)

    def __init__(self, process, filename, parent=None):
        super().__init__(parent)
        self.process = process
        self.filename = filename
        self._is_cancelled = False

    def run(self):
        try:
            self.process.wait()
            if self._is_cancelled:
                return
            if self.process.returncode == 0:
                self.finished_export.emit(self.filename, True, "")
            else:
                self.finished_export.emit(self.filename, False, f"FFmpeg exited with code {self.process.returncode}")
        except Exception as e:
            if not self._is_cancelled:
                self.finished_export.emit(self.filename, False, str(e))

    def cancel(self):
        self._is_cancelled = True
        if self.process:
            try:
                self.process.kill()
            except OSError:
                pass
