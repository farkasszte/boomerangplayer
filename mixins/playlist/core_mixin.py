import os
from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QColor, QPixmap, QIcon
from PyQt6.QtWidgets import QListWidgetItem
from translations import tr

class PlaylistCoreMixin:
    # ------------------------------------------------------------------ #
    # Drag-and-drop into view                                              #
    # ------------------------------------------------------------------ #

    def handle_view_drop(self, files):
        self.handle_playlist_drop(files, insert_row=None, auto_load_if_empty=True)

    def handle_playlist_drop(self, files, insert_row=None, auto_load_if_empty=False):
        if not files:
            return
        video_exts = ('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.m4v', '.webm', '.flv', '.mpg', '.mpeg', '.ogv')
        image_exts = ('.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff')
        audio_exts = ('.mp3', '.wav', '.aac', '.flac', '.m4a', '.ogg', '.wma')
        playlist_exts = ('.bpl', '.json')
        all_exts = video_exts + image_exts + audio_exts + playlist_exts

        def is_bpl_playlist(filepath):
            if not os.path.isfile(filepath):
                return False
            if filepath.lower().endswith('.bpl'):
                return True
            if filepath.lower().endswith('.json'):
                try:
                    with open(filepath, 'r', encoding='utf-8') as pf:
                        prefix = pf.read(512)
                        return 'boomerangplaylist' in prefix
                except Exception:
                    return False
            return False

        files_to_add = []
        playlist_files = []
        for path in files:
            if not path:
                continue
            if os.path.isdir(path):
                try:
                    for f in sorted(os.listdir(path)):
                        if f.lower().endswith(all_exts):
                            fpath = os.path.join(path, f)
                            if is_bpl_playlist(fpath):
                                playlist_files.append(fpath)
                            elif not f.lower().endswith('.json'):
                                files_to_add.append(fpath)
                except OSError:
                    pass
            elif os.path.isfile(path) and path.lower().endswith(all_exts):
                if is_bpl_playlist(path):
                    playlist_files.append(path)
                elif not path.lower().endswith('.json'):
                    files_to_add.append(path)

        loaded_playlist = False
        if playlist_files and hasattr(self, 'load_playlist_by_path'):
            loaded_playlist = self.load_playlist_by_path(playlist_files[0], silent=True)
            if files_to_add:
                self.add_files_to_playlist(files_to_add, insert_row=insert_row)
        elif files_to_add:
            self.add_files_to_playlist(files_to_add, insert_row=insert_row)

        if auto_load_if_empty and not loaded_playlist and files_to_add and not self.currentFilePath:
            self.load_video(files_to_add[0])

    # ------------------------------------------------------------------ #
    # Adding files                                                         #
    # ------------------------------------------------------------------ #

    def add_files_to_playlist(self, file_paths, cached_thumbnails=None, insert_row=None):
        
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
                
                
                if insert_row is not None and 0 <= insert_row <= self.playlistList.count():
                    self.playlistList.insertItem(insert_row, item)
                    insert_row += 1
                else:
                    self.playlistList.addItem(item)
                
                if show_thumbs and not has_cached_thumb:
                    
                    if filePath not in self.thumb_queue:
                        
                        self.thumb_queue.append(filePath)
                
                existing_paths.add(abs_path.lower())
        
        if show_thumbs:
            
            self._process_thumb_queue()

        if hasattr(self, 'update_playlist_counter'):
            self.update_playlist_counter()
        if hasattr(self, 'refresh_window_frame'):
            self.refresh_window_frame()

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
            idx = self.mainSplitter.indexOf(self.playlistContainer)
            if idx != -1 and len(sizes) > idx and sizes[idx] < 260:
                sizes[idx] = 260
                self.mainSplitter.setSizes(sizes)
