import os
from PyQt6.QtCore import Qt

class PlaylistSortMixin:
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
