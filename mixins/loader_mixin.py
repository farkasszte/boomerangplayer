"""
LoaderMixin — media file/folder loading, ffprobe metadata extraction, and saved zoom level recovery.
"""

import os
import subprocess
import json
import logging
from PyQt6.QtCore import Qt, QUrl, QTimer, QPointF
from PyQt6.QtMultimedia import QMediaPlayer
from utils import mark_temp_dir_owner
from qfluentwidgets import FluentIcon
from utils import get_resource_path, format_time, VERSION, get_embedded_video_offset
from translations import tr

logger = logging.getLogger("Loader")

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
        """Custom file picker — avoids QFileDialog which corrupts DWM rendering in fullscreen."""
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                                      QListWidget, QListWidgetItem, QPushButton,
                                      QComboBox, QLineEdit, QLabel, QAbstractItemView,
                                      QTreeWidget, QTreeWidgetItem,
                                      QSplitter, QHeaderView, QToolButton,
                                      QStackedWidget, QApplication, QStyle)
        from PyQt6.QtGui import QIcon, QColor
        from PyQt6.QtWidgets import QHeaderView as _QHVRaw
        import re
        from PyQt6.QtCore import QDir, Qt, QStorageInfo, QStandardPaths, QSize, QObject, QTimer, pyqtSignal as _Signal
        from workers.threads import ThumbnailThread

        class _ClickableHeader(_QHVRaw):
            sectionClicked = _Signal(int)
            def mousePressEvent(self, e):
                idx = self.logicalIndexAt(e.pos())
                if idx >= 0:
                    self.sectionClicked.emit(idx)
                super().mousePressEvent(e)

        video_exts = ('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.m4v', '.webm', '.flv', '.mpg', '.mpeg', '.ogv')
        image_exts = ('.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff')
        audio_exts = ('.mp3', '.wav', '.aac', '.flac', '.m4a', '.ogg', '.wma')
        playlist_exts = ('.json', '.bpl')
        all_exts = video_exts + image_exts + audio_exts + playlist_exts
        filter_map = {0: all_exts, 1: video_exts, 2: image_exts, 3: audio_exts, 4: playlist_exts}

        inverse_text = self.config.get('inverse_text', False)
        accent_color = self.config.get('accent_color', '#00f2ff')
        bg_color = self.config.get('bg_color', '#202020')
        fg_color = "#1c1c1c" if inverse_text else "#ffffff"
        widget_bg = "#ffffff" if inverse_text else "#1a1a1a"
        border = "rgba(0,0,0,0.15)" if inverse_text else "rgba(255,255,255,0.1)"
        hover = "rgba(0,0,0,0.08)" if inverse_text else "rgba(255,255,255,0.1)"
        header_bg = "#eaeaea" if inverse_text else "#252525"

        dialog = QDialog(self)
        dialog.setWindowTitle(tr('add_files_title'))
        dialog.setModal(False)
        dialog.setMinimumSize(850, 500)
        dialog.setStyleSheet(f"""
            QDialog, QLabel {{
                background-color: {bg_color}; color: {fg_color}; font-size: 13px;
            }}
            QListWidget {{
                background-color: {widget_bg}; color: {fg_color};
                border: 1px solid {border}; border-radius: 4px; outline: none;
            }}
            QListWidget::item {{ padding: 4px 8px; border: none; outline: none; }}
            QListWidget::item:selected {{ background-color: {accent_color}; color: #000; }}
            QListWidget::item:hover {{ background-color: {hover}; }}
            QTreeWidget {{
                background-color: {widget_bg}; color: {fg_color};
                border: 1px solid {border}; border-radius: 4px; outline: none;
                font-size: 13px;
            }}
            QTreeWidget::item {{ padding: 2px 4px; border: none; outline: none; }}
            QTreeWidget::item:selected {{ background-color: {accent_color}; color: #000; }}
            QTreeWidget::item:hover {{ background-color: {hover}; }}
            QHeaderView::section {{
                background-color: {header_bg}; color: {fg_color};
                border: none; padding: 4px 8px; font-size: 12px; font-weight: bold;
            }}
            QLineEdit {{
                border: 1px solid {border}; border-radius: 4px;
                padding: 5px; background: {widget_bg}; color: {fg_color};
            }}
            QComboBox {{
                border: 1px solid {border}; border-radius: 4px;
                padding: 4px 8px; background: {widget_bg}; color: {fg_color};
            }}
            QPushButton {{
                background: {widget_bg}; border: 1px solid {border};
                border-radius: 4px; padding: 6px 12px; min-width: 75px;
                font-weight: 500; color: {fg_color};
            }}
            QPushButton:hover {{ background-color: {hover}; }}
            QSplitter::handle {{ background: {border}; width: 1px; }}
        """)

        # Windows 11 DWM title bar
        import sys
        if sys.platform == 'win32':
            try:
                import ctypes
                hwnd = int(dialog.winId())
                def _qcolor_to_ref(c):
                    return c.red() | (c.green() << 8) | (c.blue() << 16)
                bg_ref = _qcolor_to_ref(QColor(bg_color))
                fg_ref = _qcolor_to_ref(QColor(fg_color))
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(ctypes.c_int(bg_ref)), 4)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 36, ctypes.byref(ctypes.c_int(fg_ref)), 4)
            except Exception:
                pass

        # === State + helper functions (defined before UI uses them) ===
        default_folder = self.config.get('default_folder', '')
        dialog._current_path = default_folder if default_folder and os.path.isdir(default_folder) else QDir.rootPath()
        dialog._history = []
        dialog._history_idx = -1
        dialog.selected_files = []
        dialog._view_mode = "detail"  # "detail" or "list"

        def _format_size(size):
            if size < 1024: return f"{size} B"
            elif size < 1048576: return f"{size/1024:.0f} KB"
            elif size < 1073741824: return f"{size/1048576:.1f} MB"
            else: return f"{size/1073741824:.2f} GB"

        def _format_date(dt):
            return dt.toString("dd/MM/yyyy HH:mm") if dt.isValid() else ""

        def _get_special_folders():
            folders = []
            try:
                mapping = [
                    ('Videos', QStandardPaths.StandardLocation.MoviesLocation),
                    ('Pictures', QStandardPaths.StandardLocation.PicturesLocation),
                    ('Desktop', QStandardPaths.StandardLocation.DesktopLocation),
                    ('Downloads', QStandardPaths.StandardLocation.DownloadLocation),
                    ('Documents', QStandardPaths.StandardLocation.DocumentsLocation),
                    ('Music', QStandardPaths.StandardLocation.MusicLocation),
                ]
                for label, loc in mapping:
                    p = QStandardPaths.writableLocation(loc)
                    if p and os.path.isdir(p):
                        folders.append((label, p))
            except Exception:
                pass
            # OneDrive (registry first, then common fallback path)
            od = None
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\OneDrive") as k:
                    od = winreg.QueryValueEx(k, "UserFolder")[0]
            except Exception:
                try:
                    od = os.path.expandvars(r"%UserProfile%\OneDrive")
                except Exception:
                    od = None
            if od and os.path.isdir(od):
                folders.append(("OneDrive", od))
            return folders

        def _highlight_drive(dlg):
            path = dlg._current_path.lower()
            best_idx, best_len = None, -1
            for i in range(dlg._drive_list.count()):
                d = dlg._drive_list.item(i).data(Qt.ItemDataRole.UserRole)
                if not d:
                    continue
                d = d.lower()
                if path.startswith(d) and len(d) > best_len:
                    best_idx, best_len = i, len(d)
            if best_idx is not None:
                dlg._drive_list.blockSignals(True)
                dlg._drive_list.setCurrentRow(best_idx)
                dlg._drive_list.blockSignals(False)

        def _natural_key(s):
            # Digit-aware (natural) sort so "2" comes before "10", case-insensitive.
            return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', s)]

        _DIR_ROLE = Qt.ItemDataRole.UserRole + 1
        _SIZE_ROLE = Qt.ItemDataRole.UserRole + 2
        _DATE_ROLE = Qt.ItemDataRole.UserRole + 3
        _TYPE_ROLE = Qt.ItemDataRole.UserRole + 4

        class _SortTreeItem(QTreeWidgetItem):
            def __lt__(self, other):
                tw = self.treeWidget()
                col = tw.sortColumn() if tw is not None else 0
                self_dir = bool(self.data(0, _DIR_ROLE))
                other_dir = bool(other.data(0, _DIR_ROLE))
                if self_dir != other_dir:
                    return self_dir and not other_dir  # folders always first
                if col == 1:  # size
                    return (self.data(0, _SIZE_ROLE) or 0) < (other.data(0, _SIZE_ROLE) or 0)
                if col == 3:  # date modified
                    a = self.data(0, _DATE_ROLE)
                    b = other.data(0, _DATE_ROLE)
                    a = a.toMSecsSinceEpoch() if a is not None else 0
                    b = b.toMSecsSinceEpoch() if b is not None else 0
                    return a < b
                if col == 2:  # type
                    return (self.data(0, _TYPE_ROLE) or '') < (other.data(0, _TYPE_ROLE) or '')
                return _natural_key(self.text(0)) < _natural_key(other.text(0))

        def _apply_sort(dlg):
            col = dlg._sort_column
            rev = dlg._sort_order == 'desc'

            def key(e):
                if col == 1:
                    return e['size']
                if col == 3:
                    return e['date'].toMSecsSinceEpoch()
                if col == 2:
                    return e['suffix'].lower()
                return _natural_key(e['name'])

            dirs = [e for e in dlg._entries if e['is_dir']]
            files = [e for e in dlg._entries if not e['is_dir']]
            dirs.sort(key=key, reverse=rev)
            files.sort(key=key, reverse=rev)
            dlg._sorted_entries = dirs + files

        _col_labels = [tr('name'), tr('size'), tr('type'), tr('date_modified')]

        def _update_header_labels(dlg):
            labels = []
            for i, base in enumerate(_col_labels):
                if i == dlg._sort_column:
                    arrow = ' ▼' if dlg._sort_order == 'desc' else ' ▲'
                    labels.append(base + arrow)
                else:
                    labels.append(base)
            dlg._file_tree.setHeaderLabels(labels)

        def _on_header_clicked(dlg, idx):
            if dlg._sort_column == idx:
                dlg._sort_order = 'desc' if dlg._sort_order == 'asc' else 'asc'
            else:
                dlg._sort_column = idx
                dlg._sort_order = 'asc'
            _apply_sort(dlg)
            _render_tree(dlg, dlg._view_mode == 'detail')
            _update_header_labels(dlg)

        def _refresh(dlg):
            path = dlg._current_path
            dlg._path_bar.setText(path)
            _highlight_drive(dlg)
            exts = filter_map.get(dlg._filter_combo.currentIndex(), all_exts)
            name_filter = dlg._name_filter.text().strip().lower()
            d = QDir(path)
            d.setFilter(QDir.Filter.Dirs | QDir.Filter.Files | QDir.Filter.NoDotAndDotDot)
            raw = []
            for info in d.entryInfoList():
                name = info.fileName()
                is_dir = info.isDir()
                if not is_dir and not name.lower().endswith(exts):
                    continue
                if name_filter and name.lower().find(name_filter) == -1:
                    continue
                raw.append({
                    'name': name,
                    'path': info.absoluteFilePath(),
                    'is_dir': is_dir,
                    'size': info.size(),
                    'date': info.lastModified(),
                    'suffix': info.suffix(),
                })
            dlg._entries = raw
            _apply_sort(dlg)
            _render_active(dlg)

        def _item_path(item):
            # QTreeWidgetItem.data(column, role) vs QListWidgetItem.data(role)
            try:
                return item.data(0, Qt.ItemDataRole.UserRole)
            except TypeError:
                return item.data(Qt.ItemDataRole.UserRole)

        def _selected_paths(dlg):
            if dlg._view_mode == 'thumb':
                items = dlg._thumb_list.selectedItems()
            else:
                items = dlg._file_tree.selectedItems()
            return [_item_path(item) for item in items]

        def _render_active(dlg):
            if dlg._view_mode == 'thumb':
                _render_thumb(dlg)
            else:
                _render_tree(dlg, dlg._view_mode == 'detail')

        def _render_tree(dlg, detail):
            dlg._file_tree.clear()
            for e in dlg._sorted_entries:
                type_str = "File Folder" if e['is_dir'] else (e['suffix'].upper() + " File" if e['suffix'] else "File")
                item = _SortTreeItem()
                item.setData(0, Qt.ItemDataRole.UserRole, e['path'])
                item.setData(0, _DIR_ROLE, e['is_dir'])
                item.setData(0, _SIZE_ROLE, e['size'])
                item.setData(0, _DATE_ROLE, e['date'])
                item.setData(0, _TYPE_ROLE, type_str)
                item.setText(0, e['name'])
                if e['is_dir']:
                    item.setForeground(0, QColor(accent_color))
                    if detail:
                        item.setText(1, "—")
                        item.setText(2, type_str)
                        item.setText(3, _format_date(e['date']))
                else:
                    if detail:
                        item.setText(1, _format_size(e['size']))
                        item.setText(2, type_str)
                        item.setText(3, _format_date(e['date']))
                dlg._file_tree.addTopLevelItem(item)

        def _render_thumb(dlg):
            for t in dlg._thumb_threads:
                try:
                    t.cancel()
                except Exception:
                    pass
            dlg._thumb_threads = []
            dlg._thumb_list.clear()
            dlg._thumb_items_by_path = {}
            dlg._thumb_pending = set()
            dlg._thumb_done = set()
            for e in dlg._sorted_entries:
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, e['path'])
                item.setText(e['name'])
                if e['is_dir']:
                    item.setIcon(dlg._folder_icon)
                    dlg._thumb_done.add(e['path'])
                else:
                    item.setIcon(dlg._file_icon)
                dlg._thumb_items_by_path[e['path']] = item
                dlg._thumb_list.addItem(item)
            QTimer.singleShot(30, lambda: _ensure_visible_thumbs(dlg))

        def _ensure_visible_thumbs(dlg):
            if dlg._view_mode != 'thumb':
                return
            viewport = dlg._thumb_list.viewport()
            rect = viewport.rect()
            max_concurrent = 12
            for i in range(dlg._thumb_list.count()):
                if len(dlg._thumb_pending) >= max_concurrent:
                    break
                item = dlg._thumb_list.item(i)
                path = item.data(Qt.ItemDataRole.UserRole)
                if path in dlg._thumb_done or path in dlg._thumb_pending:
                    continue
                r = dlg._thumb_list.visualItemRect(item)
                if not r.isValid() or not rect.intersects(r):
                    continue
                dlg._thumb_pending.add(path)
                t = ThumbnailThread(path, dlg)
                t.finished.connect(lambda p, px, _it=item, _p=path: _on_thumb(dlg, _it, _p, px))
                dlg._thumb_threads.append(t)
                t.start()

        def _on_thumb(dlg, item, path, pixmap):
            dlg._thumb_pending.discard(path)
            dlg._thumb_done.add(path)
            if pixmap is not None and not pixmap.isNull():
                item.setIcon(QIcon(pixmap))
            _ensure_visible_thumbs(dlg)


        def _navigate(dlg, path):
            if not path or not os.path.isdir(path):
                return
            if dlg._current_path != path:
                if dlg._history_idx < len(dlg._history) - 1:
                    dlg._history = dlg._history[:dlg._history_idx + 1]
                dlg._history.append(dlg._current_path)
                dlg._history_idx = len(dlg._history) - 1
            dlg._current_path = path
            _refresh(dlg)

        def _go_back():
            if dialog._history_idx > 0:
                dialog._history_idx -= 1
                dialog._current_path = dialog._history[dialog._history_idx]
                _refresh(dialog)

        def _go_forward():
            if dialog._history_idx < len(dialog._history) - 1:
                dialog._history_idx += 1
                dialog._current_path = dialog._history[dialog._history_idx]
                _refresh(dialog)

        def _on_open():
            selected = [p for p in _selected_paths(dialog) if os.path.isfile(p)]
            if selected:
                dialog.selected_files = selected
                dialog.accept()

        def _on_add_folder():
            exts = filter_map.get(dialog._filter_combo.currentIndex(), all_exts)
            name_filter = dialog._name_filter.text().strip().lower()
            files = []
            for f in sorted(os.listdir(dialog._current_path)):
                if not f.lower().endswith(exts):
                    continue
                if name_filter and f.lower().find(name_filter) == -1:
                    continue
                files.append(os.path.join(dialog._current_path, f))
            if files:
                dialog.selected_files = files
                dialog.accept()

        def _apply_view_visibility(dlg):
            is_thumb = dlg._view_mode == 'thumb'
            dlg._stack.setCurrentIndex(1 if is_thumb else 0)
            dlg._file_tree.header().setVisible(dlg._view_mode == 'detail')
            for mode, btn in dlg._view_btns.items():
                btn.setChecked(mode == dlg._view_mode)

        def _set_view(mode):
            dialog._view_mode = mode
            _apply_view_visibility(dialog)
            _refresh(dialog)

        def _set_default():
            self.config['default_folder'] = dialog._current_path
            from qfluentwidgets import InfoBar, InfoBarPosition
            InfoBar.success(
                title='',
                content=tr('default_folder_set'),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )

        # === UI layout ===
        root = QVBoxLayout(dialog)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Top bar: path + nav buttons + view buttons + default-folder lock
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(12, 10, 12, 6)
        top_bar.setSpacing(6)
        dialog._path_bar = QLineEdit()
        dialog._path_bar.returnPressed.connect(lambda: _navigate(dialog, dialog._path_bar.text()))
        top_bar.addWidget(dialog._path_bar, 1)

        top_btn_size = 28
        top_btn_style = "QPushButton { min-width: 0px; padding: 2px; }"

        def _get_drive_root(path):
            if len(path) >= 2 and path[1] == ':':
                return path[:2].upper() + "\\"
            return QDir.rootPath()

        home_sp = getattr(QStyle.StandardPixmap, 'SP_DirHomeIcon', None) or QStyle.StandardPixmap.SP_DirHome
        for icon_sp, handler, tip in [
            (QStyle.StandardPixmap.SP_ArrowLeft, _go_back, tr('go_back')),
            (QStyle.StandardPixmap.SP_ArrowRight, _go_forward, tr('go_forward')),
            (QStyle.StandardPixmap.SP_FileDialogToParent, lambda: _navigate(dialog, os.path.dirname(dialog._current_path)), tr('go_up')),
            (home_sp, lambda: _navigate(dialog, _get_drive_root(dialog._current_path)), tr('go_home')),
        ]:
            btn = QPushButton()
            btn.setIcon(QApplication.instance().style().standardIcon(icon_sp))
            btn.setFixedSize(top_btn_size, top_btn_size)
            btn.setToolTip(tip)
            btn.setStyleSheet(top_btn_style)
            btn.clicked.connect(handler)
            top_bar.addWidget(btn)

        lock_btn = QPushButton("🔒")
        lock_btn.setFixedSize(top_btn_size, top_btn_size)
        lock_btn.setToolTip(tr('set_default_folder'))
        lock_btn.setStyleSheet(top_btn_style)
        lock_btn.clicked.connect(_set_default)
        top_bar.addWidget(lock_btn)

        view_labels = {'detail': tr('detail_view'), 'list': tr('list_view'), 'thumb': tr('thumbnail_view')}
        view_icons = {
            'detail': QStyle.StandardPixmap.SP_FileDialogDetailedView,
            'list': QStyle.StandardPixmap.SP_FileDialogListView,
            'thumb': QStyle.StandardPixmap.SP_FileDialogContentsView,
        }
        _app_style = QApplication.instance().style()
        dialog._view_btns = {}
        for mode in ['detail', 'list', 'thumb']:
            btn = QPushButton()
            btn.setIcon(_app_style.standardIcon(view_icons[mode]))
            btn.setFixedSize(top_btn_size, top_btn_size)
            btn.setCheckable(True)
            btn.setToolTip(view_labels[mode])
            btn.setStyleSheet(top_btn_style)
            btn.clicked.connect(lambda _=None, m=mode: _set_view(m))
            dialog._view_btns[mode] = btn
            top_bar.addWidget(btn)

        root.addLayout(top_bar)

        # Main area: drive sidebar | file tree
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        dialog._drive_list = QListWidget()
        dialog._drive_list.setFixedWidth(160)

        for label, p in _get_special_folders():
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, p)
            dialog._drive_list.addItem(item)
        sep = QListWidgetItem("—")
        sep.setFlags(Qt.ItemFlag.NoItemFlags)
        dialog._drive_list.addItem(sep)

        for drive in QDir.drives():
            d_path = drive.path()
            try:
                si = QStorageInfo(d_path)
                vol_name = si.displayName() if si.isValid() and si.name() else d_path
            except Exception:
                vol_name = d_path
            item = QListWidgetItem(f"{vol_name} ({d_path})")
            item.setData(Qt.ItemDataRole.UserRole, d_path)
            dialog._drive_list.addItem(item)
        dialog._drive_list.currentRowChanged.connect(lambda: (
            _navigate(dialog, dialog._drive_list.currentItem().data(Qt.ItemDataRole.UserRole))
            if dialog._drive_list.currentItem() else None
        ))
        splitter.addWidget(dialog._drive_list)

        dialog._file_tree = QTreeWidget()
        dialog._sort_column = 0
        dialog._sort_order = 'asc'
        dialog._file_tree.setHeaderLabels([tr('name') + ' ▲', tr('size'), tr('type'), tr('date_modified')])
        dialog._file_tree.setRootIsDecorated(False)
        dialog._file_tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        hdr = _ClickableHeader(Qt.Orientation.Horizontal)
        dialog._file_tree.setHeader(hdr)
        hdr.setSectionsClickable(True)
        hdr.sectionClicked.connect(lambda idx: _on_header_clicked(dialog, idx))
        hdr.resizeSection(0, 350)
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)

        dialog._thumb_list = QListWidget()
        dialog._thumb_list.setViewMode(QListWidget.ViewMode.IconMode)
        dialog._thumb_list.setIconSize(QSize(120, 120))
        dialog._thumb_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        dialog._thumb_list.setSpacing(10)
        dialog._thumb_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        dialog._thumb_list.hide()
        dialog._thumb_threads = []
        dialog._thumb_items_by_path = {}
        dialog._thumb_pending = set()
        dialog._thumb_done = set()
        dialog._thumb_list.verticalScrollBar().valueChanged.connect(
            lambda _=None: _ensure_visible_thumbs(dialog))

        class _ThumbResizeFilter(QObject):
            def __init__(self, dlg, parent=None):
                super().__init__(parent)
                self._dlg = dlg
            def eventFilter(self, obj, event):
                if event.type() == event.Type.Resize:
                    _ensure_visible_thumbs(self._dlg)
                return super().eventFilter(obj, event)
        dialog._thumb_list.installEventFilter(_ThumbResizeFilter(dialog))

        try:
            _style = QApplication.instance().style()
            dialog._folder_icon = _style.standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon)
            dialog._file_icon = _style.standardIcon(QStyle.StandardPixmap.SP_FileIcon)
        except Exception:
            dialog._folder_icon = QIcon()
            dialog._file_icon = QIcon()

        def _on_item_double_clicked(item, col=None):
            p = _item_path(item)
            if os.path.isdir(p):
                _navigate(dialog, p)
            else:
                dialog.selected_files = [p]
                dialog.accept()
        dialog._file_tree.itemDoubleClicked.connect(_on_item_double_clicked)
        dialog._thumb_list.itemDoubleClicked.connect(_on_item_double_clicked)

        dialog._stack = QStackedWidget()
        dialog._stack.addWidget(dialog._file_tree)
        dialog._stack.addWidget(dialog._thumb_list)
        splitter.addWidget(dialog._stack)
        splitter.setSizes([160, 690])
        root.addWidget(splitter, 1)

        # Bottom area: search + filter + buttons
        bottom = QHBoxLayout()
        bottom.setContentsMargins(12, 8, 12, 10)
        bottom.setSpacing(8)
        dialog._name_filter = QLineEdit()
        dialog._name_filter.setPlaceholderText(tr('search_files'))
        dialog._name_filter.textChanged.connect(lambda: _refresh(dialog))
        bottom.addWidget(dialog._name_filter, 1)
        dialog._filter_combo = QComboBox()
        dialog._filter_combo.addItems([
            tr('all_media'), tr('video_files'), tr('image_files'),
            tr('audio_files'), tr('playlist')
        ])
        dialog._filter_combo.setMinimumWidth(200)
        dialog._filter_combo.currentIndexChanged.connect(lambda: _refresh(dialog))
        bottom.addWidget(dialog._filter_combo)

        for text, handler, w, tip in [
            (tr('open'), _on_open, 90, tr('open')),
            (tr('add_folder'), _on_add_folder, 110, tr('add_folder')),
            (tr('cancel'), dialog.reject, 90, tr('cancel')),
        ]:
            btn = QPushButton(text)
            btn.setFixedWidth(w)
            btn.setToolTip(tip)
            btn.clicked.connect(handler)
            bottom.addWidget(btn)
        root.addLayout(bottom)

        _apply_view_visibility(dialog)
        _navigate(dialog, dialog._current_path)
        dialog.resize(850, 500)
        dialog.show()

        self._open_media_dialog = dialog
        dialog.finished.connect(self._on_open_media_finished)

    def _on_open_media_finished(self, result):
        dialog = self._open_media_dialog
        if result and hasattr(dialog, 'selected_files') and dialog.selected_files:
            self._process_selected_files(dialog.selected_files)

    def _process_selected_files(self, selected):
        video_exts = ('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.m4v', '.webm', '.flv', '.mpg', '.mpeg', '.ogv')
        image_exts = ('.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff')
        audio_exts = ('.mp3', '.wav', '.aac', '.flac', '.m4a', '.ogg', '.wma')
        playlist_exts = ('.json', '.bpl')
        all_exts = video_exts + image_exts + audio_exts + playlist_exts

        files_to_add = []
        playlist_files = []
        for path in selected:
            if os.path.isdir(path):
                for f in sorted(os.listdir(path)):
                    if f.lower().endswith(all_exts):
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
        logger.info(f"load_video started for: {filePath}")
        was_playing = getattr(self, 'is_playing', False)
        self.stop_playback()
        self.was_playing_before_cache_miss = was_playing
        self.frame_accumulator = 0.0
        self.last_advance_ms = 0
        self.loop_count = 0

        logger.info("Setting mediaPlayer source to empty and cleaning up cache/markers")
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
            logger.info(f"File recognized as image: {is_image}")

            embedded_offset = None
            if is_image and filePath.lower().endswith(('.jpg', '.jpeg')):
                logger.info("Checking for embedded video in JPEG (motion photo)...")
                embedded_offset = get_embedded_video_offset(filePath)

            if embedded_offset is not None:
                self.is_motion_photo = True
                self.motion_photo_original_path = filePath
                if not self.current_temp_dir:
                    import tempfile
                    self.current_temp_dir = tempfile.mkdtemp(prefix="boomerang_frames_")
                    mark_temp_dir_owner(self.current_temp_dir)
                
                temp_video_path = os.path.join(self.current_temp_dir, "extracted_video.mp4")
                try:
                    logger.info(f"Extracting motion photo video data starting at offset {embedded_offset}")
                    with open(filePath, 'rb') as f:
                        f.seek(embedded_offset)
                        video_data = f.read()
                    with open(temp_video_path, 'wb') as f:
                        f.write(video_data)
                    self.currentVideoPath = temp_video_path
                    is_image = False
                    logger.info(f"Successfully extracted motion photo video to {temp_video_path}")
                except Exception as ex:
                    logger.exception(f"Error extracting motion photo video")

            if is_image:
                logger.info("Processing as static image...")
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
                logger.info("Extracting video metadata using ffprobe...")
                fps, duration_ms, total_frames = self.get_video_info(self.currentVideoPath)
                if self.is_motion_photo:
                    total_frames += 1

                if fps > 0:
                    self.fps = fps
                    logger.info(f"ffprobe detected FPS: {self.fps}")

                if self.is_motion_photo:
                    self.cached_frame_dict = {0: filePath}
                else:
                    self.cached_frame_dict = {}

                self.current_cache_index = 0

                logger.info(f"Setting QMediaPlayer source to: {self.currentVideoPath}")
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

            logger.info("Loading saved markers for file...")
            self.load_markers_for_current()

            if not is_image:
                if hasattr(self, 'auto_load_subtitles_for_video'):
                    logger.info("Checking for subtitles...")
                    self.auto_load_subtitles_for_video(filePath)

            if not is_image:
                if self.is_audio_only:
                    logger.info("Generating placeholder for audio file...")
                    self.generate_audio_placeholder()
                    self.update_pixmap_from_cache()
                    self.apply_transformations(fit=True)
                else:
                    logger.info("Initializing cache and starting full video frame extraction...")
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
            logger.info(f"load_video completed successfully for: {filePath}")

        except Exception as e:
            logger.exception(f"Error opening file: {filePath}")
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
        logger.info(f"get_video_info started for: {file_path}")
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
            
            logger.info(f"[get_video_info] {os.path.basename(file_path)}: codec={codec}, is_audio_only={self.is_audio_only}, fps={fps}, duration={duration}s, nb_frames={nb_frames}")
            return fps, duration * 1000, nb_frames
        except Exception as e:
            logger.error(f"ffprobe error: {e}", exc_info=True)
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
