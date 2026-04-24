"""
CacheMixin — frame extraction, cache management, pixmap rendering.
"""

import os
import tempfile
import shutil
import numpy as np
from PyQt6.QtGui import QImage, QPixmap
from translations import tr


class CacheMixin:
    # ------------------------------------------------------------------ #
    # Cache housekeeping                                                   #
    # ------------------------------------------------------------------ #

    def cleanup_cache(self):
        if self.current_temp_dir and os.path.exists(self.current_temp_dir):
            try:
                shutil.rmtree(self.current_temp_dir, ignore_errors=True)
            except:
                pass
        self.current_temp_dir = None
        self.cached_frame_dict = {}
        self.last_extracted_center = -1
        if hasattr(self, 'pixmapItem'):
            self.pixmapItem.setPixmap(QPixmap())

    # ------------------------------------------------------------------ #
    # Extraction requests                                                  #
    # ------------------------------------------------------------------ #

    def request_frame_extraction(self, center_frame, force=False):
        if not self.currentFilePath:
            return

        if self.extraction_thread and self.extraction_thread.isRunning():
            return  # Already extracting

        start_frame = max(0, center_frame - self.cache_window_half)
        num_frames = self.cache_window_half * 2

        # Don't extract if we already have this exact range (optimisation)
        threshold = self.cache_window_half // 2
        if (not force and self.last_extracted_center != -1
                and abs(self.last_extracted_center - center_frame) < threshold):
            return

        self.last_extracted_center = center_frame

        if not self.current_temp_dir:
            self.current_temp_dir = tempfile.mkdtemp(prefix="boomerang_frames_")

        from mixins.threads import FrameExtractionThread
        self.extraction_thread = FrameExtractionThread(
            self.currentFilePath,
            start_frame,
            num_frames,
            self.fps,
            self.current_temp_dir,
            self
        )
        self.extraction_thread.finished_extraction.connect(self.on_extraction_finished)
        self.extraction_thread.start()

    def start_full_extraction(self):
        if not self.currentFilePath:
            return

        self.cleanup_cache()
        self.loadingOverlay.show()

        data = self.playlistData.get(self.currentFilePath, {})
        start_pos = data.get('startFrame', 0)
        self.current_cache_index = start_pos
        self.request_frame_extraction(start_pos)

    def check_sliding_window(self):
        if self.last_extracted_center == -1:
            return

        dist = abs(self.current_cache_index - self.last_extracted_center)
        threshold = self.cache_window_half // 2
        if dist > threshold:
            self.request_frame_extraction(self.current_cache_index)

    # ------------------------------------------------------------------ #
    # Extraction callback                                                  #
    # ------------------------------------------------------------------ #

    def on_extraction_finished(self, frame_dict, temp_dir, start_frame, num_frames):
        if not frame_dict:
            self.loadingOverlay.hide()
            return

        self.cached_frame_dict.update(frame_dict)
        self.cached_file_path = self.currentFilePath

        # Prune old frames to save disk/RAM
        keys_to_delete = []
        center = self.last_extracted_center
        prune_threshold = self.cache_window_half * 1.5
        for frame_idx, fpath in self.cached_frame_dict.items():
            if abs(frame_idx - center) > prune_threshold:
                keys_to_delete.append(frame_idx)

        for k in keys_to_delete:
            try:
                os.remove(self.cached_frame_dict[k])
            except:
                pass
            del self.cached_frame_dict[k]

        self.loadingOverlay.hide()
        self.loadingOverlay.setText(
            f"{tr('caching')}: {start_frame} - {start_frame + num_frames}. "
            f"Cache size: {len(self.cached_frame_dict)}"
        )

        fit_needed = not hasattr(self, 'initial_fit_done')
        if fit_needed:
            self.initial_fit_done = True

        self.update_pixmap_from_cache()
        if fit_needed:
            self.apply_transformations(fit=True)

        self.sync_progress_bar()

        if getattr(self, 'was_playing_before_cache_miss', False):
            self.was_playing_before_cache_miss = False
            self.play_pause()

    # ------------------------------------------------------------------ #
    # Progress bar sync                                                    #
    # ------------------------------------------------------------------ #

    def sync_progress_bar(self):
        if not self.currentFilePath:
            return

        self.progressBar.blockSignals(True)

        if getattr(self, 'is_zoomed_nav', False):
            s = getattr(self, 'cache_start', 0)
            e = getattr(self, 'cache_end', self.total_frames - 1)
            self.progressBar.setRange(s, e)
        else:
            self.progressBar.setRange(0, max(0, self.total_frames - 1))

        self.progressBar.setValue(self.current_cache_index)
        self.progressBar.blockSignals(False)
        self.progressBar.update()

    # ------------------------------------------------------------------ #
    # Image adjustments & pixmap rendering                                #
    # ------------------------------------------------------------------ #

    def reset_adjustments(self):
        self.brightnessSlider.setValue(0)
        self.contrastSlider.setValue(100)
        self.gammaSlider.setValue(100)
        self.saturationSlider.setValue(100)
        self.update_pixmap_from_cache()

    def update_pixmap_from_cache(self):
        if self.current_cache_index in getattr(self, 'cached_frame_dict', {}):
            file_path = self.cached_frame_dict[self.current_cache_index]
            pixmap = QPixmap(file_path)

            # Apply image adjustments
            b = self.brightnessSlider.value()
            c = self.contrastSlider.value() / 100.0
            g = self.gammaSlider.value() / 100.0
            s = self.saturationSlider.value() / 100.0

            if b != 0 or c != 1.0 or g != 1.0 or s != 1.0:
                img = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
                width, height = img.width(), img.height()

                ptr = img.bits()
                ptr.setsize(img.sizeInBytes())
                arr = np.frombuffer(ptr, np.uint8).reshape((height, width, 4))

                rgb = arr[:, :, :3].astype(np.float32)

                if c != 1.0 or b != 0:
                    rgb = rgb * c + b

                if g != 1.0:
                    rgb = 255.0 * (np.power(rgb / 255.0, 1.0 / g))

                if s != 1.0:
                    gray = (0.299 * rgb[:, :, 0]
                            + 0.587 * rgb[:, :, 1]
                            + 0.114 * rgb[:, :, 2])
                    gray = np.stack([gray] * 3, axis=-1)
                    rgb = gray + s * (rgb - gray)

                arr[:, :, :3] = np.clip(rgb, 0, 255).astype(np.uint8)
                pixmap = QPixmap.fromImage(img)

            if self.pixmapItem:
                self.pixmapItem.setPixmap(pixmap)
                self.apply_transformations(fit=False)

            if hasattr(self, 'frameLabel'):
                self.frameLabel.setText(
                    f" [F: {self.current_cache_index + 1} / {self.total_frames}]"
                )

        if not self.is_scrubbing:
            self.sync_progress_bar()

        if self.fps > 0:
            pos = int((self.current_cache_index * 1000) / self.fps)
            from utils import format_time
            self.currentTimeLabel.setText(format_time(pos))
