import os
from PyQt6.QtCore import Qt, QSize, QPoint
from PyQt6.QtGui import QColor, QPixmap, QIcon
from PyQt6.QtWidgets import QListView, QMenu
from mixins.threads import ThumbnailThread
from translations import tr

class PlaylistThumbnailMixin:
    def _process_thumb_queue(self):
        """Starts the next thumbnail thread if there's space."""
        # pyrefly: ignore [missing-attribute]
        if not self.thumbToggle.isChecked():
            # pyrefly: ignore [missing-attribute]
            self.thumb_queue.clear()
            return

        # pyrefly: ignore [missing-attribute]
        while len(self.thumb_threads) < self.MAX_THUMB_THREADS and self.thumb_queue:
            # pyrefly: ignore [missing-attribute]
            filePath = self.thumb_queue.pop(0)
            
            # Don't process if already being processed or finished (though queue should handle this)
            # pyrefly: ignore [not-iterable]
            already_running = any(t.filePath == filePath for t in self.thumb_threads)
            if already_running:
                continue

            thread = ThumbnailThread(filePath, self)
            thread.finished.connect(self.on_thumbnail_ready)
            # pyrefly: ignore [missing-attribute]
            self.thumb_threads.append(thread)
            thread.start()

    # ------------------------------------------------------------------ #
    # Thumbnail callbacks                                                  #
    # ------------------------------------------------------------------ #

    def on_thumbnail_ready(self, filePath, pixmap):
        # Cleanup finished thread
        # pyrefly: ignore [missing-attribute]
        sender = self.sender()
        # pyrefly: ignore [missing-attribute]
        if sender in self.thumb_threads:
            # pyrefly: ignore [missing-attribute]
            self.thumb_threads.remove(sender)

        # pyrefly: ignore [missing-attribute]
        if not self.thumbToggle.isChecked():
            self._process_thumb_queue()
            return
            
        # pyrefly: ignore [missing-attribute]
        for i in range(self.playlistList.count()):
            # pyrefly: ignore [missing-attribute]
            item = self.playlistList.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == filePath:
                item.setIcon(QIcon(pixmap))
                break
        
        self._process_thumb_queue()

    def on_thumb_toggle_changed(self, checked):
        if not checked:
            # pyrefly: ignore [missing-attribute]
            if not self.fileNameToggle.isChecked():
                # pyrefly: ignore [missing-attribute]
                self.fileNameToggle.blockSignals(True)
                # pyrefly: ignore [missing-attribute]
                self.fileNameToggle.setChecked(True)
                # pyrefly: ignore [missing-attribute]
                self.fileNameToggle.blockSignals(False)
        self.update_playlist_layout(force_reload_thumbs=checked)

    def on_filename_toggle_changed(self, checked):
        if not checked:
            # pyrefly: ignore [missing-attribute]
            if not self.thumbToggle.isChecked():
                # pyrefly: ignore [missing-attribute]
                self.thumbToggle.blockSignals(True)
                # pyrefly: ignore [missing-attribute]
                self.thumbToggle.setChecked(True)
                # pyrefly: ignore [missing-attribute]
                self.thumbToggle.blockSignals(False)
                self.update_playlist_layout(force_reload_thumbs=True)
                return
        self.update_playlist_layout(force_reload_thumbs=False)

    def on_thumb_size_changed(self, idx):
        # pyrefly: ignore [missing-attribute]
        self.config['thumbnail_size_index'] = idx
        from utils import save_config
        # pyrefly: ignore [missing-attribute]
        save_config(self.config)
        self.update_thumb_size_btn_text()
        self.update_playlist_layout()

    def update_thumb_size_btn_text(self):
        if hasattr(self, 'thumbSizeBtn'):
            # pyrefly: ignore [missing-attribute]
            size_idx = self.config.get('thumbnail_size_index', 1)
            sizes_labels = [tr('size_small'), tr('size_medium'), tr('size_large')]
            current_label = sizes_labels[size_idx] if 0 <= size_idx < len(sizes_labels) else tr('size_medium')
            self.thumbSizeBtn.setText(current_label)

    def show_thumb_size_menu(self):
        # pyrefly: ignore [no-matching-overload]
        menu = QMenu(parent=self)
        menu.setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # pyrefly: ignore [missing-attribute]
        accent = self.config.get('accent_color', '#00f2ff')
        style = getattr(self, '_MENU_POPUP_STYLE', """
            QMenu { background-color: #202020; border: none; padding: 4px 0px; }
            QMenu::item { padding: 8px 25px; color: white; background-color: transparent; }
            QMenu::item:selected { background-color: rgba(255,255,255,0.1); }
            QMenu::item:checked { color: %ACCENT%; font-weight: bold; }
            QMenu::indicator { width: 0px; }
        """).replace('%ACCENT%', accent)
        menu.setStyleSheet(style)

        # pyrefly: ignore [missing-attribute]
        current_idx = self.config.get('thumbnail_size_index', 1)

        sizes = [
            (tr('size_small'), 0),
            (tr('size_medium'), 1),
            (tr('size_large'), 2)
        ]

        for label, idx in sizes:
            action = menu.addAction(label)
            # pyrefly: ignore [missing-attribute]
            action.setCheckable(True)
            # pyrefly: ignore [missing-attribute]
            action.setChecked(current_idx == idx)
            # pyrefly: ignore [missing-attribute]
            action.triggered.connect(lambda checked, i=idx: self.on_thumb_size_changed(i))

        # pyrefly: ignore [missing-attribute]
        pos = self.thumbSizeBtn.mapToGlobal(QPoint(0, self.thumbSizeBtn.height()))
        menu.exec(pos)

    def update_playlist_layout(self, force_reload_thumbs=False):
        # pyrefly: ignore [missing-attribute]
        show_thumbs = self.thumbToggle.isChecked()
        # pyrefly: ignore [missing-attribute]
        show_names = self.fileNameToggle.isChecked()
        
        # pyrefly: ignore [missing-attribute]
        self.config['show_thumbnails'] = show_thumbs
        # pyrefly: ignore [missing-attribute]
        self.config['show_filenames'] = show_names
        from utils import save_config
        # pyrefly: ignore [missing-attribute]
        save_config(self.config)
        
        # pyrefly: ignore [missing-attribute]
        size_idx = self.config.get('thumbnail_size_index', 1)
        sizes = [
            (QSize(80, 80), QSize(80, 90), 8),
            (QSize(120, 120), QSize(120, 130), 10),
            (QSize(160, 160), QSize(160, 170), 12)
        ]
        thumb_size, item_size, spacing = sizes[size_idx] if 0 <= size_idx < len(sizes) else sizes[1]

        if show_thumbs and not show_names:
            # pyrefly: ignore [missing-attribute]
            self.playlistList.setViewMode(QListView.ViewMode.IconMode)
            # pyrefly: ignore [missing-attribute]
            self.playlistList.setResizeMode(QListView.ResizeMode.Adjust)
            # pyrefly: ignore [missing-attribute]
            self.playlistList.setMovement(QListView.Movement.Static)
            # pyrefly: ignore [missing-attribute]
            self.playlistList.setSpacing(spacing)
            # pyrefly: ignore [missing-attribute]
            self.playlistList.setIconSize(thumb_size)
        elif show_thumbs and show_names:
            # pyrefly: ignore [missing-attribute]
            self.playlistList.setViewMode(QListView.ViewMode.ListMode)
            # pyrefly: ignore [missing-attribute]
            self.playlistList.setResizeMode(QListView.ResizeMode.Adjust)
            # pyrefly: ignore [missing-attribute]
            self.playlistList.setMovement(QListView.Movement.Static)
            # pyrefly: ignore [missing-attribute]
            self.playlistList.setSpacing(spacing // 2)
            # pyrefly: ignore [missing-attribute]
            self.playlistList.setIconSize(thumb_size)
        else:
            # pyrefly: ignore [missing-attribute]
            self.playlistList.setViewMode(QListView.ViewMode.ListMode)
            # pyrefly: ignore [missing-attribute]
            self.playlistList.setResizeMode(QListView.ResizeMode.Adjust)
            # pyrefly: ignore [missing-attribute]
            self.playlistList.setMovement(QListView.Movement.Static)
            # pyrefly: ignore [missing-attribute]
            self.playlistList.setSpacing(1)
            # pyrefly: ignore [missing-attribute]
            self.playlistList.setIconSize(QSize(0, 0))

        if not show_thumbs:
            # pyrefly: ignore [missing-attribute]
            self.thumb_queue.clear()
            # pyrefly: ignore [missing-attribute]
            for t in self.thumb_threads:
                t.cancel()
            # pyrefly: ignore [missing-attribute]
            self.thumb_threads.clear()

        # pyrefly: ignore [missing-attribute]
        for i in range(self.playlistList.count()):
            # pyrefly: ignore [missing-attribute]
            item = self.playlistList.item(i)
            filePath = item.data(Qt.ItemDataRole.UserRole)
            baseName = os.path.basename(filePath) if filePath else ""
            
            if show_thumbs and not show_names:
                item.setSizeHint(thumb_size)
                item.setText("")
                if item.icon().isNull():
                    placeholder = QPixmap(thumb_size)
                    placeholder.fill(QColor(60, 60, 60))
                    item.setIcon(QIcon(placeholder))
            elif show_thumbs and show_names:
                item.setSizeHint(item_size)
                item.setText(baseName)
                if item.icon().isNull():
                    placeholder = QPixmap(thumb_size)
                    placeholder.fill(QColor(60, 60, 60))
                    item.setIcon(QIcon(placeholder))
            else:
                item.setSizeHint(QSize(0, 28))
                item.setText(baseName)
                item.setIcon(QIcon())

        if show_thumbs and force_reload_thumbs:
            # pyrefly: ignore [missing-attribute]
            self.thumb_queue.clear()
            # pyrefly: ignore [missing-attribute]
            for i in range(self.playlistList.count()):
                # pyrefly: ignore [missing-attribute]
                item = self.playlistList.item(i)
                filePath = item.data(Qt.ItemDataRole.UserRole)
                placeholder = QPixmap(thumb_size)
                placeholder.fill(QColor(60, 60, 60))
                item.setIcon(QIcon(placeholder))
                # pyrefly: ignore [missing-attribute]
                self.thumb_queue.append(filePath)
            self._process_thumb_queue()
