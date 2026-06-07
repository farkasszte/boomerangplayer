import os
import json
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFileDialog
from qfluentwidgets import InfoBar, InfoBarPosition
from translations import tr

class PlaylistPersistenceMixin:
    def save_playlist_to_file(self):
        filters = f"{tr('json_files')} (*.json);;{tr('bpl_files')} (*.bpl)"
        fileName, selectedFilter = QFileDialog.getSaveFileName(
            # pyrefly: ignore [bad-argument-type]
            self, tr('save_project_title'), "", filters
        )
        if fileName:
            is_bpl = fileName.lower().endswith('.bpl') or 'bpl_files' in selectedFilter
            if is_bpl and not fileName.lower().endswith('.bpl'):
                fileName += '.bpl'
            elif not is_bpl and not fileName.lower().endswith('.json'):
                fileName += '.json'

            data = {'files': [], 'markers': self.playlistData}
            # pyrefly: ignore [missing-attribute]
            for i in range(self.playlistList.count()):
                # pyrefly: ignore [missing-attribute]
                item = self.playlistList.item(i)
                data['files'].append(item.data(Qt.ItemDataRole.UserRole))
            
            if is_bpl:
                # Add base64 cached thumbnails
                thumbnails = {}
                from PyQt6.QtCore import QByteArray, QBuffer
                # pyrefly: ignore [missing-attribute]
                for i in range(self.playlistList.count()):
                    # pyrefly: ignore [missing-attribute]
                    item = self.playlistList.item(i)
                    filePath = item.data(Qt.ItemDataRole.UserRole)
                    icon = item.icon()
                    if icon and not icon.isNull():
                        pixmap = icon.pixmap(160, 160)
                        if not pixmap.isNull():
                            try:
                                image = pixmap.toImage()
                                ba = QByteArray()
                                buffer = QBuffer(ba)
                                buffer.open(QBuffer.OpenModeFlag.WriteOnly)
                                image.save(buffer, "JPG", 80)
                                base64_str = ba.toBase64().data().decode('utf-8')
                                thumbnails[filePath] = base64_str
                            except Exception as ex:
                                print(f"Error encoding thumbnail to base64: {ex}")
                data['thumbnails'] = thumbnails

            with open(fileName, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)

    def load_playlist_by_path(self, fileName):
        if fileName and os.path.exists(fileName):
            try:
                with open(fileName, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # pyrefly: ignore [missing-attribute]
                self.playlistList.clear()
                self.playlistData = data.get('markers', {})

                cached_thumbnails = data.get('thumbnails', None)
                # pyrefly: ignore [missing-attribute]
                self.add_files_to_playlist(data.get('files', []), cached_thumbnails=cached_thumbnails)

                # pyrefly: ignore [missing-attribute]
                if self.playlistList.count() > 0:
                    # pyrefly: ignore [missing-attribute]
                    self.load_video(self.playlistList.item(0).data(Qt.ItemDataRole.UserRole))
            except Exception as e:
                print(f"Error loading playlist: {e}")
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
        filters = f"{tr('json_files')} (*.json);;{tr('bpl_files')} (*.bpl);;{tr('all_files')} (*)"
        fileName, _ = QFileDialog.getOpenFileName(
            # pyrefly: ignore [bad-argument-type]
            self, tr('open_project_title'), "", filters
        )
        if fileName:
            self.load_playlist_by_path(fileName)
