"""
MarkerMixin — loop markers, loop range, loop mode, save/load frame & segment.
"""

import os
import subprocess
import bisect
from PyQt6.QtWidgets import QFileDialog
from PyQt6.QtGui import QImage
from translations import tr


class MarkerMixin:
    # ------------------------------------------------------------------ #
    # Marker CRUD                                                          #
    # ------------------------------------------------------------------ #

    def add_smart_marker(self):
        f = self.current_cache_index
        if f not in self.markers:
            self.markers.append(f)
            self.markers.sort()

        self.needs_range_update = True
        self.progressBar.update_markers(self.markers)
        self.update_loop_frames_label()
        self.save_current_markers()

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

    def clear_loop_markers(self):
        self.markers = []
        self.progressBar.update_markers(self.markers)
        self.update_loop_frames_label()
        self.save_current_markers()

    # ------------------------------------------------------------------ #
    # Loop range calculation                                               #
    # ------------------------------------------------------------------ #

    def get_active_loop_range(self):
        if not self.currentFilePath or self.total_frames <= 0:
            return 0, 0

        f = int(self.current_cache_index)
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
        start_f, end_f = self.get_active_loop_range()
        self.loopFramesLabel.setText(f"[F: {start_f} - {end_f}]")

    # ------------------------------------------------------------------ #
    # Loop mode changes                                                    #
    # ------------------------------------------------------------------ #

    def on_loop_mode_changed(self, index):
        self.isPingPong = (index == 3)
        if index == 2:  # Backward
            self.isForward = False
        else:
            self.isForward = True

        if hasattr(self, 'loopToggle'):
            self.loopToggle.blockSignals(True)
            self.loopToggle.setChecked(index != 0)
            self.loopToggle.blockSignals(False)

        if self.currentFilePath:
            if self.currentFilePath not in self.playlistData:
                self.playlistData[self.currentFilePath] = {'markers': [], 'loopMode': 0}
            self.playlistData[self.currentFilePath]['loopMode'] = index

    def on_loop_switch_toggled(self, checked):
        if checked:
            if self.loopCombo.currentIndex() == 0:
                self.loopCombo.setCurrentIndex(1)
        else:
            self.loopCombo.setCurrentIndex(0)

    # ------------------------------------------------------------------ #
    # Playlist marker persistence                                          #
    # ------------------------------------------------------------------ #

    def save_current_markers(self):
        if self.currentFilePath:
            if self.currentFilePath not in self.playlistData:
                self.playlistData[self.currentFilePath] = {}
                
            data = self.playlistData[self.currentFilePath]
            data['markers'] = self.markers
            data['loopMode'] = self.loopCombo.currentIndex()
            data['speed'] = self.speedSlider.value()
            data['isMirrored'] = self.isMirrored
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
                data['scrollX'] = center.x()
                data['scrollY'] = center.y()
            
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

            self.speedSlider.setValue(data.get('speed', 100))
            self.isMirrored = data.get('isMirrored', False)
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
            self.zoomValueLabel.setText(f"{zoom_val}%")

            self.apply_transformations(fit=True)
            
            # Restore position
            last_pos = data.get('lastPosition', 0)
            if last_pos > 0:
                self.set_position(last_pos)
        else:
            self.markers = []
            self.progressBar.update_markers(self.markers)
            self.needs_range_update = True
            if not self.globalLoopToggle.isChecked():
                self.loopCombo.setCurrentIndex(0)
            self.speedSlider.setValue(100)
            
            # Reset zoom UI immediately
            self.zoomSlider.blockSignals(True)
            self.zoomSlider.setValue(100)
            self.zoomSlider.blockSignals(False)
            self.zoomValueLabel.setText("100%")
            
            self.reset_adjustments()
            self.apply_transformations(fit=True)

        self.update_loop_frames_label()

    # ------------------------------------------------------------------ #
    # Save frame / save loop segment                                       #
    # ------------------------------------------------------------------ #

    def save_current_frame(self):
        if self.current_cache_index not in getattr(self, 'cached_frame_dict', {}):
            return

        fileName, _ = QFileDialog.getSaveFileName(self, "Save Frame", "", "PNG Image (*.png)")
        if fileName:
            img = QImage(self.cached_frame_dict[self.current_cache_index])
            img.save(fileName)

    def save_loop_segment(self):
        if not self.currentFilePath:
            return

        fileName, _ = QFileDialog.getSaveFileName(self, "Save Loop", "", "Video Files (*.mp4 *.mkv)")
        if fileName:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            ffmpeg_path = os.path.join(base_dir, "ffmpeg.exe" if os.name == 'nt' else "ffmpeg")

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
