"""
PlaybackMixin — play/pause, frame advance, seeking, file loading, media events with Multi-Instance UDP Sync hooks.
"""

import os
import subprocess
import json
from PyQt6.QtCore import Qt, QUrl, QTimer, QElapsedTimer, QPointF
from PyQt6.QtMultimedia import QMediaPlayer
from qfluentwidgets import FluentIcon
from utils import get_resource_path, format_time, VERSION, get_embedded_video_offset
from translations import tr


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QMainWindow, QPushButton, QSlider
    from PyQt6.QtMultimedia import QMediaPlayer
    from config import Configuration
    PlaybackMixinBase = QMainWindow
else:
    PlaybackMixinBase = object


class PlaybackMixin(PlaybackMixinBase):
    if TYPE_CHECKING:
        is_playing: bool
        was_playing_before_cache_miss: bool
        frame_accumulator: float
        last_advance_ms: int
        mediaPlayer: QMediaPlayer
        currentFilePath: str | None
        currentVideoPath: str | None
        video_codec: str | None
        last_transform_state: tuple | None
        is_motion_photo: bool
        motion_photo_original_path: str | None
        cached_frame_dict: dict
        current_cache_index: int
        fps: float
        total_frames: int
        playButton: QPushButton
        config: Configuration
        speedSlider: QSlider
        
        cleanup_cache: callable
        save_current_markers: callable
        update_pixmap_from_cache: callable
        apply_transformations: callable
        sync_progress_bar: callable
        start_full_extraction: callable
        load_markers_for_current: callable
    # ------------------------------------------------------------------ #
    # File / video loading                                                 #
    # ------------------------------------------------------------------ #

    def open_media(self):
        """
        Unified smart file/folder picker.
        • Selecting one or more files  → adds those files directly.
        • Clicking a folder and pressing Open (non-native dialog) → adds ALL
          matching files from that folder automatically.
        Supports playlist files (.json / .bpl) as well.
        """
        from PyQt6.QtWidgets import QFileDialog

        video_exts = ('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.m4v')
        image_exts = ('.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff')
        audio_exts = ('.mp3', '.wav', '.aac', '.flac', '.m4a', '.ogg', '.wma')
        playlist_exts = ('.json', '.bpl')
        
        all_exts = video_exts + image_exts + audio_exts + playlist_exts

        name_filters = [
            f"{tr('all_media')} (*.mp4 *.mkv *.avi *.mov *.wmv *.m4v *.jpg *.jpeg *.png *.bmp *.webp *.tiff *.mp3 *.wav *.aac *.flac *.m4a *.ogg *.wma *.json *.bpl)",
            f"{tr('video_files')} (*.mp4 *.mkv *.avi *.mov *.wmv *.m4v)",
            f"{tr('image_files')} (*.jpg *.jpeg *.png *.bmp *.webp *.tiff)",
            f"{tr('audio_files')} (*.mp3 *.wav *.aac *.flac *.m4a *.ogg *.wma)",
            f"{tr('playlist')} (*.bpl *.json)",
        ]
        title = tr('add_files_title')

        dialog = QFileDialog(self, title)
        dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        # Non-native mode: allows single-clicking a folder to place it in the
        # filename field so the user can press Open to add the whole folder.
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dialog.setNameFilters(name_filters)

        # --- Dynamic palette based on theme mode (light/dark) ---
        inverse_text = self.config.get('inverse_text', False)
        accent_color = self.config.get('accent_color', '#00f2ff')
        bg_color = self.config.get('bg_color', '#202020')

        from PyQt6.QtGui import QPalette, QColor
        pal = QPalette()
        if inverse_text:
            pal.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.Window,          QColor(bg_color))
            pal.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.WindowText,      QColor('#1c1c1c'))
            pal.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.Base,            QColor('#ffffff'))
            pal.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.AlternateBase,   QColor('#f9f9f9'))
            pal.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.Text,            QColor('#1c1c1c'))
            pal.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.Button,          QColor('#eaeaea'))
            pal.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.ButtonText,      QColor('#1c1c1c'))
            pal.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.BrightText,      QColor('#1c1c1c'))
            pal.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.ToolTipBase,     QColor('#ffffff'))
            pal.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.ToolTipText,     QColor('#1c1c1c'))
        else:
            pal.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.Window,          QColor(bg_color))
            pal.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.WindowText,      QColor('#ffffff'))
            pal.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.Base,            QColor('#1a1a1a'))
            pal.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.AlternateBase,   QColor('#252525'))
            pal.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.Text,            QColor('#ffffff'))
            pal.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.Button,          QColor('#3a3a3a'))
            pal.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.ButtonText,      QColor('#ffffff'))
            pal.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.BrightText,      QColor('#ffffff'))
            pal.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.ToolTipBase,     QColor('#3a3a3a'))
            pal.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.ToolTipText,     QColor('#ffffff'))
        
        accent = QColor(accent_color)
        pal.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.Highlight,       accent)
        pal.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.HighlightedText, QColor('#000000'))
        dialog.setPalette(pal)

        # Style the dialog with custom CSS stylesheet
        fg_color = "#1c1c1c" if inverse_text else "#ffffff"
        widget_bg = "#ffffff" if inverse_text else "#1a1a1a"
        widget_border = "rgba(0, 0, 0, 0.15)" if inverse_text else "rgba(255, 255, 255, 0.1)"
        widget_border_bottom = "rgba(0, 0, 0, 0.25)" if inverse_text else "rgba(255, 255, 255, 0.2)"
        
        bg_translucent = "rgba(0, 0, 0, 0.04)" if inverse_text else "rgba(255, 255, 255, 0.05)"
        bg_hover = "rgba(0, 0, 0, 0.08)" if inverse_text else "rgba(255, 255, 255, 0.1)"
        bg_pressed = "rgba(0, 0, 0, 0.02)" if inverse_text else "rgba(255, 255, 255, 0.03)"
        
        header_bg = "#eaeaea" if inverse_text else "#252525"
        
        dialog_style = f"""
            QFileDialog {{
                background-color: {bg_color};
            }}
            QLabel {{
                color: {fg_color};
                font-size: 13px;
            }}
            QLineEdit {{
                background-color: {widget_bg};
                border: 1px solid {widget_border};
                border-bottom: 1px solid {widget_border_bottom};
                border-radius: 4px;
                padding: 5px;
                color: {fg_color};
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 1px solid {accent_color};
            }}
            QComboBox {{
                background-color: {widget_bg};
                border: 1px solid {widget_border};
                border-radius: 4px;
                padding: 4px 8px;
                color: {fg_color};
                font-size: 13px;
            }}
            QComboBox:hover {{
                background-color: {bg_hover};
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 15px;
                border-left-width: 0px;
                border-style: solid;
            }}
            QPushButton {{
                background-color: {bg_translucent};
                border: 1px solid {widget_border};
                border-radius: 4px;
                color: {fg_color};
                font-size: 13px;
                font-weight: 500;
                padding: 6px 12px;
                min-width: 75px;
            }}
            QPushButton:hover {{
                background-color: {bg_hover};
            }}
            QPushButton:pressed {{
                background-color: {bg_pressed};
            }}
            QTreeView, QListView {{
                background-color: {widget_bg};
                color: {fg_color};
                border: 1px solid {widget_border};
                border-radius: 4px;
                font-size: 13px;
                outline: none;
            }}
            QTreeView::item, QListView::item {{
                outline: none;
                border: none;
            }}
            QTreeView::item:hover, QListView::item:hover {{
                background-color: {bg_hover};
                border: none;
                outline: none;
            }}
            QTreeView::item:selected, QListView::item:selected {{
                background-color: {accent_color};
                color: #000000;
                border: none;
                outline: none;
            }}
            QHeaderView::section {{
                background-color: {header_bg};
                color: {fg_color};
                padding: 4px;
                border: none;
                font-size: 12px;
            }}
            QToolButton {{
                background-color: transparent;
                border: none;
                border-radius: 4px;
                padding: 5px;
                color: {fg_color};
            }}
            QToolButton:hover {{
                background-color: {bg_hover};
            }}
        """
        dialog.setStyleSheet(dialog_style)

        # Apply Windows 11 title bar styling using DWM API
        import sys
        if sys.platform == 'win32':
            try:
                import ctypes
                hwnd = int(dialog.winId())
                
                def qcolor_to_colorref(qcolor):
                    return qcolor.red() | (qcolor.green() << 8) | (qcolor.blue() << 16)
                
                from PyQt6.QtGui import QColor
                bg_color_ref = qcolor_to_colorref(QColor(bg_color))
                fg_color_ref = qcolor_to_colorref(QColor(fg_color))
                
                # DWMWA_CAPTION_COLOR = 35 (Windows 11 Build 22000+)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    35,
                    ctypes.byref(ctypes.c_int(bg_color_ref)),
                    4
                )
                # DWMWA_TEXT_COLOR = 36 (Windows 11 Build 22000+)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    36,
                    ctypes.byref(ctypes.c_int(fg_color_ref)),
                    4
                )
            except Exception as e:
                print(f"[DWM] Failed to set custom title bar colors: {e}")

        # --- Sidebar: list all available drives directly (no "My Computer" step) ---
        from PyQt6.QtCore import QDir, QUrl
        drive_urls = [QUrl.fromLocalFile(d.absolutePath()) for d in QDir.drives()]
        dialog.setSidebarUrls(drive_urls)

        # Add custom "Add folder" button next to Open/Cancel
        from PyQt6.QtWidgets import QDialogButtonBox, QPushButton, QWidget, QHBoxLayout, QLabel, QToolButton
        
        # Translate default dialog labels ("File name:", "Files of type:")
        for label in dialog.findChildren(QLabel):
            text_clean = label.text().replace('&', '')
            if "File name" in text_clean:
                label.setText(tr('file_name'))
            elif "Files of type" in text_clean:
                label.setText(tr('file_types'))

        # Tint only the first 3 navigation arrow icons (Back, Forward, Up) to be highly visible,
        # leaving the multi-color icons (New Folder, Grid/List view) with their original textures.
        from PyQt6.QtGui import QPixmap, QIcon, QPainter
        from PyQt6.QtCore import Qt, QSize
        tool_btns = dialog.findChildren(QToolButton)
        tool_btns = sorted(tool_btns, key=lambda b: b.x())
        for idx, btn in enumerate(tool_btns):
            if idx >= 3:
                continue
            icon = btn.icon()
            if not icon.isNull():
                sz = btn.iconSize()
                if sz.width() <= 0 or sz.height() <= 0:
                    sz = QSize(16, 16)
                pixmap = icon.pixmap(sz)
                if not pixmap.isNull():
                    tinted = QPixmap(pixmap.size())
                    tinted.fill(Qt.GlobalColor.transparent)
                    painter = QPainter(tinted)
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
                    painter.drawPixmap(0, 0, pixmap)
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                    painter.fillRect(tinted.rect(), QColor(fg_color))
                    painter.end()
                    btn.setIcon(QIcon(tinted))

        button_box = dialog.findChild(QDialogButtonBox)
        if button_box:
            add_folder_btn = QPushButton(tr('add_folder'))
            
            # Find the OK/Open button (AcceptRole) and translate buttons
            open_btn = None
            for btn in button_box.buttons():
                role = button_box.buttonRole(btn)
                if role == QDialogButtonBox.ButtonRole.AcceptRole:
                    open_btn = btn
                    btn.setText(tr('open'))
                elif role == QDialogButtonBox.ButtonRole.RejectRole:
                    btn.setText(tr('cancel'))
            
            def on_add_folder_clicked():
                current_dir = dialog.directory().absolutePath()
                dialog.setProperty("selected_folder", current_dir)
                dialog.done(1) # Bypass QFileDialog validation cleanly
            add_folder_btn.clicked.connect(on_add_folder_clicked)
            
            layout = button_box.layout()
            if layout and open_btn:
                idx = layout.indexOf(open_btn)
                if idx != -1:
                    # Create a horizontal container for Open and Add folder
                    container = QWidget()
                    h_layout = QHBoxLayout(container)
                    h_layout.setContentsMargins(0, 0, 0, 0)
                    h_layout.setSpacing(6)
                    
                    # Reparent and layout buttons side-by-side
                    layout.removeWidget(open_btn)
                    h_layout.addWidget(open_btn)
                    h_layout.addWidget(add_folder_btn)
                    
                    # Insert the container at the original Open button index
                    layout.insertWidget(idx, container)
                else:
                    button_box.addButton(add_folder_btn, QDialogButtonBox.ButtonRole.ActionRole)
            else:
                button_box.addButton(add_folder_btn, QDialogButtonBox.ButtonRole.ActionRole)

        if not dialog.exec():
            return

        folder_path = dialog.property("selected_folder")
        if folder_path:
            selected = [folder_path]
        else:
            selected = dialog.selectedFiles()

        if not selected:
            return

        files_to_add = []
        playlist_files = []

        selected_filter = dialog.selectedNameFilter()
        if tr('video_files') in selected_filter:
            folder_exts = video_exts
        elif tr('image_files') in selected_filter:
            folder_exts = image_exts
        elif tr('audio_files') in selected_filter:
            folder_exts = audio_exts
        elif tr('playlist') in selected_filter:
            folder_exts = playlist_exts
        else:
            folder_exts = all_exts

        for path in selected:
            if os.path.isdir(path):
                # Folder selected → expand to all matching files, sorted by active filter
                for f in sorted(os.listdir(path)):
                    if f.lower().endswith(folder_exts):
                        fpath = os.path.join(path, f)
                        if f.lower().endswith(playlist_exts):
                            playlist_files.append(fpath)
                        else:
                            files_to_add.append(fpath)
            elif os.path.isfile(path):
                if path.lower().endswith(playlist_exts):
                    playlist_files.append(path)
                else:
                    files_to_add.append(path)

        if playlist_files:
            self.load_playlist_by_path(playlist_files[0])
            if files_to_add:
                self.add_files_to_playlist(files_to_add)
        elif files_to_add:
            self.add_files_to_playlist(files_to_add)
            if self.mediaPlayer.playbackState() == QMediaPlayer.PlaybackState.StoppedState:
                self.load_video(files_to_add[0])

    def load_video(self, filePath):
        was_playing = getattr(self, 'is_playing', False)
        self.stop_playback()
        self.was_playing_before_cache_miss = was_playing
        self.frame_accumulator = 0.0
        self.last_advance_ms = 0

        self.mediaPlayer.setSource(QUrl())
        self.cleanup_cache()
        self.save_current_markers()
        is_image = False   # pre-initialise; re-assigned below once filePath is validated
        try:
            self.is_loading_video = True
            self.currentFilePath = filePath
            self.currentVideoPath = filePath
            self.video_codec = None
            self.last_transform_state = None
            self.is_motion_photo = False
            self.motion_photo_original_path = None
            self.is_audio_only = False
            if hasattr(self, 'initial_fit_done'):
                delattr(self, 'initial_fit_done')

            is_image = filePath.lower().endswith(
                ('.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff')
            )

            # Check if it has an embedded MP4 video
            embedded_offset = None
            if is_image and filePath.lower().endswith(('.jpg', '.jpeg')):
                embedded_offset = get_embedded_video_offset(filePath)

            if embedded_offset is not None:
                self.is_motion_photo = True
                self.motion_photo_original_path = filePath
                # Create a temporary directory if it doesn't exist
                if not self.current_temp_dir:
                    import tempfile
                    self.current_temp_dir = tempfile.mkdtemp(prefix="boomerang_frames_")
                
                # Extract the video portion
                temp_video_path = os.path.join(self.current_temp_dir, "extracted_video.mp4")
                try:
                    with open(filePath, 'rb') as f:
                        f.seek(embedded_offset)
                        video_data = f.read()
                    with open(temp_video_path, 'wb') as f:
                        f.write(video_data)
                    self.currentVideoPath = temp_video_path
                    is_image = False  # Treat as video now!
                    print(f"Extracted motion photo video to {temp_video_path} (offset: {embedded_offset})")
                except Exception as ex:
                    print(f"Error extracting motion photo video: {ex}")

            if is_image:
                self.cached_frame_dict = {0: filePath}
                self.cached_file_path = filePath
                self.current_cache_index = 0
                self.fps = 1.0
                self.total_frames = 0
                self.sync_progress_bar()
                self.update_pixmap_from_cache()
                self.apply_transformations(fit=True)
                if hasattr(self, '_apply_file_saved_zoom'):
                    self._apply_file_saved_zoom()
                self.mediaPlayer.stop()
                self.setWindowTitle(f"Boomerang Player v{VERSION} - {os.path.basename(filePath)}")
            else:
                fps, duration_ms, total_frames = self.get_video_info(self.currentVideoPath)
                if self.is_motion_photo:
                    total_frames += 1

                if fps > 0:
                    self.fps = fps
                    print(f"ffprobe detected FPS: {self.fps}")

                if self.is_motion_photo:
                    self.cached_frame_dict = {0: filePath}
                else:
                    self.cached_frame_dict = {}

                self.current_cache_index = 0

                self.mediaPlayer.setSource(QUrl.fromLocalFile(self.currentVideoPath))
                if self.is_motion_photo:
                    self.setWindowTitle(f"Boomerang Player v{VERSION} - [Motion Photo] {os.path.basename(filePath)}")
                elif self.is_audio_only:
                    self.setWindowTitle(f"Boomerang Player v{VERSION} - [Audio] {os.path.basename(filePath)}")
                else:
                    self.setWindowTitle(f"Boomerang Player v{VERSION} - {os.path.basename(filePath)}")

                # Store ffprobe results for frame-accurate timing
                self.ffprobe_fps = fps
                self.ffprobe_duration = duration_ms
                self.ffprobe_nb_frames = total_frames
                self.fps = fps
                self.total_frames = total_frames

                self.update_duration(duration_ms)

                self.mediaPlayer.pause()
                self.playButton.setIcon(FluentIcon.PLAY)
                self.playButton.setEnabled(True)

                if self.is_audio_only:
                    self.generate_audio_placeholder()
                    self.update_pixmap_from_cache()
                    # Apply fitting so placeholder draws nicely
                    self.apply_transformations(fit=True)
                else:
                    self.update_pixmap_from_cache()
                    self.start_full_extraction()

            if hasattr(self, 'subtitles'):
                self.subtitles = []
                self.subtitleFilePath = None
                if hasattr(self, 'subtitleLabel'):
                    self.subtitleLabel.hide()
            if not is_image:
                if hasattr(self, 'auto_load_subtitles_for_video'):
                    self.auto_load_subtitles_for_video(filePath)

            self.load_markers_for_current()

        except Exception as e:
            print(f"Error opening file: {e}")
            from qfluentwidgets import InfoBar, InfoBarPosition
            InfoBar.error(
                title=tr('file_info_title'),
                content=f"Error opening file: {e}",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
        finally:
            if not self.currentFilePath or is_image:
                pass  # Image path: flag cleared by _apply_file_saved_zoom timer
            if not hasattr(self, '_apply_file_saved_zoom'):
                self.is_loading_video = False

    def get_video_info(self, file_path):
        """Get FPS and duration using ffprobe, supporting both video and audio-only files."""
        try:
            ffprobe_path = get_resource_path("ffprobe.exe" if os.name == 'nt' else "ffprobe")
            if not os.path.exists(ffprobe_path):
                ffprobe_path = "ffprobe"

            cmd = [
                ffprobe_path, "-v", "error",
                "-show_entries", "stream=codec_type,codec_name,avg_frame_rate,duration,nb_frames:format=duration",
                "-of", "json", file_path
            ]

            creationflags = 0
            if os.name == 'nt':
                creationflags = subprocess.CREATE_NO_WINDOW

            result = subprocess.check_output(cmd, creationflags=creationflags).decode('utf-8')
            data = json.loads(result)
            streams = data.get('streams', [])
            
            video_stream = next((s for s in streams if s.get('codec_type') == 'video'), None)
            audio_stream = next((s for s in streams if s.get('codec_type') == 'audio'), None)
            
            self.is_audio_only = (video_stream is None and audio_stream is not None)
            
            stream = video_stream if video_stream is not None else audio_stream
            if not stream:
                return 30.0, 0, 0

            fmt = data.get('format', {})
            
            # 1. Get FPS
            if self.is_audio_only:
                fps = 30.0
            else:
                fps_str = stream.get('r_frame_rate', stream.get('avg_frame_rate', '30/1'))
                if '/' in fps_str:
                    num, den = map(int, fps_str.split('/'))
                    fps = num / den if den != 0 else 30.0
                else:
                    fps = float(fps_str)
                
            # 2. Get Duration
            s_dur = stream.get('duration')
            f_dur = fmt.get('duration')
            duration = float(s_dur if s_dur is not None else (f_dur if f_dur is not None else 0))
            
            # 3. Get Number of Frames
            nb_frames = int(stream.get('nb_frames', 0))
            if nb_frames == 0 and duration > 0:
                nb_frames = int(duration * fps)
            
            codec = stream.get('codec_name', 'unknown')
            self.video_codec = codec
            
            print(f"[get_video_info] {os.path.basename(file_path)}: codec={codec}, is_audio_only={self.is_audio_only}, fps={fps}, duration={duration}s, nb_frames={nb_frames}")
            return fps, duration * 1000, nb_frames
        except Exception as e:
            print(f"ffprobe error: {e}")
            return 30.0, 0, 0

    # ------------------------------------------------------------------ #
    # Play / pause / stop                                                  #
    # ------------------------------------------------------------------ #

    def play_pause(self):
        self._toggle_playback(True)

    def play_pause_backward(self):
        self._toggle_playback(False)

    def _toggle_playback(self, target_forward):
        if self.is_playing:
            if self.isForward == target_forward:
                self.stop_playback()
            else:
                self.stop_playback()
                self.isForward = target_forward
                self._start_playback()
        else:
            self.isForward = target_forward
            self._start_playback()

    def _start_playback(self):
        if not getattr(self, 'cached_frame_dict', None):
            return
        self.is_playing = True
        self.update_play_icons()

        self.frame_accumulator = 0.0
        
        self.elapsedTimer.start()
        self.last_advance_ms = 0

        
        self.playbackTimer.start(10)

        if self.isForward and self.fps > 0:
            audio_pos = int((self.current_cache_index * 1000) / self.fps)
            self.mediaPlayer.setPosition(audio_pos)
            
            self.audioOutput.setMuted(self.userMutedIntent)
            # Ensure the playback rate is set before calling play
            rate = self.speedSlider.value() / 100.0
            self.mediaPlayer.setPlaybackRate(rate)
            self.mediaPlayer.play()
        else:
            self.mediaPlayer.pause()
            
            self.audioOutput.setMuted(True)

        if not getattr(self, '_block_broadcast', False):
            
            self.broadcast_sync_event("play", {"isForward": self.isForward, "speed": self.speedSlider.value()})

    def stop_playback(self):
        self.is_playing = False
        
        self.playbackTimer.stop()
        self.mediaPlayer.pause()
        self.update_play_icons()

        if not getattr(self, '_block_broadcast', False):
            
            self.broadcast_sync_event("pause", None)

    # ------------------------------------------------------------------ #
    # Frame advance (timer callback)                                       #
    # ------------------------------------------------------------------ #

    def advance_frame(self):
        if not getattr(self, 'cached_frame_dict', None) or self.fps <= 0:
            return

        
        current_ms = self.elapsedTimer.elapsed()
        delta_ms = current_ms - self.last_advance_ms
        self.last_advance_ms = current_ms

        delta_ms = min(delta_ms, 100)

        
        rate = self.speedSlider.value() / 100.0
        frames_to_advance = (delta_ms * self.fps * rate) / 1000.0

        if not hasattr(self, 'frame_accumulator'):
            self.frame_accumulator = 0.0
        self.frame_accumulator += frames_to_advance

        int_delta = int(self.frame_accumulator)
        if int_delta < 1:
            return

        # Save state in case of a hold-frame cache miss
        old_index = self.current_cache_index
        old_forward = self.isForward
        old_accumulator = self.frame_accumulator

        self.frame_accumulator -= int_delta

        
        loop_mode = self.loopCombo.currentIndex()
        if loop_mode == 0:
            start_frame = 0
            end_frame = max(0, self.total_frames - 1)
        else:
            if getattr(self, 'needs_range_update', True):
                
                self.active_loop_start, self.active_loop_end = self.get_active_loop_range()
                self.needs_range_update = False
                
                self.update_loop_frames_label()

            start_frame = self.active_loop_start
            end_frame = self.active_loop_end

        if self.isForward:
            self.current_cache_index += int_delta
            if self.current_cache_index > end_frame:
                if loop_mode in (1, 2, 3):
                    if loop_mode == 3:  # Ping-pong
                        self.isForward = False
                        self.current_cache_index = end_frame - (self.current_cache_index - end_frame)
                        self.mediaPlayer.pause()
                        
                        self.audioOutput.setMuted(True)
                    else:
                        self.current_cache_index = start_frame + (self.current_cache_index - end_frame - 1)

                    if self.fps > 0:
                        self.mediaPlayer.setPosition(
                            int(self.current_cache_index * 1000 / self.fps)
                        )
                        
                        self.audioOutput.setVolume(self.audioOutput.volume())
                else:
                    self.current_cache_index = end_frame
                    self.stop_playback()
        else:
            self.current_cache_index -= int_delta
            if self.current_cache_index < start_frame:
                if loop_mode == 3:  # Ping-pong
                    self.isForward = True
                    self.current_cache_index = start_frame + (start_frame - self.current_cache_index)
                    
                    self.audioOutput.setVolume(self.audioOutput.volume())
                    if self.fps > 0:
                        self.mediaPlayer.setPosition(
                            int(self.current_cache_index * 1000 / self.fps)
                        )
                        
                        self.audioOutput.setMuted(self.userMutedIntent)
                        # Ensure the playback rate is set before calling play
                        rate = self.speedSlider.value() / 100.0
                        self.mediaPlayer.setPlaybackRate(rate)
                        self.mediaPlayer.play()
                elif loop_mode == 2:  # Backward loop
                    self.current_cache_index = end_frame - (start_frame - self.current_cache_index - 1)
                else:
                    self.current_cache_index = start_frame
                    self.stop_playback()

        self.current_cache_index = max(0, min(max(0, self.total_frames - 1), self.current_cache_index))

        if self.current_cache_index not in self.cached_frame_dict and not getattr(self, 'is_audio_only', False):
            # Restore state so we don't skip the missing frame once playback resumes
            self.current_cache_index = old_index
            self.isForward = old_forward
            self.frame_accumulator = old_accumulator

            self.was_playing_before_cache_miss = self.is_playing
            self.stop_playback()
            
            self.loadingOverlay.show()

            
            if self.extraction_thread and self.extraction_thread.isRunning():
                t_start = getattr(self.extraction_thread, 'player_start', -1)
                t_end = getattr(self.extraction_thread, 'player_end', -1)
                # Ensure we check the frame we *want* to display, which is old_index + int_delta
                target_frame = old_index + int_delta if old_forward else old_index - int_delta
                if t_start <= target_frame <= t_end:
                    # Thread is already extracting the needed frames. Just wait.
                    return
            
            # Thread is NOT running or NOT covering the needed frame. Force extraction.
            # We request extraction centered on the frame we wanted to reach
            target_frame = old_index + int_delta if old_forward else old_index - int_delta
            
            self.request_frame_extraction(target_frame, force=True)
            return

        self.update_pixmap_from_cache()
        
        self.check_sliding_window()
        self.sync_progress_bar()
        
        self.update_chronometer()

    # ------------------------------------------------------------------ #
    # Seeking / stepping                                                   #
    # ------------------------------------------------------------------ #

    def set_position(self, index):
        self.current_cache_index = index
        self.needs_range_update = True
        self.isForward = True

        if index not in getattr(self, 'cached_frame_dict', {}) and not getattr(self, 'is_audio_only', False):
            
            self.loadingOverlay.show()
            
            self.request_frame_extraction(index, force=True)
        else:
            self.update_pixmap_from_cache()
            
            self.check_sliding_window()
            
            self.update_chronometer()

        if self.fps > 0:
            ms = int((index * 1000) / self.fps)
            
            self.currentTimeLabel.setText(format_time(ms))

        if not getattr(self, '_block_broadcast', False):
            
            self.broadcast_sync_event("seek", index)

    def on_slider_pressed(self):
        self.is_scrubbing = True

    def on_slider_released(self):
        self.is_scrubbing = False
        if self.fps > 0:
            pos = int((self.current_cache_index * 1000) / self.fps)
            self.mediaPlayer.setPosition(pos)
        self.update_pixmap_from_cache()
        
        self.update_chronometer()

    def step_frame(self, direction):
        self.current_cache_index += direction
        
        max_frame = self.progressBar.maximum() if self.progressBar.maximum() > 0 else 0
        self.current_cache_index = max(0, min(max_frame, self.current_cache_index))

        if self.current_cache_index not in getattr(self, 'cached_frame_dict', {}) and not getattr(self, 'is_audio_only', False):
            
            self.loadingOverlay.show()
            
            self.request_frame_extraction(self.current_cache_index, force=True)
            return

        self.update_pixmap_from_cache()
        
        self.check_sliding_window()
        
        self.update_chronometer()

        if not getattr(self, '_block_broadcast', False):
            
            self.broadcast_sync_event("step", direction)

    # ------------------------------------------------------------------ #
    # Media player signal handlers                                        #
    # ------------------------------------------------------------------ #

    def update_play_icons(self):
        if self.is_playing:
            if self.isForward:
                
                self.playButton.setIcon(self.pauseIcon)
                
                self.playBackwardButton.setIcon(self.flippedPlayIcon)
            else:
                
                self.playButton.setIcon(self.normalPlayIcon)
                
                self.playBackwardButton.setIcon(self.pauseIcon)
        else:
            
            self.playButton.setIcon(self.normalPlayIcon)
            
            self.playBackwardButton.setIcon(self.flippedPlayIcon)

    def handle_state_change(self, state):
        is_paused_or_stopped = not self.is_playing
        if hasattr(self, 'stepBackButton'):
            self.stepBackButton.setEnabled(is_paused_or_stopped)
            
            self.stepForwardButton.setEnabled(is_paused_or_stopped)
        self.update_play_icons()

        # Re-apply locked speed when transitioning to playing state
        if state == QMediaPlayer.PlaybackState.PlayingState:
            is_speed_locked = getattr(self, 'isSpeedLocked', False)
            speed_slider = getattr(self, 'speedSlider', None)
            if speed_slider is not None and is_speed_locked:
                speed_val = speed_slider.value()
                self.mediaPlayer.setPlaybackRate(speed_val / 100.0)

    def update_duration(self, duration):
        # Use ffprobe nb_frames if available to prevent drift/over-estimation
        if hasattr(self, 'ffprobe_nb_frames') and self.ffprobe_nb_frames > 0:
            self.total_frames = self.ffprobe_nb_frames
            if self.fps > 0:
                duration = (self.total_frames * 1000.0) / self.fps
        elif self.fps > 0:
            self.total_frames = int((duration / 1000.0) * self.fps)
            
        
        self.totalTimeLabel.setText(format_time(duration))
        self.sync_progress_bar()

        last_valid_frame = max(0, self.total_frames - 1)
        self.markers = [m for m in self.markers if m <= last_valid_frame]
        
        self.progressBar.update_markers(self.markers)
        
        self.update_loop_frames_label()

    def handle_status_change(self, status):
        if status in (QMediaPlayer.MediaStatus.LoadedMedia, QMediaPlayer.MediaStatus.BufferedMedia):
            if status == QMediaPlayer.MediaStatus.LoadedMedia:
                self.handle_metadata_change()
            
            # Apply current speed slider value to the media player
            speed_slider = getattr(self, 'speedSlider', None)
            if speed_slider is not None:
                speed_val = speed_slider.value()
                self.mediaPlayer.setPlaybackRate(speed_val / 100.0)

            
            if self.view and self.pixmapItem and self.last_transform_state is None:
                self.apply_transformations(fit=True)
                if hasattr(self, '_apply_file_saved_zoom'):
                    self._apply_file_saved_zoom()

    def handle_metadata_change(self):
        pass

    def on_speed_slider_changed(self, value):
        snapped = round(value / 5) * 5
        if snapped != value:
            
            self.speedSlider.setValue(snapped)
            return
        rate = snapped / 100.0
        self.mediaPlayer.setPlaybackRate(rate)
        if hasattr(self, 'speedValueLabel') and self.speedValueLabel:
            if hasattr(self.speedValueLabel, 'setValue'):
                self.speedValueLabel.blockSignals(True)
                self.speedValueLabel.setValue(snapped)
                self.speedValueLabel.blockSignals(False)
            else:
                self.speedValueLabel.setText(f"{snapped}%")

        if not getattr(self, '_block_broadcast', False):
            
            self.broadcast_sync_event("speed", snapped)

    # ------------------------------------------------------------------ #
    # Window close                                                         #
    # ------------------------------------------------------------------ #

    def closeEvent(self, event):
        self.cleanup_cache()
        
        try:
            from utils import get_markers_path
            path = get_markers_path()
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            print(f"Error removing markers.json on exit: {e}")
            
        super().closeEvent(event)

    def _apply_file_saved_zoom(self):
        if not self.currentFilePath:
            return
        
        data = self.playlistData.get(self.currentFilePath, {})
        zoom = data.get('zoom', 100)
        center_x = data.get('centerX', data.get('scrollX', None))
        center_y = data.get('centerY', data.get('scrollY', None))
        
        current_file = self.currentFilePath
        
        QTimer.singleShot(100, lambda: self._execute_file_saved_zoom(zoom, center_x, center_y, current_file))

    def _execute_file_saved_zoom(self, zoom, center_x, center_y, target_file):
        if self.currentFilePath != target_file:
            self.is_loading_video = False
            return
            
        val = int(zoom * 100) if zoom < 10 else int(zoom)
        
        self.update_zoom(val)
        
        if hasattr(self, 'view') and self.view:
            if center_x is not None and center_y is not None:
                self.view.centerOn(QPointF(center_x, center_y))
            elif hasattr(self, 'pixmapItem') and self.pixmapItem:
                self.view.centerOn(self.pixmapItem.boundingRect().center())
            
        self.is_loading_video = False

    def on_user_zoom_changed(self, zoom_level):
        if self.is_loading_video:
            return
        
        self.sync_zoom_ui(zoom_level)
