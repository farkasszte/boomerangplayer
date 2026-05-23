"""
PlaylistMixin — playlist sidebar logic, CRUD, thumbnails, file info.
"""

import os
import json
from PyQt6.QtCore import Qt, QPoint, QSize
from PyQt6.QtGui import QColor, QPixmap, QIcon
from PyQt6.QtWidgets import QFileDialog, QListWidgetItem
from qfluentwidgets import MessageBox
from mixins.threads import ThumbnailThread
from styles import MENU_STYLE
from translations import tr
from utils import get_resource_path, VERSION, send_to_recycle_bin
import subprocess


class PlaylistMixin:
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

        for filePath in file_paths:
            if os.path.isfile(filePath):
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
        
        if show_thumbs:
            self._process_thumb_queue()

    def _process_thumb_queue(self):
        """Starts the next thumbnail thread if there's space."""
        if not self.thumbToggle.isChecked():
            self.thumb_queue.clear()
            return

        while len(self.thumb_threads) < self.MAX_THUMB_THREADS and self.thumb_queue:
            filePath = self.thumb_queue.pop(0)
            
            # Don't process if already being processed or finished (though queue should handle this)
            already_running = any(t.filePath == filePath for t in self.thumb_threads)
            if already_running:
                continue

            thread = ThumbnailThread(filePath, self)
            thread.finished.connect(self.on_thumbnail_ready)
            self.thumb_threads.append(thread)
            thread.start()

    # ------------------------------------------------------------------ #
    # Thumbnail callbacks                                                  #
    # ------------------------------------------------------------------ #

    def on_thumbnail_ready(self, filePath, pixmap):
        # Cleanup finished thread
        sender = self.sender()
        if sender in self.thumb_threads:
            self.thumb_threads.remove(sender)

        if not self.thumbToggle.isChecked():
            self._process_thumb_queue()
            return
            
        for i in range(self.playlistList.count()):
            item = self.playlistList.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == filePath:
                item.setIcon(QIcon(pixmap))
                break
        
        self._process_thumb_queue()

    def on_thumb_toggle_changed(self, checked):
        if not checked:
            if not self.fileNameToggle.isChecked():
                self.fileNameToggle.blockSignals(True)
                self.fileNameToggle.setChecked(True)
                self.fileNameToggle.blockSignals(False)
        self.update_playlist_layout(force_reload_thumbs=checked)

    def on_filename_toggle_changed(self, checked):
        if not checked:
            if not self.thumbToggle.isChecked():
                self.thumbToggle.blockSignals(True)
                self.thumbToggle.setChecked(True)
                self.thumbToggle.blockSignals(False)
                self.update_playlist_layout(force_reload_thumbs=True)
                return
        self.update_playlist_layout(force_reload_thumbs=False)

    def on_thumb_size_changed(self, idx):
        self.config['thumbnail_size_index'] = idx
        from utils import save_config
        save_config(self.config)
        self.update_thumb_size_btn_text()
        self.update_playlist_layout()

    def update_thumb_size_btn_text(self):
        if hasattr(self, 'thumbSizeBtn'):
            size_idx = self.config.get('thumbnail_size_index', 1)
            sizes_labels = [tr('size_small'), tr('size_medium'), tr('size_large')]
            current_label = sizes_labels[size_idx] if 0 <= size_idx < len(sizes_labels) else tr('size_medium')
            self.thumbSizeBtn.setText(current_label)

    def show_thumb_size_menu(self):
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtCore import QPoint
        menu = QMenu(parent=self)
        menu.setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        accent = self.config.get('accent_color', '#00f2ff')
        style = getattr(self, '_MENU_POPUP_STYLE', """
            QMenu { background-color: #202020; border: none; padding: 4px 0px; }
            QMenu::item { padding: 8px 25px; color: white; background-color: transparent; }
            QMenu::item:selected { background-color: rgba(255,255,255,0.1); }
            QMenu::item:checked { color: %ACCENT%; font-weight: bold; }
            QMenu::indicator { width: 0px; }
        """).replace('%ACCENT%', accent)
        menu.setStyleSheet(style)

        current_idx = self.config.get('thumbnail_size_index', 1)

        sizes = [
            (tr('size_small'), 0),
            (tr('size_medium'), 1),
            (tr('size_large'), 2)
        ]

        for label, idx in sizes:
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(current_idx == idx)
            action.triggered.connect(lambda checked, i=idx: self.on_thumb_size_changed(i))

        pos = self.thumbSizeBtn.mapToGlobal(QPoint(0, self.thumbSizeBtn.height()))
        menu.exec(pos)

    def update_playlist_layout(self, force_reload_thumbs=False):
        show_thumbs = self.thumbToggle.isChecked()
        show_names = self.fileNameToggle.isChecked()
        
        self.config['show_thumbnails'] = show_thumbs
        self.config['show_filenames'] = show_names
        from utils import save_config
        save_config(self.config)
        
        from PyQt6.QtWidgets import QListView
        
        size_idx = self.config.get('thumbnail_size_index', 1)
        sizes = [
            (QSize(80, 80), QSize(80, 90), 8),
            (QSize(120, 120), QSize(120, 130), 10),
            (QSize(160, 160), QSize(160, 170), 12)
        ]
        thumb_size, item_size, spacing = sizes[size_idx] if 0 <= size_idx < len(sizes) else sizes[1]

        if show_thumbs and not show_names:
            self.playlistList.setViewMode(QListView.ViewMode.IconMode)
            self.playlistList.setResizeMode(QListView.ResizeMode.Adjust)
            self.playlistList.setMovement(QListView.Movement.Static)
            self.playlistList.setSpacing(spacing)
            self.playlistList.setIconSize(thumb_size)
        elif show_thumbs and show_names:
            self.playlistList.setViewMode(QListView.ViewMode.ListMode)
            self.playlistList.setResizeMode(QListView.ResizeMode.Adjust)
            self.playlistList.setMovement(QListView.Movement.Static)
            self.playlistList.setSpacing(spacing // 2)
            self.playlistList.setIconSize(thumb_size)
        else:
            self.playlistList.setViewMode(QListView.ViewMode.ListMode)
            self.playlistList.setResizeMode(QListView.ResizeMode.Adjust)
            self.playlistList.setMovement(QListView.Movement.Static)
            self.playlistList.setSpacing(1)
            self.playlistList.setIconSize(QSize(0, 0))

        if not show_thumbs:
            self.thumb_queue.clear()
            for t in self.thumb_threads:
                t.cancel()
            self.thumb_threads.clear()

        for i in range(self.playlistList.count()):
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
            self.thumb_queue.clear()
            for i in range(self.playlistList.count()):
                item = self.playlistList.item(i)
                filePath = item.data(Qt.ItemDataRole.UserRole)
                placeholder = QPixmap(thumb_size)
                placeholder.fill(QColor(60, 60, 60))
                item.setIcon(QIcon(placeholder))
                self.thumb_queue.append(filePath)
            self._process_thumb_queue()

    # ------------------------------------------------------------------ #
    # Item interaction                                                     #
    # ------------------------------------------------------------------ #

    def on_playlist_item_clicked(self, item):
        filePath = item.data(Qt.ItemDataRole.UserRole)
        self.load_video(filePath)

    # ------------------------------------------------------------------ #
    # Menu popups                                                          #
    # ------------------------------------------------------------------ #

    def show_add_menu(self):
        menu_hint = self.addMenu.sizeHint()
        pos = self.btn_add.mapToGlobal(QPoint(0, -menu_hint.height()))
        self.addMenu.exec(pos)

    def show_sort_menu(self):
        if self.playlistList.count() == 0:
            return
        menu_hint = self.sortMenu.sizeHint()
        pos = self.btn_sort.mapToGlobal(QPoint(0, -menu_hint.height()))
        self.sortMenu.exec(pos)

    def show_clear_menu(self):
        if self.playlistList.count() == 0:
            return
        menu_hint = self.removeMenu.sizeHint()
        pos = self.btn_clear.mapToGlobal(QPoint(0, -menu_hint.height()))
        self.removeMenu.exec(pos)

    def show_remove_menu(self):
        self.show_clear_menu()

    def show_playlist_context_menu(self, item, pos):
        if not item.isSelected():
            self.playlistList.clearSelection()
            item.setSelected(True)
            self.playlistList.setCurrentItem(item)

        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        menu.setStyleSheet(MENU_STYLE)
        menu.addAction(tr('rename'), lambda: self.rename_playlist_item(item))
        menu.addAction(tr('open_in_new_window'), lambda: self.open_in_new_window(item))
        menu.addAction(tr('remove_selected'), self.remove_from_playlist)
        menu.addAction(tr('delete_file'), lambda: self.delete_playlist_item(item))
        menu.exec(pos)

    def open_in_new_window(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path and os.path.exists(path):
            import sys
            try:
                # Launch a new instance of the current script with the file path
                subprocess.Popen([sys.executable, sys.argv[0], path], 
                                 creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            except Exception as e:
                print(f"Error opening in new window: {e}")

    def rename_playlist_item(self, item):
        from PyQt6.QtWidgets import QInputDialog
        old_path = item.data(Qt.ItemDataRole.UserRole)
        if not old_path or not os.path.exists(old_path):
            return
        
        old_full_name = os.path.basename(old_path)
        old_base_name, extension = os.path.splitext(old_full_name)
        
        new_base_name, ok = QInputDialog.getText(self, tr('rename_file_title'), tr('enter_new_name'), text=old_base_name)
        
        if ok and new_base_name and new_base_name != old_base_name:
            new_name = new_base_name + extension
            new_path = os.path.join(os.path.dirname(old_path), new_name)
            try:
                # IMPORTANT: If this is the current file, release the lock!
                is_current = (self.currentFilePath == old_path)
                if is_current:
                    # Clear media player source to release file lock on Windows
                    from PyQt6.QtCore import QUrl
                    self.mediaPlayer.setSource(QUrl())
                    
                    # Also stop extraction if it's running
                    if hasattr(self, 'extraction_thread') and self.extraction_thread and self.extraction_thread.isRunning():
                        self.extraction_thread.cancel()

                    # Stop any thumbnail generation for this file
                    if old_path in self.thumb_queue:
                        self.thumb_queue.remove(old_path)

                    for t in getattr(self, 'thumb_threads', []):
                        if t.filePath == old_path:
                            t.cancel()
                            # It will be removed from self.thumb_threads in on_thumbnail_ready
                            # or we can remove it now if we're sure it's not emitting anymore
                            # but safer to let the callback handle it.
                
                os.rename(old_path, new_path)
                
                # Update item
                item.setText(new_name)
                item.setData(Qt.ItemDataRole.UserRole, new_path)
                
                # Update playlist data
                if old_path in self.playlistData:
                    self.playlistData[new_path] = self.playlistData.pop(old_path)
                
                # Restore current file state if it was the one renamed
                if is_current:
                    self.currentFilePath = new_path
                    self.setWindowTitle(f"Boomerang Player v{VERSION} - {new_name}")
                    from PyQt6.QtCore import QUrl
                    self.mediaPlayer.setSource(QUrl.fromLocalFile(new_path))
                    # Restore position
                    if self.fps > 0:
                        pos = int((self.current_cache_index * 1000) / self.fps)
                        self.mediaPlayer.setPosition(pos)
                    self.mediaPlayer.pause()
                
                # Update cache path if needed
                if getattr(self, 'cached_file_path', None) == old_path:
                    self.cached_file_path = new_path
            except Exception as e:
                # If error occurred, try to restore if it was current
                if is_current and self.currentFilePath == old_path:
                    from PyQt6.QtCore import QUrl
                    self.mediaPlayer.setSource(QUrl.fromLocalFile(old_path))
                
                from qfluentwidgets import InfoBar, InfoBarPosition
                InfoBar.error(
                    title=tr('rename_file_title'),
                    content=f"Error: {e}",
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=5000,
                    parent=self
                )
                print(f"Error renaming file: {e}")

    def delete_playlist_item(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if not path or not os.path.exists(path):
            return

        from qfluentwidgets import MessageBox
        box = MessageBox(
            tr('delete_file_confirm_title'),
            tr('delete_file_confirm_msg').format(os.path.basename(path)),
            self
        )
        box.yesButton.setText(tr('delete'))
        box.cancelButton.setText(tr('cancel'))
        
        if not box.exec():
            return

        try:
            is_current = (self.currentFilePath == path)
            if is_current:
                # 1. Stop playback
                self.stop_playback()
                
                # 2. Clear media player source to release file lock on Windows
                from PyQt6.QtCore import QUrl
                self.mediaPlayer.setSource(QUrl())
                
                # 3. Stop extraction if running
                if hasattr(self, 'extraction_thread') and self.extraction_thread and self.extraction_thread.isRunning():
                    self.extraction_thread.cancel()

                # 4. Stop any thumbnail generation for this file
                if path in self.thumb_queue:
                    self.thumb_queue.remove(path)

                for t in getattr(self, 'thumb_threads', []):
                    if t.filePath == path:
                        t.cancel()
                
                # 5. Cleanup cache
                self.cleanup_cache()
                
                # 6. Reset UI details
                if hasattr(self, 'pixmapItem') and self.pixmapItem:
                    self.pixmapItem.setPixmap(QPixmap())
                self.progressBar.setRange(0, 0)
                self.progressBar.setValue(0)
                self.frameLabel.setText(" [F: 0]")
                self.currentTimeLabel.setText("00:00")
                self.totalTimeLabel.setText("00:00")
                self.currentFilePath = None
                self.setWindowTitle(f"Boomerang Player v{VERSION}")

            success = send_to_recycle_bin(path)
            
            if success:
                # Remove from playlist view
                row = self.playlistList.row(item)
                if row >= 0:
                    self.playlistList.takeItem(row)
                
                # Remove from playlistData (markers)
                if path in self.playlistData:
                    del self.playlistData[path]
                
                # Show success message
                from qfluentwidgets import InfoBar, InfoBarPosition
                InfoBar.success(
                    title=tr('delete_file_confirm_title'),
                    content=tr('delete_success'),
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
            else:
                raise Exception("Failed to move file to Recycle Bin. The file might be in use or access was denied.")

        except Exception as e:
            # If error occurred and it was the current file, restore player source
            if is_current:
                from PyQt6.QtCore import QUrl
                self.mediaPlayer.setSource(QUrl.fromLocalFile(path))
            
            from qfluentwidgets import InfoBar, InfoBarPosition
            InfoBar.error(
                title=tr('delete_file_confirm_title'),
                content=f"Error: {e}",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
            print(f"Error deleting file: {e}")

    # ------------------------------------------------------------------ #
    # Sorting                                                              #
    # ------------------------------------------------------------------ #

    def sort_playlist_by(self, criteria):
        items_info = []
        for i in range(self.playlistList.count()):
            item = self.playlistList.item(i)
            path = item.data(Qt.ItemDataRole.UserRole)
            items_info.append({
                'item': item,
                'name': os.path.basename(path).lower() if path else "",
                'date': os.path.getmtime(path) if os.path.exists(path) else 0
            })

        if criteria == "name_asc":
            items_info.sort(key=lambda x: x['name'])
        elif criteria == "name_desc":
            items_info.sort(key=lambda x: x['name'], reverse=True)
        elif criteria == "date_newest":
            items_info.sort(key=lambda x: x['date'], reverse=True)
        elif criteria == "date_oldest":
            items_info.sort(key=lambda x: x['date'])

        taken_items = [self.playlistList.takeItem(0)
                       for _ in range(self.playlistList.count())]

        for info in items_info:
            self.playlistList.addItem(info['item'])

    # ------------------------------------------------------------------ #
    # Remove / clear                                                       #
    # ------------------------------------------------------------------ #

    def remove_from_playlist(self):
        selected_items = self.playlistList.selectedItems()
        if not selected_items:
            curr = self.playlistList.currentItem()
            if curr:
                selected_items = [curr]

        for item in selected_items:
            path = item.data(Qt.ItemDataRole.UserRole)
            if path in self.playlistData:
                del self.playlistData[path]
            row = self.playlistList.row(item)
            if row >= 0:
                self.playlistList.takeItem(row)

    def clear_playlist(self):
        self.thumb_queue.clear()
        for t in self.thumb_threads:
            t.cancel()
        self.thumb_threads.clear()

        self.playlistList.clear()
        self.playlistData = {}
        self.stop_playback()
        self.cleanup_cache()
        self.currentFilePath = None
        self.setWindowTitle(f"Boomerang Player v{VERSION}")
        if hasattr(self, 'pixmapItem'):
            self.pixmapItem.setPixmap(QPixmap())
        self.progressBar.setRange(0, 0)
        self.progressBar.setValue(0)
        self.frameLabel.setText(" [F: 0]")
        self.currentTimeLabel.setText("00:00")
        self.totalTimeLabel.setText("00:00")

    # ------------------------------------------------------------------ #
    # Playlist file persistence                                            #
    # ------------------------------------------------------------------ #

    def save_playlist_to_file(self):
        fileName, _ = QFileDialog.getSaveFileName(
            self, tr('save_project_title'), "", f"{tr('json_files')} (*.json)"
        )
        if fileName:
            data = {'files': [], 'markers': self.playlistData}
            for i in range(self.playlistList.count()):
                item = self.playlistList.item(i)
                data['files'].append(item.data(Qt.ItemDataRole.UserRole))
            with open(fileName, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)

    def load_playlist_by_path(self, fileName):
        if fileName and os.path.exists(fileName):
            try:
                with open(fileName, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                self.playlistList.clear()
                self.playlistData = data.get('markers', {})

                self.add_files_to_playlist(data.get('files', []))

                if self.playlistList.count() > 0:
                    self.load_video(self.playlistList.item(0).data(Qt.ItemDataRole.UserRole))
            except Exception as e:
                print(f"Error loading playlist: {e}")
                from qfluentwidgets import InfoBar, InfoBarPosition
                InfoBar.error(
                    title=tr('open_project_title'),
                    content=f"Error: {e}",
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=5000,
                    parent=self
                )

    def load_playlist_from_file(self):
        fileName, _ = QFileDialog.getOpenFileName(
            self, tr('open_project_title'), "", f"{tr('json_files')} (*.json)"
        )
        if fileName:
            self.load_playlist_by_path(fileName)

    # ------------------------------------------------------------------ #
    # File info dialog                                                     #
    # ------------------------------------------------------------------ #

    def show_file_info(self):
        if not self.currentFilePath or not os.path.exists(self.currentFilePath):
            return

        try:
            ffprobe_path = get_resource_path("ffprobe.exe" if os.name == 'nt' else "ffprobe")
            if not os.path.exists(ffprobe_path):
                ffprobe_path = "ffprobe"

            cmd = [
                ffprobe_path, "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height,avg_frame_rate,codec_name,pix_fmt",
                "-show_entries", "format=size,duration,format_name",
                "-of", "json", self.currentFilePath
            ]

            creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            result = subprocess.check_output(cmd, creationflags=creationflags).decode('utf-8')
            data = json.loads(result)

            stream = data.get('streams', [{}])[0]
            fmt = data.get('format', {})

            size_mb = float(fmt.get('size', 0)) / (1024 * 1024)
            res = f"{stream.get('width', '?')}x{stream.get('height', '?')}"
            codec = stream.get('codec_name', 'unknown')
            pix_fmt = stream.get('pix_fmt', 'unknown')
            container = fmt.get('format_name', 'unknown').split(',')[0]

            info_text = (
                f"<b>{tr('file')}:</b> {os.path.basename(self.currentFilePath)}<br><br>"
                f"<b>{tr('resolution')}:</b> {res}<br>"
                f"<b>{tr('codec')}:</b> {codec} ({pix_fmt})<br>"
                f"<b>{tr('container')}:</b> {container}<br>"
                f"<b>{tr('fps')}:</b> {float(self.fps):.2f}<br>"
                f"<b>{tr('size')}:</b> {size_mb:.2f} MB<br><br>"
                f"<font color='#888'>{self.currentFilePath}</font>"
            )

            # Create a compact menu instead of a MessageBox
            from PyQt6.QtWidgets import QMenu, QWidgetAction, QLabel, QVBoxLayout, QWidget
            menu = QMenu(self)
            menu.setStyleSheet(MENU_STYLE)
            
            content = QWidget()
            layout = QVBoxLayout(content)
            layout.setContentsMargins(15, 10, 15, 10)
            
            label = QLabel(info_text)
            label.setStyleSheet("color: white; font-size: 12px; border: none;")
            label.setWordWrap(True)
            label.setFixedWidth(280)
            layout.addWidget(label)
            
            action = QWidgetAction(menu)
            action.setDefaultWidget(content)
            menu.addAction(action)
            
            # Show menu next to the info button
            pos = self.infoButton.mapToGlobal(QPoint(0, self.infoButton.height() + 5))
            menu.exec(pos)

        except Exception as e:
            print(f"Error getting file info: {e}")

    # ------------------------------------------------------------------ #
    # Panel toggles                                                        #
    # ------------------------------------------------------------------ #

    def toggle_playlist(self):
        is_visible = self.playlistContainer.isVisible()
        if not is_visible:
            self.drawingContainer.hide()
        self.playlistContainer.setVisible(not is_visible)

        if not is_visible:
            sizes = self.mainSplitter.sizes()
            if sizes[3] < 250:
                sizes[3] = 250
                self.mainSplitter.setSizes(sizes)
