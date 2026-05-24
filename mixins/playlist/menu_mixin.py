from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtWidgets import QMenu
from styles import MENU_STYLE
from translations import tr

class PlaylistMenuMixin:
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

        menu = QMenu(self)
        menu.setStyleSheet(MENU_STYLE)
        menu.addAction(tr('rename'), lambda: self.rename_playlist_item(item))
        menu.addAction(tr('open_in_new_window'), lambda: self.open_in_new_window(item))
        menu.addAction(tr('remove_selected'), self.remove_from_playlist)
        menu.addAction(tr('delete_file'), lambda: self.delete_playlist_item(item))
        menu.exec(pos)
