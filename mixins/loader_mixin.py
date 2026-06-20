"""
LoaderMixin — media file/folder loading, ffprobe metadata extraction, and saved zoom level recovery.
"""

import os
import subprocess
import json
from PyQt6.QtCore import Qt, QUrl, QTimer, QPointF
from PyQt6.QtMultimedia import QMediaPlayer
from qfluentwidgets import FluentIcon
from utils import get_resource_path, format_time, VERSION, get_embedded_video_offset
from translations import tr

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QMainWindow, QPushButton, QSlider, QLabel
    from PyQt6.QtMultimedia import QAudioOutput
    from config import Configuration
    from components import GPUPixmapItem
    LoaderMixinBase = QMainWindow
else:
    LoaderMixinBase = object


class LoaderMixin(LoaderMixinBase):
    if TYPE_CHECKING:
        config: Configuration
        mediaPlayer: QMediaPlayer
        audioOutput: QAudioOutput
        current_temp_dir: str | None
        currentFilePath: str | None
        currentVideoPath: str | None
        video_codec: str | None
        is_hdr: bool
        color_transfer: str
        color_primaries: str
        last_transform_state: tuple | None
        is_motion_photo: bool
        motion_photo_original_path: str | None
        is_audio_only: bool
        cached_frame_dict: dict
        cached_file_path: str | None
        current_cache_index: int
        fps: float
        total_frames: int
        playButton: QPushButton
        subtitleLabel: QLabel | None
        subtitles: list
        subtitleFilePath: str | None
        playlistData: dict
        ffprobe_fps: float
        ffprobe_duration: float
        ffprobe_nb_frames: int
        audio_tracks_info: list
        speedSlider: QSlider
        progressBar: QSlider
        view: any
        pixmapItem: GPUPixmapItem | None
        markers: list
        loadingOverlay: QLabel
        is_loading_video: bool

        load_playlist_by_path: callable
        add_files_to_playlist: callable
        stop_playback: callable
        cleanup_cache: callable
        save_current_markers: callable
        sync_progress_bar: callable
        update_pixmap_from_cache: callable
        apply_transformations: callable
        start_full_extraction: callable
        load_markers_for_current: callable
        generate_audio_placeholder: callable
        update_duration: callable
        handle_metadata_change: callable
        auto_load_subtitles_for_video: callable
        update_zoom: callable
        sync_zoom_ui: callable

    def open_media(self):
        """
        Unified smart file/folder picker.
        • Selecting one or more files  → adds those files directly.
        • Clicking a folder and pressing Open (non-native dialog) → adds ALL
          matching files from that folder automatically.
        Supports playlist files (.json / .bpl) as well.
        """
        from PyQt6.QtWidgets import QFileDialog

        video_exts = ('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.m4v', '.webm', '.flv', '.mpg', '.mpeg', '.ogv')
        image_exts = ('.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff')
        audio_exts = ('.mp3', '.wav', '.aac', '.flac', '.m4a', '.ogg', '.wma')
        playlist_exts = ('.json', '.bpl')
        
        all_exts = video_exts + image_exts + audio_exts + playlist_exts

        name_filters = [
            f"{tr('all_media')} (*.mp4 *.mkv *.avi *.mov *.wmv *.m4v *.webm *.flv *.mpg *.mpeg *.ogv *.jpg *.jpeg *.png *.bmp *.webp *.tiff *.mp3 *.wav *.aac *.flac *.m4a *.ogg *.wma *.json *.bpl)",
            f"{tr('video_files')} (*.mp4 *.mkv *.avi *.mov *.wmv *.m4v *.webm *.flv *.mpg *.mpeg *.ogv)",
            f"{tr('image_files')} (*.jpg *.jpeg *.png *.bmp *.webp *.tiff)",
            f"{tr('audio_files')} (*.mp3 *.wav *.aac *.flac *.m4a *.ogg *.wma)",
            f"{tr('playlist')} (*.bpl *.json)",
        ]
        title = tr('add_files_title')

        dialog = QFileDialog(self, title)
        dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dialog.setNameFilters(name_filters)

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
                
                bg_color_ref = qcolor_to_colorref(QColor(bg_color))
                fg_color_ref = qcolor_to_colorref(QColor(fg_color))
                
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(ctypes.c_int(bg_color_ref)), 4)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 36, ctypes.byref(ctypes.c_int(fg_color_ref)), 4)
            except Exception as e:
                print(f"[DWM] Failed to set custom title bar colors: {e}")

        from PyQt6.QtCore import QDir
        drive_urls = [QUrl.fromLocalFile(d.absolutePath()) for d in QDir.drives()]
        dialog.setSidebarUrls(drive_urls)

        from PyQt6.QtWidgets import QDialogButtonBox, QPushButton, QWidget, QHBoxLayout, QLabel, QToolButton
        
        for label in dialog.findChildren(QLabel):
            text_clean = label.text().replace('&', '')
            if "File name" in text_clean:
                label.setText(tr('file_name'))
            elif "Files of type" in text_clean:
                label.setText(tr('file_types'))

        from PyQt6.QtGui import QPixmap, QIcon, QPainter
        from PyQt6.QtCore import QSize
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
                dialog.done(1)
            add_folder_btn.clicked.connect(on_add_folder_clicked)
            
            layout = button_box.layout()
            if layout and open_btn:
                idx = layout.indexOf(open_btn)
                if idx != -1:
                    container = QWidget()
                    h_layout = QHBoxLayout(container)
                    h_layout.setContentsMargins(0, 0, 0, 0)
                    h_layout.setSpacing(6)
                    
                    layout.removeWidget(open_btn)
                    h_layout.addWidget(open_btn)
                    h_layout.addWidget(add_folder_btn)
                    
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
        self.loop_count = 0

        self.mediaPlayer.setSource(QUrl())
        self.cleanup_cache()
        self.save_current_markers()
        is_image = False
        try:
            self.is_loading_video = True
            if hasattr(self, 'subtitles'):
                self.subtitles = []
                self.subtitleFilePath = None
                if hasattr(self, 'subtitleLabel') and self.subtitleLabel:
                    self.subtitleLabel.hide()
            self.currentFilePath = filePath
            self.currentVideoPath = filePath
            self.video_codec = None
            self.is_hdr = False
            self.color_transfer = ""
            self.color_primaries = ""
            self.last_transform_state = None
            self.is_motion_photo = False
            self.motion_photo_original_path = None
            self.is_audio_only = False
            if hasattr(self, 'initial_fit_done'):
                delattr(self, 'initial_fit_done')

            is_image = filePath.lower().endswith(
                ('.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff')
            )

            embedded_offset = None
            if is_image and filePath.lower().endswith(('.jpg', '.jpeg')):
                embedded_offset = get_embedded_video_offset(filePath)

            if embedded_offset is not None:
                self.is_motion_photo = True
                self.motion_photo_original_path = filePath
                if not self.current_temp_dir:
                    import tempfile
                    self.current_temp_dir = tempfile.mkdtemp(prefix="boomerang_frames_")
                
                temp_video_path = os.path.join(self.current_temp_dir, "extracted_video.mp4")
                try:
                    with open(filePath, 'rb') as f:
                        f.seek(embedded_offset)
                        video_data = f.read()
                    with open(temp_video_path, 'wb') as f:
                        f.write(video_data)
                    self.currentVideoPath = temp_video_path
                    is_image = False
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

                self.ffprobe_fps = fps
                self.ffprobe_duration = duration_ms
                self.ffprobe_nb_frames = total_frames
                self.fps = fps
                self.total_frames = total_frames

                self.update_duration(duration_ms)

                self.mediaPlayer.pause()
                self.playButton.setIcon(FluentIcon.PLAY)
                self.playButton.setEnabled(True)

            self.load_markers_for_current()

            if not is_image:
                if hasattr(self, 'auto_load_subtitles_for_video'):
                    self.auto_load_subtitles_for_video(filePath)

            if not is_image:
                if self.is_audio_only:
                    self.generate_audio_placeholder()
                    self.update_pixmap_from_cache()
                    self.apply_transformations(fit=True)
                else:
                    self.update_pixmap_from_cache()
                    self.start_full_extraction()

            if getattr(self, 'autoplay_next', False):
                if self.is_audio_only or is_image:
                    self.autoplay_next = False
                    loop_mode = self.loopCombo.currentIndex()
                    if loop_mode == 2:
                        self.isForward = False
                        self.current_cache_index = max(0, self.total_frames - 1)
                    else:
                        self.isForward = True
                        self.current_cache_index = 0
                    self._start_playback()

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
                pass
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
                "-show_entries", "stream=index,codec_type,codec_name,avg_frame_rate,duration,nb_frames,channels,color_space,color_transfer,color_primaries:stream_tags=language,title:format=duration",
                "-of", "json", file_path
            ]

            creationflags = 0
            if os.name == 'nt':
                creationflags = subprocess.CREATE_NO_WINDOW

            result = subprocess.check_output(cmd, creationflags=creationflags).decode('utf-8')
            data = json.loads(result)
            streams = data.get('streams', [])
            
            self.audio_tracks_info = []
            audio_idx = 0
            for s in streams:
                if s.get('codec_type') == 'audio':
                    tags = s.get('tags', {})
                    lang = tags.get('language', 'und')
                    title = tags.get('title', '')
                    codec = s.get('codec_name', 'unknown')
                    channels = s.get('channels', 2)
                    self.audio_tracks_info.append({
                        'index': audio_idx,
                        'stream_index': s.get('index'),
                        'codec': codec,
                        'language': lang,
                        'title': title,
                        'channels': channels
                    })
                    audio_idx += 1
            
            video_stream = next((s for s in streams if s.get('codec_type') == 'video'), None)
            audio_stream = next((s for s in streams if s.get('codec_type') == 'audio'), None)
            
            self.is_audio_only = (video_stream is None and audio_stream is not None)
            
            self.is_hdr = False
            self.color_transfer = ""
            self.color_primaries = ""
            if video_stream:
                self.color_transfer = video_stream.get('color_transfer', '')
                self.color_primaries = video_stream.get('color_primaries', '')
                if self.color_transfer in ('smpte2084', 'arib-std-b67') or self.color_primaries == 'bt2020':
                    self.is_hdr = True
            
            if not self.is_hdr and file_path:
                bn = os.path.basename(file_path).lower()
                if '.hdr.' in bn or '_hdr_' in bn or bn.endswith('hdr') or 'hdr10' in bn:
                    self.is_hdr = True

            stream = video_stream if video_stream is not None else audio_stream
            if not stream:
                return 30.0, 0, 0

            fmt = data.get('format', {})
            
            if self.is_audio_only:
                fps = 30.0
            else:
                fps_str = stream.get('r_frame_rate', stream.get('avg_frame_rate', '30/1'))
                if '/' in fps_str:
                    num, den = map(int, fps_str.split('/'))
                    fps = num / den if den != 0 else 30.0
                else:
                    fps = float(fps_str)
                
            s_dur = stream.get('duration')
            f_dur = fmt.get('duration')
            duration = float(s_dur if s_dur is not None else (f_dur if f_dur is not None else 0))
            
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
