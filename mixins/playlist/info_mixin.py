import os
import subprocess
import json
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtWidgets import QMenu, QWidgetAction, QLabel, QVBoxLayout, QWidget
from translations import tr
from utils import get_resource_path
from styles import MENU_STYLE
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QMainWindow, QPushButton
    PlaylistInfoMixinBase = QMainWindow
else:
    PlaylistInfoMixinBase = object

class PlaylistInfoMixin(PlaylistInfoMixinBase):
    if TYPE_CHECKING:
        currentFilePath: str | None
        currentVideoPath: str | None
        fps: float
        infoButton: QPushButton
    def show_file_info(self):
        # pyrefly: ignore [bad-argument-type, missing-attribute]
        if not self.currentFilePath or not os.path.exists(self.currentFilePath):
            return

        try:
            ffprobe_path = get_resource_path("ffprobe.exe" if os.name == 'nt' else "ffprobe")
            if not os.path.exists(ffprobe_path):
                ffprobe_path = "ffprobe"

            cmd = [
                ffprobe_path, "-v", "error",
                "-show_entries", "stream=codec_type,codec_name,width,height,avg_frame_rate,pix_fmt,channels,sample_rate,bit_rate",
                "-show_entries", "format=size,duration,format_name",
                "-of", "json", getattr(self, 'currentVideoPath', self.currentFilePath)
            ]

            creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            # pyrefly: ignore [no-matching-overload]
            result = subprocess.check_output(cmd, creationflags=creationflags).decode('utf-8')
            data = json.loads(result)

            video_streams = [s for s in data.get('streams', []) if s.get('codec_type') == 'video']
            audio_streams = [s for s in data.get('streams', []) if s.get('codec_type') == 'audio']

            stream = video_streams[0] if video_streams else data.get('streams', [{}])[0]
            fmt = data.get('format', {})

            size_mb = float(fmt.get('size', 0)) / (1024 * 1024)
            res = f"{stream.get('width', '?')}x{stream.get('height', '?')}"
            codec = stream.get('codec_name', 'unknown')
            pix_fmt = stream.get('pix_fmt', 'unknown')
            container = fmt.get('format_name', 'unknown').split(',')[0]

            video_text = (
                # pyrefly: ignore [missing-attribute]
                f"<b>{tr('video')}</b><br>"
                f"<b>{tr('resolution')}:</b> {res}<br>"
                f"<b>{tr('codec')}:</b> {codec} ({pix_fmt})<br>"
                f"<b>{tr('container')}:</b> {container}<br>"
                f"<b>{tr('fps')}:</b> {float(self.fps):.2f}<br>"
                f"<b>{tr('size')}:</b> {size_mb:.2f} MB"
            )

            audio_text = ""
            if audio_streams:
                audio_details = []
                for i, astream in enumerate(audio_streams):
                    acodec = astream.get('codec_name', 'unknown')
                    achannels = astream.get('channels', '?')
                    asample = astream.get('sample_rate', '?')
                    
                    if asample != '?':
                        try:
                            asample = f"{float(asample)/1000:.1f} kHz"
                        except:
                            pass
                    
                    ch_text = tr('channels')
                    audio_details.append(f"Track {i+1}: {acodec} ({achannels} {ch_text}, {asample})")
                
                audio_text = f"<br><br><b>{tr('audio')}</b><br>" + "<br>".join(audio_details)

            info_text = (
                f"{video_text}"
                f"{audio_text}<br><br>"
                f"<font color='#888'>{self.currentFilePath}</font>"
            )

            # Create a compact menu instead of a MessageBox
            # pyrefly: ignore [no-matching-overload]
            menu = QMenu(self)
            menu.setStyleSheet(MENU_STYLE)
            
            content = QWidget()
            layout = QVBoxLayout(content)
            layout.setContentsMargins(15, 10, 15, 10)
            
            label = QLabel(info_text)
            label.setStyleSheet("color: white; font-size: 12px; border: none;")
            label.setWordWrap(True)
            label.setFixedWidth(300)
            layout.addWidget(label)
            
            action = QWidgetAction(menu)
            action.setDefaultWidget(content)
            menu.addAction(action)
            
            # Show menu next to the info button
            # pyrefly: ignore [missing-attribute]
            pos = self.infoButton.mapToGlobal(QPoint(0, self.infoButton.height() + 5))
            menu.exec(pos)

        except Exception as e:
            print(f"Error getting file info: {e}")
