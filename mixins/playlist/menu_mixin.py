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
        # Don't auto-select single item when multi-select is already in effect
        if not item.isSelected():
            self.playlistList.clearSelection()
            item.setSelected(True)
            self.playlistList.setCurrentItem(item)

        selected_count = len(self.playlistList.selectedItems())

        menu = QMenu(self)
        menu.setStyleSheet(MENU_STYLE)

        if selected_count > 1:
            # Multi-selection: check for MJPEGs
            mjpeg_items = self.get_selected_mjpeg_items()
            if mjpeg_items:
                menu.addAction(f"{tr('export_photo')} ({len(mjpeg_items)})", lambda: self.bulk_export_motion_jpg_photos(mjpeg_items))
                menu.addAction(f"{tr('export_video')} ({len(mjpeg_items)})", lambda: self.bulk_export_motion_jpg_videos(mjpeg_items))
            
            menu.addAction(f"{tr('delete_file')} ({selected_count})", self.delete_selected_playlist_items)
            menu.addAction(f"{tr('remove_selected')} ({selected_count})", self.remove_from_playlist)
        else:
            # Single item: full context menu
            menu.addAction(tr('rename'), lambda: self.rename_playlist_item(item))
            menu.addAction(tr('open_in_new_window'), lambda: self.open_in_new_window(item))

            # Motion JPG export actions
            filePath = item.data(Qt.ItemDataRole.UserRole)
            from utils import get_embedded_video_offset
            offset = get_embedded_video_offset(filePath) if filePath else None
            if offset is not None:
                menu.addAction(tr('export_photo'), lambda: self.export_motion_jpg_photo(item))
                menu.addAction(tr('export_video'), lambda: self.export_motion_jpg_video(item))

            menu.addAction(tr('remove_selected'), self.remove_from_playlist)
            menu.addAction(tr('delete_file'), lambda: self.delete_playlist_item(item))

        menu.exec(pos)

    def get_selected_mjpeg_items(self):
        from utils import get_embedded_video_offset
        mjpeg_items = []
        for sel_item in self.playlistList.selectedItems():
            filePath = sel_item.data(Qt.ItemDataRole.UserRole)
            if filePath:
                offset = get_embedded_video_offset(filePath)
                if offset is not None:
                    mjpeg_items.append((sel_item, filePath, offset))
        return mjpeg_items

    def bulk_export_motion_jpg_photos(self, mjpeg_items):
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        import os

        if not mjpeg_items:
            return

        export_dir = QFileDialog.getExistingDirectory(self, tr('select_folder'))
        if not export_dir:
            return

        success_count = 0
        errors = []
        for _, filePath, offset in mjpeg_items:
            try:
                base = os.path.splitext(os.path.basename(filePath))[0]
                target_path = os.path.join(export_dir, f"{base}_photo.jpg")
                with open(filePath, 'rb') as f:
                    data = f.read(offset)
                with open(target_path, 'wb') as f:
                    f.write(data)
                success_count += 1
            except Exception as e:
                errors.append(f"{os.path.basename(filePath)}: {e}")

        if errors:
            QMessageBox.warning(
                self,
                tr('error') or "Error",
                f"Exported {success_count} photos. Failures:\n" + "\n".join(errors)
            )
        else:
            QMessageBox.information(
                self,
                tr('info') or "Information",
                f"Successfully exported {success_count} photos to {export_dir}."
            )

    def bulk_export_motion_jpg_videos(self, mjpeg_items):
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        import os

        if not mjpeg_items:
            return

        export_dir = QFileDialog.getExistingDirectory(self, tr('select_folder'))
        if not export_dir:
            return

        success_count = 0
        errors = []
        for _, filePath, offset in mjpeg_items:
            try:
                base = os.path.splitext(os.path.basename(filePath))[0]
                target_path = os.path.join(export_dir, f"{base}_video.mp4")
                with open(filePath, 'rb') as f:
                    f.seek(offset)
                    data = f.read()
                with open(target_path, 'wb') as f:
                    f.write(data)
                success_count += 1
            except Exception as e:
                errors.append(f"{os.path.basename(filePath)}: {e}")

        if errors:
            QMessageBox.warning(
                self,
                tr('error') or "Error",
                f"Exported {success_count} videos. Failures:\n" + "\n".join(errors)
            )
        else:
            QMessageBox.information(
                self,
                tr('info') or "Information",
                f"Successfully exported {success_count} videos to {export_dir}."
            )

    def export_motion_jpg_photo(self, item):
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        from utils import get_embedded_video_offset
        import os

        filePath = item.data(Qt.ItemDataRole.UserRole)
        if not filePath or not os.path.exists(filePath):
            return

        offset = get_embedded_video_offset(filePath)
        if offset is None:
            QMessageBox.warning(self, tr('warning') or "Warning", "This is not a valid Motion JPG file.")
            return

        # Prepare default filename: original name + _photo.jpg
        base, ext = os.path.splitext(os.path.basename(filePath))
        default_name = f"{base}_photo.jpg"

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            tr('export_photo'),
            os.path.join(os.path.dirname(filePath), default_name),
            "JPEG Image (*.jpg *.jpeg);;All Files (*)"
        )

        if save_path:
            try:
                with open(filePath, 'rb') as f:
                    data = f.read(offset)
                with open(save_path, 'wb') as f:
                    f.write(data)
            except Exception as e:
                QMessageBox.critical(self, tr('error') or "Error", f"Failed to export photo: {e}")

    def export_motion_jpg_video(self, item):
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        from utils import get_embedded_video_offset
        import os

        filePath = item.data(Qt.ItemDataRole.UserRole)
        if not filePath or not os.path.exists(filePath):
            return

        offset = get_embedded_video_offset(filePath)
        if offset is None:
            QMessageBox.warning(self, tr('warning') or "Warning", "This is not a valid Motion JPG file.")
            return

        # Prepare default filename: original name + _video.mp4
        base, ext = os.path.splitext(os.path.basename(filePath))
        default_name = f"{base}_video.mp4"

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            tr('export_video'),
            os.path.join(os.path.dirname(filePath), default_name),
            "MP4 Video (*.mp4);;All Files (*)"
        )

        if save_path:
            try:
                with open(filePath, 'rb') as f:
                    f.seek(offset)
                    data = f.read()
                with open(save_path, 'wb') as f:
                    f.write(data)
            except Exception as e:
                QMessageBox.critical(self, tr('error') or "Error", f"Failed to export video: {e}")
