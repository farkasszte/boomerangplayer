import os
import json
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFileDialog
from qfluentwidgets import InfoBar, InfoBarPosition
from translations import tr

class PlaylistPersistenceMixin:
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
