import os
import subprocess
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QPixmap
from qfluentwidgets import MessageBox, InfoBar, InfoBarPosition
from translations import tr
from utils import VERSION, send_to_recycle_bin

class PlaylistCrudMixin:
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
                    self.mediaPlayer.setSource(QUrl.fromLocalFile(old_path))
                
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
                self.mediaPlayer.setSource(QUrl.fromLocalFile(path))
            
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
