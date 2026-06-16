"""
MarkerMixin — loop markers, loop range, loop mode, and persistence.
"""

import bisect
from translations import tr

# Import refactored dialogs
from mixins.marker_dialogs import MarkersDialog

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
        total_frames: int
        isForward: bool
        isPingPong: bool
        loopCombo: any
        speedSlider: any
        isMirrored: bool
        isMirroredVertical: bool
        rotationAngle: int
        brightnessSlider: any
        contrastSlider: any
        gammaSlider: any
        saturationSlider: any
        hueSlider: any
        tempSlider: any
        exposureSlider: any
        sharpenSlider: any
        blurSlider: any
        invertButton: any
        zoomSlider: any
        zoomValueLabel: any
        view: any
        
        update_loop_frames_label: callable
        save_current_markers: callable
        update_chronometer: callable
        update_pixmap_from_cache: callable
        apply_transformations: callable
        set_position: callable
        reset_adjustments: callable

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
            data['hue'] = self.hueSlider.value() if hasattr(self, 'hueSlider') else 0
            data['temperature'] = self.tempSlider.value() if hasattr(self, 'tempSlider') else 0
            data['exposure'] = self.exposureSlider.value() if hasattr(self, 'exposureSlider') else 0
            data['sharpen'] = self.sharpenSlider.value() if hasattr(self, 'sharpenSlider') else 0
            data['blur'] = self.blurSlider.value() if hasattr(self, 'blurSlider') else 0
            data['invert'] = self.invertButton.isChecked() if hasattr(self, 'invertButton') else False
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
            
            if hasattr(self, 'hueSlider') and self.hueSlider:
                self.hueSlider.setValue(data.get('hue', 0))
            if hasattr(self, 'tempSlider') and self.tempSlider:
                self.tempSlider.setValue(data.get('temperature', 0))
            if hasattr(self, 'exposureSlider') and self.exposureSlider:
                self.exposureSlider.setValue(data.get('exposure', 0))
            if hasattr(self, 'sharpenSlider') and self.sharpenSlider:
                self.sharpenSlider.setValue(data.get('sharpen', 0))
            if hasattr(self, 'blurSlider') and self.blurSlider:
                self.blurSlider.setValue(data.get('blur', 0))
            if hasattr(self, 'invertButton') and self.invertButton:
                self.invertButton.setChecked(data.get('invert', False))

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
