import os
import subprocess
import json
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtMultimedia import QMediaMetaData
from PyQt6.QtWidgets import QMenu, QWidgetAction, QLabel, QVBoxLayout, QWidget
from translations import tr
from utils import get_resource_path
from styles import MENU_STYLE, get_styles
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QMainWindow, QPushButton
    from PyQt6.QtMultimedia import QMediaPlayer
    PlaylistInfoMixinBase = QMainWindow
else:
    PlaylistInfoMixinBase = object

class PlaylistInfoMixin(PlaylistInfoMixinBase):
    if TYPE_CHECKING:
        currentFilePath: str | None
        currentVideoPath: str | None
        fps: float
        infoButton: QPushButton
        mediaPlayer: QMediaPlayer

    def show_file_info(self):
        if not self.currentFilePath or not os.path.exists(self.currentFilePath):
            return

        try:
            ffprobe_path = get_resource_path("ffprobe.exe" if os.name == 'nt' else "ffprobe")
            if not os.path.exists(ffprobe_path):
                ffprobe_path = "ffprobe"

            cmd = [
                ffprobe_path, "-v", "error",
                "-show_entries", "stream=index,codec_type,codec_name,width,height,avg_frame_rate,pix_fmt,channels,sample_rate,bit_rate,tags",
                "-show_entries", "format=size,duration,format_name",
                "-of", "json", getattr(self, 'currentVideoPath', self.currentFilePath)
            ]

            creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
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
                
                f"<b>{tr('video')}</b><br>"
                f"<b>{tr('resolution')}:</b> {res}<br>"
                f"<b>{tr('codec')}:</b> {codec} ({pix_fmt})<br>"
                f"<b>{tr('container')}:</b> {container}<br>"
                f"<b>{tr('fps')}:</b> {self.fps:.2f}<br>"
                f"<b>{tr('size')}:</b> {size_mb:.2f} MB"
            )

            # Build audio info text + track labels
            audio_track_labels = []
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

                    # Try to get language tag
                    tags = astream.get('tags', {})
                    lang = tags.get('language') or tags.get('LANGUAGE') or tags.get('lang') or ''
                    title = tags.get('title') or tags.get('TITLE') or ''

                    ch_text = tr('channels')
                    if title:
                        label = f"{tr('track')} {i+1}: {title} — {acodec} ({achannels} {ch_text}, {asample})"
                    elif lang and lang.lower() not in ('und', 'unknown'):
                        label = f"{tr('track')} {i+1}: [{lang.upper()}] {acodec} ({achannels} {ch_text}, {asample})"
                    else:
                        label = f"{tr('track')} {i+1}: {acodec} ({achannels} {ch_text}, {asample})"

                    audio_track_labels.append(label)
                    audio_details.append(label)

                audio_text = f"<p style='margin-top:6px; margin-bottom:0px;'><b>{tr('audio')}</b></p>"

            # Determine active Qt audio track index
            
            qt_tracks = self.mediaPlayer.audioTracks() if hasattr(self, 'mediaPlayer') else []
            
            active_qt_idx = self.mediaPlayer.activeAudioTrack() if hasattr(self, 'mediaPlayer') else 0
            multiple_audio = len(audio_streams) > 1

            # Build info string (for the static label in the popup)
            info_text = (
                f"{video_text}"
                f"{audio_text}"
            )

            # If only 1 audio track or no Qt track switching: show as static text
            if not multiple_audio:
                if audio_streams:
                    info_text += audio_track_labels[0]
                info_text += f"<br><br><font color='#888'>{self.currentFilePath}</font>"

            # Build the popup menu
            menu = QMenu(self)
            
            inverse_text = self.config.get('inverse_text', False)
            
            accent = self.config.get('accent_color', '#00f2ff')
            fg_color = "#1c1c1c" if inverse_text else "#ffffff"
            menu.setStyleSheet(MENU_STYLE)

            content = QWidget()
            layout = QVBoxLayout(content)
            layout.setContentsMargins(12, 8, 12, 6)
            layout.setSpacing(0)

            label = QLabel(info_text)
            label.setStyleSheet(f"color: {fg_color}; font-size: 12px; border: none;")
            label.setWordWrap(True)
            label.setFixedWidth(310)
            layout.addWidget(label)

            action = QWidgetAction(menu)
            action.setDefaultWidget(content)
            menu.addAction(action)

            # If multiple audio tracks: add interactive track selection section
            if multiple_audio:
                from PyQt6.QtGui import QAction

                for i, track_label in enumerate(audio_track_labels):
                    is_active = (i == active_qt_idx)
                    display_label = f"✔  {track_label}" if is_active else f"    {track_label}"
                    track_action = QAction(display_label, menu)

                    def make_switch(idx):
                        def switch():
                            
                            self.mediaPlayer.setActiveAudioTrack(idx)
                        return switch

                    track_action.triggered.connect(make_switch(i))
                    menu.addAction(track_action)

                path_action_content = QWidget()
                path_layout = QVBoxLayout(path_action_content)
                path_layout.setContentsMargins(12, 2, 12, 6)
                path_label = QLabel(f"<font color='#888'>{self.currentFilePath}</font>")
                path_label.setStyleSheet("font-size: 11px; border: none;")
                path_label.setWordWrap(True)
                path_label.setFixedWidth(310)
                path_layout.addWidget(path_label)
                path_action = QWidgetAction(menu)
                path_action.setDefaultWidget(path_action_content)
                menu.addAction(path_action)
            else:
                pass  # path already in info_text above

            # Show menu next to the info button
            
            pos = self.infoButton.mapToGlobal(QPoint(0, self.infoButton.height() + 5))
            menu.exec(pos)

        except Exception as e:
            print(f"Error getting file info: {e}")
