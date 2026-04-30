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
from utils import get_resource_path
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
        for filePath in file_paths:
            if os.path.isfile(filePath):
                item = QListWidgetItem(os.path.basename(filePath))
                if self.thumbToggle.isChecked():
                    item.setSizeHint(QSize(120, 130))
                else:
                    item.setSizeHint(QSize(0, 28))
                item.setData(Qt.ItemDataRole.UserRole, filePath)
                placeholder = QPixmap(120, 120)
                placeholder.fill(QColor(60, 60, 60))
                item.setIcon(QIcon(placeholder))
                self.playlistList.addItem(item)

                if self.thumbToggle.isChecked():
                    thread = ThumbnailThread(filePath, self)
                    thread.finished.connect(self.on_thumbnail_ready)
                    self.thumb_threads.append(thread)
                    thread.start()

    # ------------------------------------------------------------------ #
    # Thumbnail callbacks                                                  #
    # ------------------------------------------------------------------ #

    def on_thumbnail_ready(self, filePath, pixmap):
        if not self.thumbToggle.isChecked():
            return
        for i in range(self.playlistList.count()):
            item = self.playlistList.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == filePath:
                item.setIcon(QIcon(pixmap))
                break

    def on_thumb_toggle_changed(self, checked):
        if checked:
            self.playlistList.setIconSize(QSize(120, 120))
            self.playlistList.setSpacing(5)
            for i in range(self.playlistList.count()):
                item = self.playlistList.item(i)
                item.setSizeHint(QSize(120, 130))
                filePath = item.data(Qt.ItemDataRole.UserRole)
                placeholder = QPixmap(120, 120)
                placeholder.fill(QColor(60, 60, 60))
                item.setIcon(QIcon(placeholder))

                thread = ThumbnailThread(filePath, self)
                thread.finished.connect(self.on_thumbnail_ready)
                self.thumb_threads.append(thread)
                thread.start()
        else:
            self.playlistList.setIconSize(QSize(0, 0))
            self.playlistList.setSpacing(1)
            for i in range(self.playlistList.count()):
                item = self.playlistList.item(i)
                item.setIcon(QIcon())
                item.setSizeHint(QSize(0, 28))

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
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        menu.setStyleSheet(MENU_STYLE)
        menu.addAction(tr('rename'), lambda: self.rename_playlist_item(item))
        menu.addAction(tr('open_in_new_window'), lambda: self.open_in_new_window(item))
        menu.addAction(tr('remove_selected'), self.remove_from_playlist)
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
        
        old_name = os.path.basename(old_path)
        new_name, ok = QInputDialog.getText(self, tr('rename_file_title'), tr('enter_new_name'), text=old_name)
        
        if ok and new_name and new_name != old_name:
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
                    for t in getattr(self, 'thumb_threads', []):
                        if t.filePath == old_path and t.isRunning():
                            t.cancel()
                
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
                    self.setWindowTitle(f"Boomerang Player - {new_name}")
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
                'name': item.text().lower(),
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
        item = self.playlistList.currentItem()
        if item:
            path = item.data(Qt.ItemDataRole.UserRole)
            if path in self.playlistData:
                del self.playlistData[path]
            self.playlistList.takeItem(self.playlistList.row(item))

    def clear_playlist(self):
        self.playlistList.clear()
        self.playlistData = {}
        self.stop_playback()
        self.cleanup_cache()
        self.currentFilePath = None
        self.setWindowTitle("Boomerang Player")
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

    def load_playlist_from_file(self):
        fileName, _ = QFileDialog.getOpenFileName(
            self, tr('open_project_title'), "", f"{tr('json_files')} (*.json)"
        )
        if fileName:
            with open(fileName, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.playlistList.clear()
            self.playlistData = data.get('markers', {})

            for filePath in data.get('files', []):
                if os.path.exists(filePath):
                    item = QListWidgetItem(os.path.basename(filePath))
                    item.setData(Qt.ItemDataRole.UserRole, filePath)
                    self.playlistList.addItem(item)

            if self.playlistList.count() > 0:
                self.load_video(self.playlistList.item(0).data(Qt.ItemDataRole.UserRole))

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
