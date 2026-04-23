import os
import subprocess
import tempfile
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QPixmap
from utils import get_resource_path

class FrameExtractionThread(QThread):
    finished_extraction = pyqtSignal(dict, str, int, int)
    
    def __init__(self, video_path, start_frame, num_frames, fps, temp_dir=None, parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self.start_frame = start_frame
        self.num_frames = num_frames
        self.fps = fps if fps > 0 else 30.0
        self.temp_dir = temp_dir if temp_dir else tempfile.mkdtemp(prefix="boomerang_frames_")
        self.process = None
        self._is_cancelled = False
        
    def run(self):
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            ffmpeg_path = os.path.join(base_dir, "ffmpeg.exe" if os.name == 'nt' else "ffmpeg")
            if not os.path.exists(ffmpeg_path):
                ffmpeg_path = "ffmpeg"
                
            out_pattern = os.path.join(self.temp_dir, "frame_%08d.jpg")
            start_time = self.start_frame / self.fps
            
            cmd = [
                ffmpeg_path, "-y",
                "-ss", str(start_time),
                "-i", self.video_path,
                "-vframes", str(self.num_frames),
                "-start_number", str(self.start_frame),
                "-q:v", "2", 
                out_pattern
            ]
            
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            self.process = subprocess.Popen(cmd, creationflags=creationflags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.process.wait()
            
            if self._is_cancelled:
                self.finished_extraction.emit({}, self.temp_dir, self.start_frame, self.num_frames)
                return
            
            frame_files = {}
            for i in range(self.start_frame, self.start_frame + self.num_frames):
                fpath = os.path.join(self.temp_dir, f"frame_{i:08d}.jpg")
                if os.path.exists(fpath):
                    frame_files[i] = fpath
                    
            self.finished_extraction.emit(frame_files, self.temp_dir, self.start_frame, self.num_frames)
        except Exception as e:
            print(f"Extraction error: {e}")
            self.finished_extraction.emit({}, self.temp_dir, self.start_frame, self.num_frames)

    def cancel(self):
        self._is_cancelled = True
        if self.process:
            try:
                self.process.kill()
            except:
                pass

class ThumbnailThread(QThread):
    finished = pyqtSignal(str, QPixmap)

    def __init__(self, filePath, parent=None):
        super().__init__(parent)
        self.filePath = filePath

    def run(self):
        try:
            import tempfile
            temp_dir = tempfile.gettempdir()
            thumb_name = f"thumb_{hash(self.filePath)}.jpg"
            thumb_path = os.path.join(temp_dir, thumb_name)
            
            ffmpeg_path = get_resource_path("ffmpeg.exe" if os.name == 'nt' else "ffmpeg")
            if not os.path.exists(ffmpeg_path):
                ffmpeg_path = "ffmpeg"

            cmd = [
                ffmpeg_path, "-y",
                "-ss", "0.5",
                "-i", self.filePath,
                "-vframes", "1",
                "-vf", "setsar=1,scale=120:120:force_original_aspect_ratio=decrease,pad=120:120:(ow-iw)/2:(oh-ih)/2",
                thumb_path
            ]
            
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            process = subprocess.Popen(cmd, creationflags=creationflags)
            process.wait()
            
            if os.path.exists(thumb_path):
                pixmap = QPixmap(thumb_path)
                self.finished.emit(self.filePath, pixmap)
                try: os.remove(thumb_path)
                except: pass
        except Exception as e:
            print(f"Thumbnail error: {e}")
