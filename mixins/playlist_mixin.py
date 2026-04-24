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

        taken_items = []
        for _ in range(self.playlistList.count()):
            taken_items.append(self.playlistList.takeItem(0))

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
                f"{tr('file')}: {os.path.basename(self.currentFilePath)}\n\n"
                f"{tr('resolution')}: {res}\n"
                f"{tr('codec')}: {codec} ({pix_fmt})\n"
                f"{tr('container')}: {container}\n"
                f"{tr('fps')}: {float(self.fps):.2f}\n"
                f"{tr('size')}: {size_mb:.2f} MB\n\n"
                f"{tr('path')}: {self.currentFilePath}"
            )

            w = MessageBox(tr('file_info_title'), info_text, self)
            w.yesButton.setText(tr('ok'))
            w.cancelButton.hide()
            w.exec()

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
