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
            valid_exts = ('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.m4v', '.webm', '.flv', '.mpg', '.mpeg', '.ogv',
                          '.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff')
            valid_files = [f for f in files if f.lower().endswith(valid_exts)]
            if valid_files:
                self.add_files_to_playlist(valid_files)
                
                if not self.currentFilePath:
                    
                    self.load_video(valid_files[0])

    # ------------------------------------------------------------------ #
    # Adding files                                                         #
    # ------------------------------------------------------------------ #

    def add_files_to_playlist(self, file_paths, cached_thumbnails=None):
        
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
                
                # Check for cached thumbnail
                has_cached_thumb = False
                pixmap = None
                if cached_thumbnails and filePath in cached_thumbnails:
                    thumb_data = cached_thumbnails[filePath]
                    if isinstance(thumb_data, str) and thumb_data:
                        try:
                            from PyQt6.QtCore import QByteArray
                            from PyQt6.QtGui import QImage
                            ba = QByteArray.fromBase64(thumb_data.encode('utf-8'))
                            img = QImage.fromData(ba)
                            if not img.isNull():
                                pixmap = QPixmap.fromImage(img)
                                has_cached_thumb = True
                        except Exception as e:
                            print(f"Error decoding cached thumbnail: {e}")
                
                if show_thumbs and not show_names:
                    item.setSizeHint(thumb_size)
                    item.setText("")
                    if has_cached_thumb:
                        item.setIcon(QIcon(pixmap))
                    else:
                        placeholder = QPixmap(thumb_size)
                        placeholder.fill(QColor(60, 60, 60))
                        item.setIcon(QIcon(placeholder))
                elif show_thumbs and show_names:
                    item.setSizeHint(item_size)
                    item.setText(baseName)
                    if has_cached_thumb:
                        item.setIcon(QIcon(pixmap))
                    else:
                        placeholder = QPixmap(thumb_size)
                        placeholder.fill(QColor(60, 60, 60))
                        item.setIcon(QIcon(placeholder))
                else:
                    item.setSizeHint(QSize(0, 28))
                    item.setText(baseName)
                    item.setIcon(QIcon())
                
                
                self.playlistList.addItem(item)
                
                if show_thumbs and not has_cached_thumb:
                    
                    if filePath not in self.thumb_queue:
                        
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
            if hasattr(self, 'audioContainer'):
                self.audioContainer.hide()
        
        self.playlistContainer.setVisible(not is_visible)
        if hasattr(self, 'update_sidebar_fullscreen_state'):
            self.update_sidebar_fullscreen_state()

        if not is_visible and not getattr(self, 'is_full_screen', False):
            sizes = self.mainSplitter.sizes()
            # Under new layout: index 5 is playlistContainer
            if len(sizes) > 5 and sizes[5] < 250:
                sizes[5] = 250
                self.mainSplitter.setSizes(sizes)
