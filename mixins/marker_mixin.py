"""
MarkerMixin — loop markers, loop range, loop mode, save/load frame & segment.
"""

import os
import subprocess
import bisect
from PyQt6.QtWidgets import QFileDialog, QDialog, QListWidget, QListWidgetItem, QHBoxLayout, QVBoxLayout, QLabel, QWidget
from PyQt6.QtGui import QImage
from PyQt6.QtCore import Qt, QSize
from qfluentwidgets import ToolButton, FluentIcon, PushButton, LineEdit, CaptionLabel
from translations import tr, get_lang
from utils import get_resource_path


class MarkerRowWidget(QWidget):
    def __init__(self, frame, name, parent_dialog, parent_player):
        super().__init__()
        self.frame = frame
        self.parent_dialog = parent_dialog
        self.parent_player = parent_player

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(8)

        # Convert frame to timestamp
        fps = getattr(self.parent_player, 'fps', 30.0)
        if fps <= 0:
            fps = 30.0
        seconds = frame / fps
        from utils import format_time
        time_str = format_time(int(seconds * 1000))

        # Time label
        self.label = QLabel(f"<b>{time_str}</b>")
        self.label.setStyleSheet("color: white; font-size: 12px; background: transparent; border: none;")
        layout.addWidget(self.label)

        # Frame LineEdit
        from PyQt6.QtGui import QIntValidator
        self.frameEdit = LineEdit()
        self.frameEdit.setFixedWidth(65)
        self.frameEdit.setText(str(frame))
        total_f = int(getattr(self.parent_player, 'total_frames', 999999))
        self.frameEdit.setValidator(QIntValidator(0, total_f))
        self.frameEdit.setStyleSheet("""
            LineEdit {
                color: #aaa; 
                background: rgba(255,255,255,0.06); 
                border: 1px solid rgba(255,255,255,0.1); 
                border-radius: 4px;
                font-size: 12px;
                height: 24px;
                text-align: center;
            }
        """)
        self.frameEdit.returnPressed.connect(self.on_save_clicked)
        layout.addWidget(self.frameEdit)

        # LineEdit for name
        self.nameEdit = LineEdit()
        self.nameEdit.setText(name)
        self.nameEdit.setPlaceholderText(tr('marker_name'))
        self.nameEdit.setStyleSheet("""
            LineEdit {
                color: white; 
                background: rgba(255,255,255,0.06); 
                border: 1px solid rgba(255,255,255,0.1); 
                border-radius: 4px;
                font-size: 12px;
                height: 24px;
            }
        """)
        self.nameEdit.returnPressed.connect(self.on_save_clicked)
        layout.addWidget(self.nameEdit)

        # Save Button
        self.saveBtn = ToolButton(FluentIcon.SAVE)
        self.saveBtn.setFixedSize(28, 28)
        self.saveBtn.clicked.connect(self.on_save_clicked)
        layout.addWidget(self.saveBtn)

        # Jump Button
        self.jumpBtn = ToolButton(FluentIcon.PLAY)
        self.jumpBtn.setFixedSize(28, 28)
        self.jumpBtn.clicked.connect(self.on_jump_clicked)
        layout.addWidget(self.jumpBtn)

        # Delete Button
        self.deleteBtn = ToolButton(FluentIcon.DELETE)
        self.deleteBtn.setFixedSize(28, 28)
        self.deleteBtn.clicked.connect(self.on_delete_clicked)
        layout.addWidget(self.deleteBtn)

    def on_save_clicked(self):
        try:
            new_frame = int(self.frameEdit.text())
        except ValueError:
            return
        new_name = self.nameEdit.text()
        self.parent_dialog.save_marker_changes(self.frame, new_frame, new_name)

    def on_jump_clicked(self):
        self.parent_player.set_position(self.frame)

    def on_delete_clicked(self):
        self.parent_dialog.delete_marker(self.frame)


class MarkersDialog(QDialog):
    def __init__(self, parent_player):
        super().__init__(parent_player)
        self.parent_player = parent_player
        self.setWindowTitle(tr('markers_title'))
        self.setMinimumSize(420, 450)
        self.setStyleSheet("background: #202020; color: white;")

        self.layout = QVBoxLayout(self)
        
        self.layout.setContentsMargins(15, 15, 15, 15)
        
        self.layout.setSpacing(10)

        # List Widget
        self.listWidget = QListWidget()
        self.listWidget.setStyleSheet("""
            QListWidget {
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 6px;
                padding: 5px;
            }
            QListWidget::item {
                background: transparent;
                border-bottom: 1px solid rgba(255,255,255,0.04);
                padding: 4px;
            }
            QListWidget::item:selected {
                background: rgba(255,255,255,0.06);
            }
        """)
        self.listWidget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        
        self.layout.addWidget(self.listWidget)

        # Bottom Buttons
        self.closeBtn = PushButton(tr('close'))
        self.closeBtn.clicked.connect(self.close)
        self.closeBtn.setFixedWidth(100)
        
        self.addMarkerBtn = PushButton("+ " + tr('add_marker'))
        self.addMarkerBtn.clicked.connect(self.on_add_marker_clicked)
        
        btnLayout = QHBoxLayout()
        btnLayout.addWidget(self.addMarkerBtn)
        btnLayout.addStretch(1)
        btnLayout.addWidget(self.closeBtn)
        
        self.layout.addLayout(btnLayout)

        self.load_markers()

    def load_markers(self):
        self.listWidget.clear()
        
        markers = self.parent_player.markers
        playlistData = self.parent_player.playlistData
        curr_path = self.parent_player.currentFilePath
        
        marker_names = {}
        if curr_path in playlistData:
            marker_names = playlistData[curr_path].get('marker_names', {})

        # Sort markers with 0 forced to the very end of the list for better UX
        sorted_markers = sorted(markers, key=lambda x: float('inf') if x == 0 else x)
        for f in sorted_markers:
            name = marker_names.get(str(f), f"{tr('mark')} {f}")
            
            item = QListWidgetItem(self.listWidget)
            item.setSizeHint(QSize(0, 48))
            self.listWidget.addItem(item)
            
            row = MarkerRowWidget(f, name, self, self.parent_player)
            self.listWidget.setItemWidget(item, row)

    def save_all_rows_in_place(self):
        rows_data = []
        for i in range(self.listWidget.count()):
            item = self.listWidget.item(i)
            if not item:
                continue
            widget = self.listWidget.itemWidget(item)
            if isinstance(widget, MarkerRowWidget):
                try:
                    frame_val = int(widget.frameEdit.text())
                    name_val = widget.nameEdit.text()
                    rows_data.append((widget.frame, frame_val, name_val))
                except ValueError:
                    rows_data.append((widget.frame, widget.frame, widget.nameEdit.text()))

        playlistData = self.parent_player.playlistData
        curr_path = self.parent_player.currentFilePath
        
        if curr_path:
            if curr_path not in playlistData:
                playlistData[curr_path] = {}
            if 'marker_names' not in playlistData[curr_path]:
                playlistData[curr_path]['marker_names'] = {}
            names = playlistData[curr_path]['marker_names']
            
            new_markers = []
            new_names = {}
            for old_frame, new_frame, new_name in rows_data:
                if new_frame not in new_markers:
                    new_markers.append(new_frame)
                new_names[str(new_frame)] = new_name
                
            new_markers.sort()
            self.parent_player.markers = new_markers
            playlistData[curr_path]['marker_names'] = new_names
            
            self.parent_player.needs_range_update = True
            self.parent_player.progressBar.update_markers(self.parent_player.markers)
            self.parent_player.update_loop_frames_label()
            self.parent_player.save_current_markers()
            self.parent_player.update_chronometer()

    def closeEvent(self, event):
        self.save_all_rows_in_place()
        super().closeEvent(event)

    def on_add_marker_clicked(self):
        self.save_all_rows_in_place()
        self.parent_player.add_smart_marker(force_new=True)
        self.load_markers()

    def save_marker_changes(self, old_frame, new_frame, new_name):
        self.save_all_rows_in_place()
        self.load_markers()

    def delete_marker(self, frame):
        self.save_all_rows_in_place()
        
        if frame in self.parent_player.markers:
            self.parent_player.markers.remove(frame)
            
        playlistData = self.parent_player.playlistData
        curr_path = self.parent_player.currentFilePath
        if curr_path in playlistData and 'marker_names' in playlistData[curr_path]:
            if str(frame) in playlistData[curr_path]['marker_names']:
                del playlistData[curr_path]['marker_names'][str(frame)]
                
        self.parent_player.needs_range_update = True
        self.parent_player.progressBar.update_markers(self.parent_player.markers)
        self.parent_player.update_loop_frames_label()
        self.parent_player.save_current_markers()
        self.parent_player.update_chronometer()
        
        self.load_markers()


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QMainWindow, QSlider
    from config import Configuration
    MarkerMixinBase = QMainWindow
else:
    MarkerMixinBase = object


class MarkerMixin(MarkerMixinBase):
    if TYPE_CHECKING:
        current_cache_index: int
        markers: list
        needs_range_update: bool
        progressBar: QSlider
        playlistData: dict
        currentFilePath: str | None
        fps: float
        cached_frame_dict: dict
        config: Configuration
        
        update_loop_frames_label: callable
        save_current_markers: callable
        update_chronometer: callable
        update_pixmap_from_cache: callable
    # ------------------------------------------------------------------ #
    # Marker CRUD                                                          #
    # ------------------------------------------------------------------ #

    def add_smart_marker(self, force_new=False):
        f = self.current_cache_index
        if force_new:
            while f in self.markers:
                f += 1
        
        if f not in self.markers:
            self.markers.append(f)
            self.markers.sort()

        self.needs_range_update = True
        
        self.progressBar.update_markers(self.markers)
        self.update_loop_frames_label()
        self.save_current_markers()
        self.update_chronometer()

    def delete_nearest_marker(self):
        if not self.markers:
            return

        f = self.current_cache_index
        closest = min(self.markers, key=lambda m: abs(m - f))
        self.markers.remove(closest)

        self.needs_range_update = True
        
        self.progressBar.update_markers(self.markers)
        self.update_loop_frames_label()
        self.save_current_markers()
        self.update_chronometer()

    def clear_loop_markers(self):
        self.markers = []
        
        self.progressBar.update_markers(self.markers)
        self.update_loop_frames_label()
        self.save_current_markers()
        self.update_chronometer()

    # ------------------------------------------------------------------ #
    # Loop range calculation                                               #
    # ------------------------------------------------------------------ #

    def get_active_loop_range(self):
        
        if not self.currentFilePath or self.total_frames <= 0:
            return 0, 0

        f = self.current_cache_index
        
        last_frame = max(0, self.total_frames - 1)
        valid_markers = [int(m) for m in self.markers if 0 < m < last_frame]
        full_markers = sorted(list(set([0, last_frame] + valid_markers)))

        if getattr(self, 'isForward', True):
            idx = bisect.bisect_right(full_markers, f)
        else:
            idx = bisect.bisect_left(full_markers, f)

        if idx == 0:
            start_frame = full_markers[0]
            end_frame = full_markers[1] if len(full_markers) > 1 else full_markers[0]
        elif idx >= len(full_markers):
            start_frame = full_markers[-2] if len(full_markers) > 1 else 0
            end_frame = full_markers[-1]
        else:
            start_frame = full_markers[idx - 1]
            end_frame = full_markers[idx]

        return start_frame, end_frame

    def update_loop_frames_label(self):
        if not self.currentFilePath:
            return
        if hasattr(self, 'manageMarkersButton') and self.manageMarkersButton:
            count = len(self.markers)
            self.manageMarkersButton.setText(f"{tr('manage_markers')} ({count})")

    def show_markers_dialog(self):
        if not self.currentFilePath:
            return
        dialog = MarkersDialog(self)
        dialog.exec()

    # ------------------------------------------------------------------ #
    # Loop mode changes                                                    #
    # ------------------------------------------------------------------ #

    def on_loop_mode_changed(self, index):
        self.isPingPong = (index == 3)
        if index == 2:  # Backward
            self.isForward = False
        else:
            self.isForward = True

        if self.currentFilePath:
            if self.currentFilePath not in self.playlistData:
                self.playlistData[self.currentFilePath] = {'markers': [], 'loopMode': 0}
            self.playlistData[self.currentFilePath]['loopMode'] = index

    # ------------------------------------------------------------------ #
    # Playlist marker persistence                                          #
    # ------------------------------------------------------------------ #

    def save_current_markers(self):
        if getattr(self, 'is_loading_video', False):
            return
        if self.currentFilePath:
            if self.currentFilePath not in self.playlistData:
                self.playlistData[self.currentFilePath] = {}
                
            data = self.playlistData[self.currentFilePath]
            data['markers'] = self.markers
            
            data['loopMode'] = self.loopCombo.currentIndex()
            
            data['speed'] = self.speedSlider.value()
            data['isMirrored'] = self.isMirrored
            data['isMirroredVertical'] = self.isMirroredVertical
            data['rotationAngle'] = self.rotationAngle
            
            data['brightness'] = self.brightnessSlider.value()
            
            data['contrast'] = self.contrastSlider.value()
            
            data['gamma'] = self.gammaSlider.value()
            
            data['saturation'] = self.saturationSlider.value()
            data['lastPosition'] = self.current_cache_index

            
            data['zoom'] = self.zoomSlider.value()
            if hasattr(self, 'view') and self.view:
                center = self.view.mapToScene(self.view.viewport().rect().center())
                data['centerX'] = center.x()
                data['centerY'] = center.y()
                # Save serialized drawing strokes
                data['drawings'] = self.view.serialize_strokes()
            
            from utils import save_markers
            save_markers(self.playlistData)

    def load_markers_for_current(self):
        if self.currentFilePath in self.playlistData:
            data = self.playlistData[self.currentFilePath]
            self.markers = data.get('markers', [])
            self.markers.sort()
            
            self.progressBar.update_markers(self.markers)
            self.needs_range_update = True

            loop_mode = data.get('loopMode', 3)
            
            self.loopCombo.setCurrentIndex(loop_mode)
            self.isPingPong = (loop_mode == 3)

            if not getattr(self, 'isSpeedLocked', False):
                
                self.speedSlider.setValue(data.get('speed', 100))
            self.isMirrored = data.get('isMirrored', False)
            self.isMirroredVertical = data.get('isMirroredVertical', False)
            self.rotationAngle = data.get('rotationAngle', 0)

            
            self.brightnessSlider.setValue(data.get('brightness', 0))
            
            self.contrastSlider.setValue(data.get('contrast', 100))
            
            self.gammaSlider.setValue(data.get('gamma', 100))
            
            self.saturationSlider.setValue(data.get('saturation', 100))

            # Restore zoom UI immediately to prevent cascade
            zoom_val = data.get('zoom', 100)
            
            self.zoomSlider.blockSignals(True)
            
            self.zoomSlider.setValue(zoom_val)
            
            self.zoomSlider.blockSignals(False)
            
            if hasattr(self, 'zoomValueLabel') and self.zoomValueLabel:
                if hasattr(self.zoomValueLabel, 'setValue'):
                    self.zoomValueLabel.blockSignals(True)
                    self.zoomValueLabel.setValue(zoom_val)
                    self.zoomValueLabel.blockSignals(False)
                else:
                    self.zoomValueLabel.setText(f"{zoom_val}%")

            
            self.apply_transformations(fit=True)
            
            # Restore position
            last_pos = data.get('lastPosition', 0)
            if last_pos > 0:
                
                self.set_position(last_pos)

            # Restore drawings
            if hasattr(self, 'view') and self.view:
                self.view.deserialize_strokes(data.get('drawings', []))
        else:
            self.markers = []
            
            self.progressBar.update_markers(self.markers)
            self.needs_range_update = True
            if not getattr(self, 'isSpeedLocked', False):
                
                self.speedSlider.setValue(100)
            
            # Reset transform state so previous video's flips/rotation don't carry over
            self.isMirrored = False
            self.isMirroredVertical = False
            self.rotationAngle = 0
            
            # Reset zoom UI immediately
            
            self.zoomSlider.blockSignals(True)
            
            self.zoomSlider.setValue(100)
            
            self.zoomSlider.blockSignals(False)
            
            if hasattr(self, 'zoomValueLabel') and self.zoomValueLabel:
                if hasattr(self.zoomValueLabel, 'setValue'):
                    self.zoomValueLabel.blockSignals(True)
                    self.zoomValueLabel.setValue(100)
                    self.zoomValueLabel.blockSignals(False)
                else:
                    self.zoomValueLabel.setText("100%")
            
            
            self.reset_adjustments()
            
            self.apply_transformations(fit=True)

            # Clear drawings
            if hasattr(self, 'view') and self.view:
                self.view.clear_strokes()

        self.update_loop_frames_label()

    # ------------------------------------------------------------------ #
    # Save frame / save loop segment                                       #
    # ------------------------------------------------------------------ #

    def save_current_frame(self):
        if self.current_cache_index not in getattr(self, 'cached_frame_dict', {}):
            return

        fileName, _ = QFileDialog.getSaveFileName(self, "Save Frame", "", "PNG Image (*.png)")
        if fileName:
            data = self.cached_frame_dict[self.current_cache_index]
            img = QImage()
            if isinstance(data, bytes):
                img.loadFromData(data)
            elif isinstance(data, str):
                img.load(data)
            img.save(fileName)

    def save_loop_segment(self):
        if not self.currentFilePath:
            return

        fileName, _ = QFileDialog.getSaveFileName(self, "Save Loop", "", "Video Files (*.mp4 *.mkv)")
        if fileName:
            ffmpeg_path = get_resource_path("ffmpeg.exe" if os.name == 'nt' else "ffmpeg")

            if not os.path.exists(ffmpeg_path):
                ffmpeg_path = "ffmpeg"

            if self.fps > 0:
                # Use current loop range
                start_f, end_f = self.get_active_loop_range()
                start_sec = max(0.0, (start_f / self.fps) - 0.001)
            else:
                start_f, end_f = self.get_active_loop_range()
                start_sec = 0.0

            encode_args = ["-c:v", "libx264", "-crf", "18", "-preset", "fast", "-c:a", "aac", "-b:a", "192k"]

            if end_f == 0 or end_f >= self.progressBar.maximum():
                cmd = [
                    ffmpeg_path, "-y",
                    "-ss", f"{start_sec:.6f}",
                    "-i", self.currentFilePath
                ] + encode_args + [fileName]
            else:
                if self.fps > 0:
                    frames_count = max(1, end_f - start_f)
                    duration_sec = (frames_count / self.fps) + 0.005

                    cmd = [
                        ffmpeg_path, "-y",
                        "-ss", f"{start_sec:.6f}",
                        "-i", self.currentFilePath,
                        "-t", f"{duration_sec:.6f}",
                        "-frames:v", str(frames_count)
                    ] + encode_args + [fileName]
                else:
                    duration_sec = (end_f - start_f) / 30.0
                    cmd = [
                        ffmpeg_path, "-y",
                        "-ss", f"{start_sec:.6f}",
                        "-i", self.currentFilePath,
                        "-t", f"{duration_sec:.6f}"
                    ] + encode_args + [fileName]

            try:
                creationflags = 0
                if os.name == 'nt':
                    creationflags = subprocess.CREATE_NO_WINDOW
                subprocess.Popen(cmd, creationflags=creationflags)
            except Exception as e:
                print(f"Error saving loop: {e}")
