from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QGridLayout, QMenu, QAbstractItemView,
    QStyledItemDelegate, QStyleOptionViewItem, QStyle
)
from PyQt6.QtGui import QIcon
from qfluentwidgets import CaptionLabel, PushButton
from components import DropListWidget
from styles import MENU_STYLE, _hex_to_rgb
from translations import tr

class PlaylistDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_win = parent

    def paint(self, painter, option, index):
        # 1. Let C++ draw the entire item normally (maintaining perfect bounds, padding, and layout)
        super().paint(painter, option, index)
        
        # 2. Overlay the clean, untinted icon in Normal mode exactly on top of the decoration rect
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        if isinstance(icon, QIcon) and not icon.isNull():
            opts = QStyleOptionViewItem(option)
            self.initStyleOption(opts, index)
            
            style = opts.widget.style() if opts.widget else painter.device()
            rect = style.subElementRect(QStyle.SubElement.SE_ItemViewItemDecoration, opts, opts.widget)
            icon.paint(painter, rect, Qt.AlignmentFlag.AlignCenter, QIcon.Mode.Normal, QIcon.State.Off)
            
            # 3. If selected and thumbnail is on while filename is off, draw a beautiful accent border/frame around the thumbnail
            if self.parent_win and hasattr(self.parent_win, 'config'):
                config = self.parent_win.config
                show_thumbs = config.get('show_thumbnails', True)
                show_names = config.get('show_filenames', True)
                if show_thumbs and not show_names and (option.state & QStyle.StateFlag.State_Selected):
                    accent = config.get('accent_color', '#00f2ff')
                    from PyQt6.QtGui import QPen, QColor
                    painter.save()
                    pen_width = 2
                    pen = QPen(QColor(accent), pen_width)
                    painter.setPen(pen)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    # Using QRectF (floating-point precision) with a symmetrical 0.5px offset on all sides
                    # places the center of our 2px pen exactly where it needs to be to align perfectly
                    # with the thumbnail's boundary, with zero gaps on any side.
                    from PyQt6.QtCore import QRectF
                    border_rect = QRectF(rect).adjusted(0.5, 0.5, -0.5, -0.5)
                    painter.drawRect(border_rect)
                    painter.restore()

class PlaylistSidebarUIMixin:
    def _update_playlist_list_stylesheet(self):
        """Update the playlist list stylesheet using the current accent color."""
        
        accent = self.config.get('accent_color', '#00f2ff')
        
        inverse_text = self.config.get('inverse_text', False)
        fg_color = "#1c1c1c" if inverse_text else "#ffffff"
        self.playlistList.setStyleSheet(
            f"QListWidget {{ border: none; background: transparent; outline: none; color: {fg_color}; }} "
            "QListWidget::item { border: none; outline: none; } "
            "QScrollBar:vertical { width: 0px; } "
            f"QListWidget::item:selected {{ background: rgba({_hex_to_rgb(accent)}, 0.3); border: none; outline: none; }} "
            f"QListWidget::item:selected:focus {{ background: rgba({_hex_to_rgb(accent)}, 0.4); border: none; outline: none; }}"
        )
        
        # Set QListWidget palette Highlight to the accent color so standard selected icon tinting matches the accent color (not green)
        from PyQt6.QtGui import QPalette, QColor
        palette = self.playlistList.palette()
        palette.setColor(QPalette.ColorRole.Highlight, QColor(accent))
        self.playlistList.setPalette(palette)

    def _init_playlist_sidebar(self):
        self.playlistContainer = QFrame()
        self.playlistContainer.setMinimumWidth(250)
        self.playlistContainer.setStyleSheet("background: #202020; border: none;")
        self.playlistLayout = QVBoxLayout(self.playlistContainer)
        self.playlistLayout.setContentsMargins(5, 5, 5, 5)

        self.playlistLabel = CaptionLabel(tr('playlist'))
        self.playlistLabel.setStyleSheet("font-size: 16px; font-weight: bold; color: white; background: transparent;")
        self.playlistLayout.addWidget(self.playlistLabel)

        self.playlistList = DropListWidget()
        self.playlistList.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.playlistList.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.playlistList.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.playlistList.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._update_playlist_list_stylesheet()
        self.playlistList.setItemDelegate(PlaylistDelegate(self))
        # Force a full viewport repaint on selection change to instantly clean up any sub-pixel border trails
        
        self.playlistList.itemSelectionChanged.connect(self.playlistList.viewport().update)
        self.playlistList.setIconSize(QSize(120, 120))
        
        self.playlistList.itemDoubleClicked.connect(self.on_playlist_item_clicked)
        
        self.playlistList.itemRightClicked.connect(self.show_playlist_context_menu)
        
        self.playlistList.filesDropped.connect(self.add_files_to_playlist)
        self.playlistLayout.addWidget(self.playlistList)

        self.thumb_threads = []
        self.thumb_queue = []
        self.MAX_THUMB_THREADS = 2

        self.playlistButtonsGrid = QGridLayout()
        self.playlistButtonsGrid.setSpacing(8)

        self.btn_add = PushButton(tr('add'))
        self.btn_add.setToolTip(tr('tip_add'))
        self.btn_add.clicked.connect(self.open_media)

        self.btn_sort = PushButton(tr('sort'))
        self.btn_sort.setToolTip(tr('tip_sort'))
        self.sortMenu = QMenu(self)
        self.sortMenu.setStyleSheet(MENU_STYLE)
        
        self.sortMenu.addAction(tr('sort_name_asc'),    lambda: self.sort_playlist_by("name_asc"))
        
        self.sortMenu.addAction(tr('sort_name_desc'),   lambda: self.sort_playlist_by("name_desc"))
        
        self.sortMenu.addAction(tr('sort_date_newest'), lambda: self.sort_playlist_by("date_newest"))
        
        self.sortMenu.addAction(tr('sort_date_oldest'), lambda: self.sort_playlist_by("date_oldest"))
        
        self.btn_sort.clicked.connect(self.show_sort_menu)

        self.btn_save = PushButton(tr('save'))
        self.btn_save.setToolTip(tr('tip_save'))
        
        self.btn_save.clicked.connect(self.save_playlist_to_file)

        self.btn_clear = PushButton(tr('clear'))
        self.btn_clear.setToolTip(tr('tip_clear'))
        self.removeMenu = QMenu(self)
        self.removeMenu.setStyleSheet(MENU_STYLE)
        
        self.removeMenu.addAction(tr('remove_selected'), self.remove_from_playlist)
        
        self.removeMenu.addAction(tr('clear_all'),       self.clear_playlist)
        
        self.btn_clear.clicked.connect(self.show_clear_menu)

        self.playlistButtonsGrid.addWidget(self.btn_add,   0, 0)
        self.playlistButtonsGrid.addWidget(self.btn_sort,  0, 1)
        self.playlistButtonsGrid.addWidget(self.btn_save,  1, 0)
        self.playlistButtonsGrid.addWidget(self.btn_clear, 1, 1)
        self.playlistLayout.addLayout(self.playlistButtonsGrid)
        self.playlistLayout.setContentsMargins(10, 10, 4, 10)
        
        self.update_playlist_layout(force_reload_thumbs=self.thumbToggle.isChecked())
