import os
import subprocess
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QPixmap
from qfluentwidgets import InfoBar, InfoBarPosition
from translations import tr
from utils import VERSION, send_to_recycle_bin, log_debug

def is_same_path(p1, p2):
    if not p1 or not p2:
        return False
    return os.path.normcase(os.path.normpath(p1)) == os.path.normcase(os.path.normpath(p2))

class PlaylistCrudMixin:
    def style_dialog(self, dialog):
        """Applies application-themed stylesheet to a dialog (QMessageBox, QInputDialog, etc.)"""
        accent_color = self.config.get('accent_color', '#00f2ff')
        bg_color = self.config.get('bg_color', '#202020')
        inverse_text = self.config.get('inverse_text', False)
        
        fg_color = "#1c1c1c" if inverse_text else "#ffffff"
        border_color = "rgba(0, 0, 0, 0.35)" if inverse_text else "rgba(255, 255, 255, 0.1)"
        bg_button = "rgba(0, 0, 0, 0.04)" if inverse_text else "rgba(255, 255, 255, 0.05)"
        bg_hover = "rgba(0, 0, 0, 0.08)" if inverse_text else "rgba(255, 255, 255, 0.1)"
        bg_pressed = "rgba(0, 0, 0, 0.02)" if inverse_text else "rgba(255, 255, 255, 0.03)"
        
        dialog.setStyleSheet(f"""
            QDialog, QMessageBox, QInputDialog {{
                background-color: {bg_color};
                border: 1px solid {border_color};
            }}
            QLabel {{
                color: {fg_color};
                font-size: 13px;
                background: transparent;
            }}
            QLineEdit {{
                background: {bg_button};
                border: 1px solid {border_color};
                border-radius: 5px;
                padding: 6px 10px;
                color: {fg_color};
                font-size: 13px;
                selection-background-color: {accent_color};
                selection-color: {fg_color};
            }}
            QLineEdit:focus {{
                border: 1px solid {accent_color};
            }}
            QPushButton {{
                border: 1px solid {border_color};
                border-radius: 4px;
                background-color: {bg_button};
                color: {fg_color};
                font-size: 13px;
                font-weight: 500;
                padding: 6px 16px;
                min-width: 75px;
            }}
            QPushButton:hover {{
                background-color: {bg_hover};
            }}
            QPushButton:pressed {{
                background-color: {bg_pressed};
            }}
            QPushButton:default {{
                border: 1px solid {accent_color};
            }}
        """)

    def recreate_media_player(self):
        from PyQt6 import sip
        from PyQt6.QtMultimedia import QMediaPlayer
        
        # Destroy current player to force release of Windows file locks
        if hasattr(self, 'mediaPlayer') and self.mediaPlayer:
            try:
                self.mediaPlayer.stop()
                self.mediaPlayer.setSource(QUrl())
                self.mediaPlayer.disconnect()
                if not sip.isdeleted(self.mediaPlayer):
                    sip.delete(self.mediaPlayer)
            except Exception as e:
                print(f"Error deleting mediaPlayer: {e}")
                
        # Re-create and bind to existing audioOutput
        self.mediaPlayer = QMediaPlayer()
        if hasattr(self, 'audioOutput') and self.audioOutput:
            self.mediaPlayer.setAudioOutput(self.audioOutput)
            
        # Reconnect signals
        self.mediaPlayer.durationChanged.connect(self.update_duration)
        self.mediaPlayer.playbackStateChanged.connect(self.handle_state_change)
        self.mediaPlayer.mediaStatusChanged.connect(self.handle_status_change)
        self.mediaPlayer.metaDataChanged.connect(self.handle_metadata_change)

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
        
        dialog = QInputDialog(self)
        self.style_dialog(dialog)
        dialog.setWindowTitle(tr('rename_file_title'))
        dialog.setLabelText(tr('enter_new_name'))
        dialog.setTextValue(old_base_name)
        
        ok = dialog.exec()
        new_base_name = dialog.textValue()
        
        if ok and new_base_name and new_base_name != old_base_name:
            new_name = new_base_name + extension
            new_path = os.path.join(os.path.dirname(old_path), new_name)
            is_current = False   # pre-initialise so the except block always has it bound
            try:
                # IMPORTANT: If this is the current file, release the lock!
                is_current = is_same_path(self.currentFilePath, old_path)
                if is_current:
                    # Recreate media player to release file lock on Windows
                    self.recreate_media_player()
                    
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
                if is_current and is_same_path(self.currentFilePath, old_path):
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
        log_debug(f"delete_playlist_item entered. path: {path}")
        if not path or not os.path.exists(path):
            log_debug(f"delete_playlist_item returning early. path exists: {os.path.exists(path) if path else False}")
            return

        from PyQt6.QtWidgets import QMessageBox
        box = QMessageBox(self)
        self.style_dialog(box)
        box.setWindowTitle(tr('delete_file_confirm_title'))
        box.setText(tr('delete_file_confirm_msg').format(os.path.basename(path)))
        box.setIcon(QMessageBox.Icon.Question)
        delete_btn = box.addButton(tr('delete'), QMessageBox.ButtonRole.YesRole)
        cancel_btn = box.addButton(tr('cancel'), QMessageBox.ButtonRole.NoRole)
        box.setDefaultButton(cancel_btn)
        
        box.exec()
        if box.clickedButton() != delete_btn:
            log_debug("Delete cancelled in QMessageBox.")
            return

        is_current = False   # pre-initialise so the except block always has it bound
        log_debug(f"delete_playlist_item started for path: {path}")
        try:
            is_current = is_same_path(self.currentFilePath, path)
            log_debug(f"is_current: {is_current} (currentFilePath: {self.currentFilePath})")

            # 1. Stop extraction if running on this path
            if hasattr(self, 'extraction_thread') and self.extraction_thread:
                is_running = self.extraction_thread.isRunning()
                ext_path = getattr(self.extraction_thread, 'video_path', None)
                log_debug(f"Extraction thread: running={is_running}, path={ext_path}")
                if is_same_path(ext_path, path) and is_running:
                    log_debug("Cancelling extraction thread...")
                    self.extraction_thread.cancel()
                    self.extraction_thread.wait()
                    log_debug("Extraction thread cancelled and waited.")

            # 2. Stop any thumbnail generation for this file
            if hasattr(self, 'thumb_queue') and path in self.thumb_queue:
                log_debug("Removing path from thumb_queue")
                self.thumb_queue.remove(path)

            for t in getattr(self, 'thumb_threads', []):
                t_path = t.filePath
                t_running = t.isRunning()
                log_debug(f"Thumbnail thread for {t_path}: running={t_running}")
                if is_same_path(t_path, path):
                    log_debug(f"Cancelling thumbnail thread for {t_path}...")
                    t.cancel()
                    t.wait()
                    log_debug("Thumbnail thread cancelled and waited.")

            if is_current:
                # 3. Stop playback
                self.stop_playback()
                
                # 4. Recreate media player to force release file lock on Windows
                log_debug("Recreating media player...")
                self.recreate_media_player()
                log_debug("Media player recreated.")
                
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

            from PyQt6.QtCore import QCoreApplication
            log_debug("Processing Qt events...")
            QCoreApplication.processEvents()
            
            import gc
            log_debug("Triggering garbage collection...")
            gc.collect()

            log_debug("Calling send_to_recycle_bin...")
            success = send_to_recycle_bin(path)
            log_debug(f"send_to_recycle_bin returned: {success}")
            
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
            log_debug(f"Exception caught in delete_playlist_item: {e}")
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

    def delete_selected_playlist_items(self):
        """Delete multiple selected playlist items (move to Recycle Bin)."""
        selected_items = self.playlistList.selectedItems()
        log_debug(f"delete_selected_playlist_items started. Selected count: {len(selected_items)}")
        if not selected_items:
            # Try current item
            curr = self.playlistList.currentItem()
            if curr:
                selected_items = [curr]
                log_debug(f"No selection, fell back to currentItem: {curr.data(Qt.ItemDataRole.UserRole)}")
            else:
                log_debug("No selection or current item found. Returning.")
                return

        # Filter to only valid/existing files
        valid_items = []
        for item in selected_items:
            path = item.data(Qt.ItemDataRole.UserRole)
            if path and os.path.exists(path):
                valid_items.append((item, path))

        log_debug(f"Valid items to delete: {[p for _, p in valid_items]}")
        if not valid_items:
            return

        count = len(valid_items)

        if count == 1:
            log_debug("Routing to single-item delete flow delete_playlist_item")
            self.delete_playlist_item(valid_items[0][0])
            return

        # Build confirmation message with file list (capped to prevent overflow)
        if count > 15:
            display_items = valid_items[:15]
            file_names = "\n".join(f"• {os.path.basename(path)}" for _, path in display_items)
            remaining_count = count - 15
            more_text = tr('and_more_files').format(count=remaining_count)
            file_names += f"\n{more_text}"
        else:
            file_names = "\n".join(f"• {os.path.basename(path)}" for _, path in valid_items)

        msg = tr('delete_multiple_confirm_msg').format(count=count, file_list=file_names)

        from PyQt6.QtWidgets import QMessageBox
        box = QMessageBox(self)
        self.style_dialog(box)
        box.setWindowTitle(tr('delete_file_confirm_title'))
        box.setText(msg)
        box.setIcon(QMessageBox.Icon.Question)
        delete_btn = box.addButton(tr('delete'), QMessageBox.ButtonRole.YesRole)
        cancel_btn = box.addButton(tr('cancel'), QMessageBox.ButtonRole.NoRole)
        box.setDefaultButton(cancel_btn)

        box.exec()
        if box.clickedButton() != delete_btn:
            log_debug("Bulk delete confirmation cancelled by user.")
            return

        # Track which file is currently playing to handle cleanup
        current_was_deleted = False
        success_count = 0
        error_count = 0
        errors = []

        for item, path in valid_items:
            is_current = False   # pre-initialise so the except block always has it bound
            log_debug(f"Bulk delete: processing path {path}")
            try:
                is_current = is_same_path(self.currentFilePath, path)
                log_debug(f"is_current: {is_current}")

                # 1. Stop extraction if running on this path
                if hasattr(self, 'extraction_thread') and self.extraction_thread:
                    ext_running = self.extraction_thread.isRunning()
                    ext_path = getattr(self.extraction_thread, 'video_path', None)
                    if is_same_path(ext_path, path) and ext_running:
                        log_debug("Cancelling extraction thread...")
                        self.extraction_thread.cancel()
                        self.extraction_thread.wait()

                # 2. Stop any thumbnail generation for this file
                if hasattr(self, 'thumb_queue') and path in self.thumb_queue:
                    self.thumb_queue.remove(path)

                for t in getattr(self, 'thumb_threads', []):
                    if is_same_path(t.filePath, path):
                        t.cancel()
                        t.wait()

                if is_current:
                    current_was_deleted = True
                    # 3. Stop playback
                    self.stop_playback()
                    
                    # 4. Recreate media player to force release file lock
                    self.recreate_media_player()
                    
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

                from PyQt6.QtCore import QCoreApplication
                QCoreApplication.processEvents()
                
                import gc
                gc.collect()

                log_debug("Calling send_to_recycle_bin...")
                success = send_to_recycle_bin(path)
                log_debug(f"send_to_recycle_bin returned: {success}")
                if success:
                    # Remove from playlistData (markers)
                    if path in self.playlistData:
                        del self.playlistData[path]
                    success_count += 1
                else:
                    error_count += 1
                    errors.append(os.path.basename(path))
                    if is_current:
                        current_was_deleted = False

            except Exception as e:
                log_debug(f"Exception in bulk delete for {path}: {e}")
                error_count += 1
                errors.append(f"{os.path.basename(path)} ({e})")
                print(f"Error deleting {path}: {e}")
                if current_was_deleted and is_current:
                    current_was_deleted = False

        # Remove items from playlist view in reverse order to maintain valid row indices
        rows_to_remove = []
        for item, _ in valid_items:
            
            row = self.playlistList.row(item)
            if row >= 0:
                rows_to_remove.append(row)

        for row in sorted(rows_to_remove, reverse=True):
            
            self.playlistList.takeItem(row)

        # Show result
        if success_count > 0:
            InfoBar.success(
                title=tr('delete_file_confirm_title'),
                content=tr('delete_multiple_success').format(count=success_count),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
        if error_count > 0:
            error_msg = "; ".join(errors)
            InfoBar.error(
                title=tr('delete_file_confirm_title'),
                content=f"Failed to delete {error_count} file(s): {error_msg}",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )

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
