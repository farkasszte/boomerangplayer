"""
Media file picker dialog — custom replacement for QFileDialog to avoid DWM
rendering corruption in fullscreen.
"""

import os
import re
import sys
from PyQt6.QtCore import (Qt, QDir, QStorageInfo, QStandardPaths, QSize,
                           QObject, pyqtSignal as _Signal)
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
                              QListWidgetItem, QPushButton, QComboBox, QLineEdit,
                              QAbstractItemView, QTreeWidget, QTreeWidgetItem,
                              QSplitter, QHeaderView, QStackedWidget,
                              QApplication, QStyle)
from PyQt6.QtGui import QIcon, QColor
from qfluentwidgets import FluentIcon, ToolButton
from styles import COMPACT_BTN_STYLE
from translations import tr

# ── Extension constants ──────────────────────────────────────────────────────
VIDEO_EXTS = ('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.m4v', '.webm', '.flv',
              '.mpg', '.mpeg', '.ogv')
IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff')
AUDIO_EXTS = ('.mp3', '.wav', '.aac', '.flac', '.m4a', '.ogg', '.wma')
PLAYLIST_EXTS = ('.json', '.bpl')
ALL_EXTS = VIDEO_EXTS + IMAGE_EXTS + AUDIO_EXTS + PLAYLIST_EXTS
FILTER_MAP = {0: ALL_EXTS, 1: VIDEO_EXTS, 2: IMAGE_EXTS, 3: AUDIO_EXTS, 4: PLAYLIST_EXTS}

# ── Role constants ───────────────────────────────────────────────────────────
_DIR_ROLE = Qt.ItemDataRole.UserRole + 1
_SIZE_ROLE = Qt.ItemDataRole.UserRole + 2
_DATE_ROLE = Qt.ItemDataRole.UserRole + 3
_TYPE_ROLE = Qt.ItemDataRole.UserRole + 4


# ── Pure helpers ─────────────────────────────────────────────────────────────

def _natural_key(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', s)]


def _format_size(size):
    if size < 1024:
        return f"{size} B"
    elif size < 1048576:
        return f"{size / 1024:.0f} KB"
    elif size < 1073741824:
        return f"{size / 1048576:.1f} MB"
    else:
        return f"{size / 1073741824:.2f} GB"


def _format_date(dt):
    return dt.toString("dd/MM/yyyy HH:mm") if dt.isValid() else ""


def _item_path(item):
    try:
        return item.data(0, Qt.ItemDataRole.UserRole)
    except TypeError:
        return item.data(Qt.ItemDataRole.UserRole)


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
    od = None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\OneDrive") as k:
            od = winreg.QueryValueEx(k, "UserFolder")[0]
    except Exception:
        try:
            od = os.path.expandvars(r"%UserProfile%\OneDrive")
        except Exception:
            od = None
    if od and os.path.isdir(od):
        folders.append(("OneDrive", od))
    return folders


# ── Helper classes ───────────────────────────────────────────────────────────

class _ClickableHeader(QHeaderView):
    sectionClicked = _Signal(int)

    def mousePressEvent(self, e):
        idx = self.logicalIndexAt(e.pos())
        if idx >= 0:
            self.sectionClicked.emit(idx)
        super().mousePressEvent(e)


class _SortTreeItem(QTreeWidgetItem):
    def __lt__(self, other):
        tw = self.treeWidget()
        col = tw.sortColumn() if tw is not None else 0
        self_dir = bool(self.data(0, _DIR_ROLE))
        other_dir = bool(other.data(0, _DIR_ROLE))
        if self_dir != other_dir:
            return self_dir and not other_dir
        if col == 1:
            return (self.data(0, _SIZE_ROLE) or 0) < (other.data(0, _SIZE_ROLE) or 0)
        if col == 3:
            a = self.data(0, _DATE_ROLE)
            b = other.data(0, _DATE_ROLE)
            a = a.toMSecsSinceEpoch() if a is not None else 0
            b = b.toMSecsSinceEpoch() if b is not None else 0
            return a < b
        if col == 2:
            return (self.data(0, _TYPE_ROLE) or '') < (other.data(0, _TYPE_ROLE) or '')
        return _natural_key(self.text(0)) < _natural_key(other.text(0))


class _ThumbResizeFilter(QObject):
    def __init__(self, ensure_fn, parent=None):
        super().__init__(parent)
        self._ensure_fn = ensure_fn
        self._dlg_ref = None

    def set_dialog(self, dlg):
        self._dlg_ref = dlg

    def eventFilter(self, obj, event):
        if event.type() == event.Type.Resize and self._dlg_ref is not None:
            self._ensure_fn()
        return super().eventFilter(obj, event)



# ── Main dialog class ────────────────────────────────────────────────────────

class MediaFileDialog(QDialog):
    """Custom file picker with drive sidebar, tree/thumbnail views, and filter."""

    def __init__(self, parent, config, save_mode=False):
        super().__init__(parent)
        self._config = config
        self._save_mode = save_mode
        self.selected_files = []
        self._setup_ui()

    # ── Public ────────────────────────────────────────────────────────────────

    def selected_paths(self):
        if self._view_mode == 'thumb':
            items = self._thumb_list.selectedItems()
        else:
            items = self._file_tree.selectedItems()
        return [_item_path(item) for item in items]

    # ── UI setup ──────────────────────────────────────────────────────────────

    def _setup_ui(self):
        inverse_text = self._config.get('inverse_text', False)
        accent = self._config.get('accent_color', '#00f2ff')
        bg = self._config.get('bg_color', '#202020')
        fg = "#1c1c1c" if inverse_text else "#ffffff"
        wbg = "#ffffff" if inverse_text else "#1a1a1a"
        bdr = "rgba(0,0,0,0.15)" if inverse_text else "rgba(255,255,255,0.1)"
        hov = "rgba(0,0,0,0.08)" if inverse_text else "rgba(255,255,255,0.1)"
        hdr = "#eaeaea" if inverse_text else "#252525"

        if self._save_mode:
            self.setWindowTitle(tr('save_project_title'))
            self.setModal(True)
        else:
            self.setWindowTitle(tr('add_files_title'))
            self.setModal(False)
        self.setMinimumSize(650, 400)
        self.setStyleSheet(f"""
            QDialog, QLabel {{
                background-color: {bg}; color: {fg}; font-size: 13px;
            }}
            QListWidget {{
                background-color: {wbg}; color: {fg};
                border: 1px solid {bdr}; border-radius: 4px; outline: none;
            }}
            QListWidget::item {{ padding: 4px 8px; border: none; outline: none; }}
            QListWidget::item:selected {{ background-color: {accent}; color: #000; }}
            QListWidget::item:hover {{ background-color: {hov}; }}
            QTreeWidget {{
                background-color: {wbg}; color: {fg};
                border: 1px solid {bdr}; border-radius: 4px; outline: none;
                font-size: 13px;
            }}
            QTreeWidget::item {{ padding: 2px 4px; border: none; outline: none; }}
            QTreeWidget::item:selected {{ background-color: {accent}; color: #000; }}
            QTreeWidget::item:hover {{ background-color: {hov}; }}
            QHeaderView::section {{
                background-color: {hdr}; color: {fg};
                border: none; padding: 4px 8px; font-size: 12px; font-weight: bold;
            }}
            QLineEdit {{
                border: 1px solid {bdr}; border-radius: 4px;
                padding: 5px; background: {wbg}; color: {fg};
            }}
            QComboBox {{
                border: 1px solid {bdr}; border-radius: 4px;
                padding: 6px 8px; background: {wbg}; color: {fg};
            }}
            QComboBox::drop-down {{ border: none; width: 20px; }}
            QComboBox::down-arrow {{ border: none; }}
            QComboBox QAbstractItemView {{
                background: {wbg}; color: {fg};
                border: 1px solid {bdr}; outline: none;
            }}
            QComboBox QAbstractItemView::item {{ padding: 4px 8px; min-height: 24px; }}
            QComboBox QAbstractItemView::item:selected {{ background: {accent}; color: #000; }}
            QComboBox QAbstractItemView::item:hover {{ background: {hov}; }}
            QPushButton {{
                background: {wbg}; border: 1px solid {bdr};
                border-radius: 4px; padding: 6px 12px; min-width: 75px;
                font-weight: 500; color: {fg};
            }}
            QPushButton:hover {{ background-color: {hov}; }}
            QSplitter::handle {{ background: {bdr}; width: 1px; }}
        """)

        self._apply_dwm(bg, fg)
        self.setWindowOpacity(self._config.get('panel_opacity', 100) / 100.0)

        # State
        default_folder = self._config.get('default_folder', '')
        self._current_path = (default_folder if default_folder
                              and os.path.isdir(default_folder)
                              else QDir.rootPath())
        self._history = []
        self._history_idx = -1
        self._view_mode = "detail"
        self._sort_column = 0
        self._sort_order = 'asc'
        self._entries = []
        self._sorted_entries = []
        self._thumb_threads = []
        self._thumb_items_by_path = {}
        self._thumb_pending = set()
        self._thumb_done = set()

        self._cfg = {
            'accent': accent, 'fg': fg, 'bg': bg, 'wbg': wbg,
            'bdr': bdr, 'hov': hov, 'hdr': hdr,
        }

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addLayout(self._build_topbar())
        root.addWidget(self._build_main_area(), 1)
        root.addLayout(self._build_bottombar())

        self._apply_view_visibility()
        self._navigate(self._current_path)
        self.resize(850, 500)

    def _apply_dwm(self, bg, fg):
        if sys.platform != 'win32':
            return
        try:
            import ctypes
            hwnd = int(self.winId())

            def _ref(c):
                return c.red() | (c.green() << 8) | (c.blue() << 16)

            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 35, ctypes.byref(ctypes.c_int(_ref(QColor(bg)))), 4)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 36, ctypes.byref(ctypes.c_int(_ref(QColor(fg)))), 4)
        except Exception:
            pass

    # ── Top bar ───────────────────────────────────────────────────────────────

    def _build_topbar(self):
        c = self._cfg
        lay = QHBoxLayout()
        lay.setContentsMargins(12, 10, 12, 6)
        lay.setSpacing(8)

        self._path_bar = QLineEdit()
        self._path_bar.returnPressed.connect(
            lambda: self._navigate(self._path_bar.text()))
        self._path_bar.setMinimumWidth(200)
        lay.addWidget(self._path_bar, 1)

        # Style definition for round edge buttons
        inverse_text = self._config.get('inverse_text', False)
        bg_translucent = "rgba(0, 0, 0, 0.04)" if inverse_text else "rgba(255, 255, 255, 0.05)"
        bg_pressed = "rgba(0, 0, 0, 0.02)" if inverse_text else "rgba(255, 255, 255, 0.03)"
        
        def hex_to_rgb(hex_str):
            hex_str = hex_str.lstrip('#')
            return ",".join([str(int(hex_str[i:i+2], 16)) for i in (0, 2, 4)])
            
        btn_style = f"""
            ToolButton {{
                border: 1px solid {c['bdr']};
                border-radius: 4px;
                background: {bg_translucent};
                color: {c['fg']};
                min-width: 32px;
                min-height: 32px;
            }}
            ToolButton:hover {{
                background: {c['hov']};
            }}
            ToolButton:pressed {{
                background: {bg_pressed};
            }}
            ToolButton:checked {{
                background: rgba({hex_to_rgb(c['accent'])}, 0.15);
                border: 1px solid {c['accent']};
                color: {c['accent']};
            }}
        """

        for icon, handler, tip in [
            (FluentIcon.LEFT_ARROW, self._go_back, tr('go_back')),
            (FluentIcon.RIGHT_ARROW, self._go_forward, tr('go_forward')),
            (FluentIcon.UP, lambda: self._navigate(
                os.path.dirname(self._current_path)), tr('go_up')),
            (FluentIcon.HOME, lambda: self._navigate(
                self._drive_root(self._current_path)), tr('go_home')),
        ]:
            btn = ToolButton(icon)
            btn.setFixedSize(32, 32)
            btn.setToolTip(tip)
            btn.setStyleSheet(btn_style)
            btn.clicked.connect(handler)
            lay.addWidget(btn)

        lock_btn = ToolButton(FluentIcon.FOLDER)
        lock_btn.setFixedSize(32, 32)
        lock_btn.setToolTip(tr('set_default_folder'))
        lock_btn.setStyleSheet(btn_style)
        lock_btn.clicked.connect(self._set_default)
        lay.addWidget(lock_btn)

        icons = {'detail': FluentIcon.DOCUMENT,
                 'list': FluentIcon.MENU,
                 'thumb': FluentIcon.TILES}
        self._view_btns = {}
        for mode in ['detail', 'list', 'thumb']:
            btn = ToolButton(icons[mode])
            btn.setFixedSize(32, 32)
            btn.setCheckable(True)
            btn.setToolTip(tr(f'{mode}_view'))
            btn.setStyleSheet(btn_style)
            btn.clicked.connect(lambda _=None, m=mode: self._set_view(m))
            self._view_btns[mode] = btn
            lay.addWidget(btn)

        lay.addStretch()
        return lay

    # ── Main area ─────────────────────────────────────────────────────────────

    def _build_main_area(self):
        c = self._cfg
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # Drive sidebar
        self._drive_list = QListWidget()
        self._drive_list.setFixedWidth(160)
        for label, p in _get_special_folders():
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, p)
            self._drive_list.addItem(item)
        sep = QListWidgetItem("—")
        sep.setFlags(Qt.ItemFlag.NoItemFlags)
        self._drive_list.addItem(sep)
        for drive in QDir.drives():
            d_path = drive.path()
            try:
                si = QStorageInfo(d_path)
                vol = si.displayName() if si.isValid() and si.name() else d_path
            except Exception:
                vol = d_path
            item = QListWidgetItem(f"{vol} ({d_path})")
            item.setData(Qt.ItemDataRole.UserRole, d_path)
            self._drive_list.addItem(item)
        self._drive_list.currentRowChanged.connect(self._on_drive_changed)
        splitter.addWidget(self._drive_list)

        # File tree
        self._file_tree = QTreeWidget()
        self._file_tree.setHeaderLabels([
            tr('name') + ' ▲', tr('size'), tr('type'), tr('date_modified')])
        self._file_tree.setRootIsDecorated(False)
        self._file_tree.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        hdr = _ClickableHeader(Qt.Orientation.Horizontal)
        self._file_tree.setHeader(hdr)
        hdr.setSectionsClickable(True)
        hdr.sectionClicked.connect(self._on_header_clicked)
        hdr.resizeSection(0, 350)
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)

        # Thumbnail list
        self._thumb_list = QListWidget()
        self._thumb_list.setViewMode(QListWidget.ViewMode.IconMode)
        self._thumb_list.setIconSize(QSize(120, 120))
        self._thumb_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._thumb_list.setSpacing(10)
        self._thumb_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        self._thumb_list.hide()
        self._thumb_list.verticalScrollBar().valueChanged.connect(
            lambda _: self._ensure_visible_thumbs())
        self._thumb_resize_filter = _ThumbResizeFilter(self._ensure_visible_thumbs)
        self._thumb_resize_filter.set_dialog(self)
        self._thumb_list.installEventFilter(self._thumb_resize_filter)

        try:
            style = QApplication.instance().style()
            self._folder_icon = style.standardIcon(
                QStyle.StandardPixmap.SP_DirOpenIcon)
            self._file_icon = style.standardIcon(
                QStyle.StandardPixmap.SP_FileIcon)
        except Exception:
            self._folder_icon = QIcon()
            self._file_icon = QIcon()

        self._file_tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._thumb_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._file_tree.itemClicked.connect(self._on_item_clicked)
        self._thumb_list.itemClicked.connect(self._on_item_clicked)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._file_tree)
        self._stack.addWidget(self._thumb_list)
        splitter.addWidget(self._stack)
        splitter.setSizes([160, 690])
        return splitter

    # ── Bottom bar ────────────────────────────────────────────────────────────

    def _build_bottombar(self):
        lay = QHBoxLayout()
        lay.setContentsMargins(12, 8, 12, 10)
        lay.setSpacing(8)

        self._name_filter = QLineEdit()
        self._name_filter.setPlaceholderText(tr('search_files') if not self._save_mode else tr('file_name'))
        self._name_filter.setMinimumWidth(200)
        if not self._save_mode:
            self._name_filter.textChanged.connect(lambda: self._refresh())
        lay.addWidget(self._name_filter)

        self._filter_combo = QComboBox()
        if self._save_mode:
            self._filter_combo.addItems([
                f"{tr('bpl_files')} (*.bpl)", f"{tr('json_files')} (*.json)"
            ])
        else:
            self._filter_combo.addItems([
                tr('all_media'), tr('video_files'), tr('image_files'),
                tr('audio_files'), tr('playlist')])
        self._filter_combo.setMinimumWidth(100)
        self._filter_combo.currentIndexChanged.connect(lambda: self._refresh())
        lay.addWidget(self._filter_combo)

        if self._save_mode:
            buttons = [
                (tr('save'), self._on_save_clicked, 120, tr('save')),
                (tr('cancel'), self.reject, 120, tr('cancel')),
            ]
        else:
            buttons = [
                (tr('open'), self._on_open, 120, tr('open')),
                (tr('add_folder'), self._on_add_folder, 120, tr('add_folder')),
                (tr('cancel'), self.reject, 120, tr('cancel')),
            ]

        for text, handler, w, tip in buttons:
            btn = QPushButton(text)
            btn.setFixedWidth(w)
            btn.setToolTip(tip)
            btn.clicked.connect(handler)
            lay.addWidget(btn)
        return lay

    # ── Navigation ────────────────────────────────────────────────────────────

    @staticmethod
    def _drive_root(path):
        if len(path) >= 2 and path[1] == ':':
            return path[:2].upper() + "\\"
        return QDir.rootPath()

    def _navigate(self, path):
        if not path or not os.path.isdir(path):
            return
        if self._current_path != path:
            if self._history_idx < len(self._history) - 1:
                self._history = self._history[:self._history_idx + 1]
            self._history.append(self._current_path)
            self._history_idx = len(self._history) - 1
        self._current_path = path
        self._refresh()

    def _go_back(self):
        if self._history_idx > 0:
            self._history_idx -= 1
            self._current_path = self._history[self._history_idx]
            self._refresh()

    def _go_forward(self):
        if self._history_idx < len(self._history) - 1:
            self._history_idx += 1
            self._current_path = self._history[self._history_idx]
            self._refresh()

    # ── Refresh / render ──────────────────────────────────────────────────────

    def _refresh(self):
        self._path_bar.setText(self._current_path)
        self._highlight_drive()
        if self._save_mode:
            exts = ('.bpl',) if self._filter_combo.currentIndex() == 0 else ('.json',)
            nf = ""
        else:
            exts = FILTER_MAP.get(self._filter_combo.currentIndex(), ALL_EXTS)
            nf = self._name_filter.text().strip().lower()
        d = QDir(self._current_path)
        d.setFilter(QDir.Filter.Dirs | QDir.Filter.Files
                    | QDir.Filter.NoDotAndDotDot)
        raw = []
        for info in d.entryInfoList():
            name = info.fileName()
            is_dir = info.isDir()
            if not is_dir and not name.lower().endswith(exts):
                continue
            if nf and name.lower().find(nf) == -1:
                continue
            raw.append({
                'name': name, 'path': info.absoluteFilePath(),
                'is_dir': is_dir, 'size': info.size(),
                'date': info.lastModified(), 'suffix': info.suffix(),
            })
        self._entries = raw
        self._apply_sort()
        self._render_active()

    def _highlight_drive(self):
        path = self._current_path.lower()
        best_idx, best_len = None, -1
        for i in range(self._drive_list.count()):
            d = self._drive_list.item(i).data(Qt.ItemDataRole.UserRole)
            if not d:
                continue
            d = d.lower()
            if path.startswith(d) and len(d) > best_len:
                best_idx, best_len = i, len(d)
        if best_idx is not None:
            self._drive_list.blockSignals(True)
            self._drive_list.setCurrentRow(best_idx)
            self._drive_list.blockSignals(False)

    def _apply_sort(self):
        col, rev = self._sort_column, self._sort_order == 'desc'

        def key(e):
            if col == 1:
                return e['size']
            if col == 3:
                return e['date'].toMSecsSinceEpoch()
            if col == 2:
                return e['suffix'].lower()
            return _natural_key(e['name'])

        dirs = [e for e in self._entries if e['is_dir']]
        files = [e for e in self._entries if not e['is_dir']]
        dirs.sort(key=key, reverse=rev)
        files.sort(key=key, reverse=rev)
        self._sorted_entries = dirs + files

    def _render_active(self):
        if self._view_mode == 'thumb':
            self._render_thumb()
        else:
            self._render_tree(self._view_mode == 'detail')

    def _render_tree(self, detail):
        accent = self._cfg['accent']
        self._file_tree.clear()
        for e in self._sorted_entries:
            tp = ("File Folder" if e['is_dir']
                  else (e['suffix'].upper() + " File" if e['suffix'] else "File"))
            item = _SortTreeItem()
            item.setData(0, Qt.ItemDataRole.UserRole, e['path'])
            item.setData(0, _DIR_ROLE, e['is_dir'])
            item.setData(0, _SIZE_ROLE, e['size'])
            item.setData(0, _DATE_ROLE, e['date'])
            item.setData(0, _TYPE_ROLE, tp)
            item.setText(0, e['name'])
            if e['is_dir']:
                item.setForeground(0, QColor(accent))
                if detail:
                    item.setText(1, "—")
                    item.setText(2, tp)
                    item.setText(3, _format_date(e['date']))
            else:
                if detail:
                    item.setText(1, _format_size(e['size']))
                    item.setText(2, tp)
                    item.setText(3, _format_date(e['date']))
            self._file_tree.addTopLevelItem(item)

    def _render_thumb(self):
        from workers.threads import ThumbnailThread
        for t in self._thumb_threads:
            try:
                t.cancel()
            except Exception:
                pass
        self._thumb_threads = []
        self._thumb_list.clear()
        self._thumb_items_by_path = {}
        self._thumb_pending = set()
        self._thumb_done = set()
        for e in self._sorted_entries:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, e['path'])
            item.setText(e['name'])
            if e['is_dir']:
                item.setIcon(self._folder_icon)
                self._thumb_done.add(e['path'])
            else:
                item.setIcon(self._file_icon)
            self._thumb_items_by_path[e['path']] = item
            self._thumb_list.addItem(item)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(30, self._ensure_visible_thumbs)

    def _ensure_visible_thumbs(self):
        if self._view_mode != 'thumb':
            return
        from workers.threads import ThumbnailThread
        vp = self._thumb_list.viewport()
        rect = vp.rect()
        for i in range(self._thumb_list.count()):
            if len(self._thumb_pending) >= 12:
                break
            item = self._thumb_list.item(i)
            path = item.data(Qt.ItemDataRole.UserRole)
            if path in self._thumb_done or path in self._thumb_pending:
                continue
            r = self._thumb_list.visualItemRect(item)
            if not r.isValid() or not rect.intersects(r):
                continue
            self._thumb_pending.add(path)
            t = ThumbnailThread(path, self)
            t.finished.connect(
                lambda px, _it=item, _p=path: self._on_thumb(_it, _p, px))
            self._thumb_threads.append(t)
            t.start()

    def _on_thumb(self, item, path, pixmap):
        self._thumb_pending.discard(path)
        self._thumb_done.add(path)
        if pixmap is not None and not pixmap.isNull():
            item.setIcon(QIcon(pixmap))
        self._ensure_visible_thumbs()

    # ── Event handlers ────────────────────────────────────────────────────────

    def _on_header_clicked(self, idx):
        if self._sort_column == idx:
            self._sort_order = ('desc' if self._sort_order == 'asc'
                                else 'asc')
        else:
            self._sort_column = idx
            self._sort_order = 'asc'
        self._apply_sort()
        self._render_tree(self._view_mode == 'detail')
        labels = []
        bases = [tr('name'), tr('size'), tr('type'), tr('date_modified')]
        for i, base in enumerate(bases):
            if i == self._sort_column:
                arrow = ' ▼' if self._sort_order == 'desc' else ' ▲'
                labels.append(base + arrow)
            else:
                labels.append(base)
        self._file_tree.setHeaderLabels(labels)

    def _on_item_double_clicked(self, item, _col=None):
        p = _item_path(item)
        if os.path.isdir(p):
            self._navigate(p)
        else:
            self.selected_files = [p]
            self.accept()

    def _on_item_clicked(self, item, col=None):
        p = _item_path(item)
        if not os.path.isdir(p):
            self._name_filter.setText(os.path.basename(p))

    def _on_save_clicked(self):
        name = self._name_filter.text().strip()
        if not name:
            return
        if not name.lower().endswith(('.bpl', '.json')):
            if self._filter_combo.currentIndex() == 0:
                name += '.bpl'
            else:
                name += '.json'
        self.selected_files = [os.path.join(self._current_path, name)]
        self.accept()

    def _on_drive_changed(self):
        cur = self._drive_list.currentItem()
        if cur:
            self._navigate(cur.data(Qt.ItemDataRole.UserRole))

    def _on_open(self):
        sel = [p for p in self.selected_paths() if os.path.isfile(p)]
        if sel:
            self.selected_files = sel
            self.accept()

    def _on_add_folder(self):
        exts = FILTER_MAP.get(self._filter_combo.currentIndex(), ALL_EXTS)
        nf = self._name_filter.text().strip().lower()
        files = []
        for f in sorted(os.listdir(self._current_path)):
            if not f.lower().endswith(exts):
                continue
            if nf and f.lower().find(nf) == -1:
                continue
            files.append(os.path.join(self._current_path, f))
        if files:
            self.selected_files = files
            self.accept()

    # ── View mode ─────────────────────────────────────────────────────────────

    def _apply_view_visibility(self):
        is_thumb = self._view_mode == 'thumb'
        self._stack.setCurrentIndex(1 if is_thumb else 0)
        self._file_tree.header().setVisible(self._view_mode == 'detail')
        for mode, btn in self._view_btns.items():
            btn.setChecked(mode == self._view_mode)

    def _set_view(self, mode):
        self._view_mode = mode
        self._apply_view_visibility()
        self._refresh()

    def _set_default(self):
        self._config['default_folder'] = self._current_path
        from qfluentwidgets import InfoBar, InfoBarPosition
        InfoBar.success(
            title='', content=tr('default_folder_set'),
            orient=Qt.Orientation.Horizontal, isClosable=True,
            position=InfoBarPosition.TOP, duration=2000,
            parent=self.parent())
