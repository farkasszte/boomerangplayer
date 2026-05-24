import os
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QPixmap, QIcon
from PyQt6.QtWidgets import QListWidgetItem
from translations import tr

class PlaylistCoreMixin:
    # ------------------------------------------------------------------ #
    # Drag-and-drop into view                                              #
    # ------------------------------------------------------------------ #

    def handle_view_drop(self, files):
        if files:
            valid_exts = ('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.m4v',
                          '.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff')
            valid_files = [f for f in files if f.lower().endswith(valid_exts)]
            if valid_files:
                self.add_files_to_playlist(valid_files)
                if not self.currentFilePath:
                    self.load_video(valid_files[0])

    # ------------------------------------------------------------------ #
    # Adding files                                                         #
    # ------------------------------------------------------------------ #

    def add_files_to_playlist(self, file_paths):
        show_thumbs = self.thumbToggle.isChecked()
        show_names = self.fileNameToggle.isChecked()
        
        size_idx = self.config.get('thumbnail_size_index', 1)
        sizes = [
            (QSize(80, 80), QSize(80, 90)),
            (QSize(120, 120), QSize(120, 130)),
            (QSize(160, 160), QSize(160, 170))
        ]
        thumb_size, item_size = sizes[size_idx] if 0 <= size_idx < len(sizes) else sizes[1]

        # Gather existing absolute paths to prevent duplicate entries
        existing_paths = set()
        for i in range(self.playlistList.count()):
            item = self.playlistList.item(i)
            path = item.data(Qt.ItemDataRole.UserRole)
            if path:
                existing_paths.add(os.path.abspath(path).lower())

        for filePath in file_paths:
            if os.path.isfile(filePath):
                abs_path = os.path.abspath(filePath)
                if abs_path.lower() in existing_paths:
                    continue
                
                baseName = os.path.basename(filePath)
                item = QListWidgetItem(baseName)
                item.setData(Qt.ItemDataRole.UserRole, filePath)
                
                if show_thumbs and not show_names:
                    item.setSizeHint(thumb_size)
                    item.setText("")
                    placeholder = QPixmap(thumb_size)
                    placeholder.fill(QColor(60, 60, 60))
                    item.setIcon(QIcon(placeholder))
                elif show_thumbs and show_names:
                    item.setSizeHint(item_size)
                    item.setText(baseName)
                    placeholder = QPixmap(thumb_size)
                    placeholder.fill(QColor(60, 60, 60))
                    item.setIcon(QIcon(placeholder))
                else:
                    item.setSizeHint(QSize(0, 28))
                    item.setText(baseName)
                    item.setIcon(QIcon())
                
                self.playlistList.addItem(item)
                
                if show_thumbs:
                    self.thumb_queue.append(filePath)
                
                existing_paths.add(abs_path.lower())
        
        if show_thumbs:
            self._process_thumb_queue()

    # ------------------------------------------------------------------ #
    # Item interaction                                                     #
    # ------------------------------------------------------------------ #

    def on_playlist_item_clicked(self, item):
        filePath = item.data(Qt.ItemDataRole.UserRole)
        self.load_video(filePath)

    # ------------------------------------------------------------------ #
    # Panel toggles                                                        #
    # ------------------------------------------------------------------ #

    def toggle_playlist(self):
        is_visible = self.playlistContainer.isVisible()
        if not is_visible:
            self.drawingContainer.hide()
        self.playlistContainer.setVisible(not is_visible)
        if hasattr(self, 'update_sidebar_fullscreen_state'):
            self.update_sidebar_fullscreen_state()

        if not is_visible and not getattr(self, 'is_full_screen', False):
            sizes = self.mainSplitter.sizes()
            if len(sizes) > 3 and sizes[3] < 250:
                sizes[3] = 250
                self.mainSplitter.setSizes(sizes)
