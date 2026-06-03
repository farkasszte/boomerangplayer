"""
CacheMixin — frame extraction, cache management, pixmap rendering.
"""

import os
import tempfile
import shutil
import numpy as np
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import Qt
from translations import tr


class CacheMixin:
    # ------------------------------------------------------------------ #
    # Cache housekeeping                                                   #
    # ------------------------------------------------------------------ #

    def cleanup_cache(self, keep_extracted_video=False):
        if hasattr(self, 'extraction_thread') and self.extraction_thread and self.extraction_thread.isRunning():
            self.extraction_thread.cancel()
            self.extraction_thread.wait()

        if self.current_temp_dir and os.path.exists(self.current_temp_dir):
            if keep_extracted_video:
                for f in os.listdir(self.current_temp_dir):
                    if f != "extracted_video.mp4":
                        try:
                            fpath = os.path.join(self.current_temp_dir, f)
                            if os.path.isdir(fpath):
                                shutil.rmtree(fpath, ignore_errors=True)
                            else:
                                os.remove(fpath)
                        except OSError:
                            pass
            else:
                try:
                    shutil.rmtree(self.current_temp_dir, ignore_errors=True)
                except OSError:
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
            print(f"[request_frame_extraction] Aborted: extraction thread is already running.")
            return  # Already extracting

        start_frame = max(0, center_frame - self.cache_window_half)
        num_frames = self.cache_window_half * 2

        # Don't extract if we already have this exact range (optimisation)
        threshold = self.cache_window_half // 2
        if (not force and self.last_extracted_center != -1
                and abs(self.last_extracted_center - center_frame) < threshold):
            print(f"[request_frame_extraction] Aborted: optimization threshold met (last={self.last_extracted_center}, current={center_frame}).")
            return

        self.last_extracted_center = center_frame

        if not self.current_temp_dir:
            import tempfile
            self.current_temp_dir = tempfile.mkdtemp(prefix="boomerang_frames_")

        video_path = getattr(self, 'currentVideoPath', self.currentFilePath)

        from mixins.threads import FrameExtractionThread
        gpu_enabled = self.config.get('gpu_acceleration', False)
        print(f"[request_frame_extraction] Starting FrameExtractionThread: file={video_path}, start={start_frame}, num={num_frames}, temp_dir={self.current_temp_dir}")
        self.extraction_thread = FrameExtractionThread(
            video_path,
            start_frame,
            num_frames,
            self.fps,
            self.current_temp_dir,
            self,
            gpu_enabled=gpu_enabled
        )
        self.extraction_thread.finished_extraction.connect(self.on_extraction_finished)
        self.extraction_thread.start()

    def start_full_extraction(self):
        if not self.currentFilePath:
            return

        self.cleanup_cache(keep_extracted_video=True)
        self.loadingOverlay.show()

        data = self.playlistData.get(self.currentFilePath, {})
        start_pos = data.get('startFrame', 0)
        self.current_cache_index = start_pos
        
        # Two-stage extraction: extract exactly 1 frame instantly
        if not self.current_temp_dir:
            import tempfile
            self.current_temp_dir = tempfile.mkdtemp(prefix="boomerang_frames_")
            
        video_path = getattr(self, 'currentVideoPath', self.currentFilePath)

        from mixins.threads import FrameExtractionThread
        gpu_enabled = self.config.get('gpu_acceleration', False)
        self.extraction_thread = FrameExtractionThread(
            video_path,
            start_pos,
            1,  # Only 1 frame!
            self.fps,
            self.current_temp_dir,
            self,
            gpu_enabled=gpu_enabled
        )
        self.extraction_thread.finished_extraction.connect(self.on_first_frame_extracted)
        self.extraction_thread.start()

    def on_first_frame_extracted(self, frame_dict, temp_dir, start_frame, num_frames):
        print(f"[on_first_frame_extracted] Called with {len(frame_dict) if frame_dict else 0} frames, temp_dir={temp_dir}, currentFilePath={self.currentFilePath}")
        if not self.currentFilePath or not self.extraction_thread or temp_dir != self.current_temp_dir:
            print("[on_first_frame_extracted] Early abort: invalid file path, missing thread, or temp_dir mismatch.")
            self.loadingOverlay.hide()
            return

        if frame_dict:
            self.cached_frame_dict = {**self.cached_frame_dict, **frame_dict}
            self.cached_file_path = self.currentFilePath
            self.update_pixmap_from_cache()

            fit_needed = not hasattr(self, 'initial_fit_done')
            if fit_needed:
                self.initial_fit_done = True
                self.apply_transformations(fit=True)
                if hasattr(self, '_apply_file_saved_zoom'):
                    self._apply_file_saved_zoom()

            self.sync_progress_bar()

        self.loadingOverlay.hide()
        
        # Safely wait for the first-stage thread to completely exit so that isRunning() returns False
        if self.extraction_thread:
            self.extraction_thread.wait()
            self.extraction_thread = None
            
        # Silently trigger the background sliding window cache extraction
        self.last_extracted_center = -1
        print(f"[on_first_frame_extracted] Triggering request_frame_extraction for start_frame={start_frame}")
        self.request_frame_extraction(start_frame, force=True)

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
        print(f"[on_extraction_finished] Called with {len(frame_dict) if frame_dict else 0} frames, temp_dir={temp_dir}, currentFilePath={self.currentFilePath}")
        if temp_dir != self.current_temp_dir:
            print(f"[on_extraction_finished] Stale callback ignored. temp_dir={temp_dir}, current_temp_dir={self.current_temp_dir}")
            return

        if not frame_dict:
            print("[on_extraction_finished] Frame dict is empty.")
            self.loadingOverlay.hide()
            if self.extraction_thread:
                self.extraction_thread.wait()
                self.extraction_thread = None
            return

        # Atomic swap: build the new dict, prune, then assign in one shot
        new_dict = {**self.cached_frame_dict, **frame_dict}
        self.cached_file_path = self.currentFilePath

        # Prune old frames to save disk/RAM
        center = self.last_extracted_center
        prune_threshold = self.cache_window_half * 1.5
        keys_to_delete = [k for k in new_dict if abs(k - center) > prune_threshold]

        for k in keys_to_delete:
            try:
                os.remove(new_dict[k])
            except OSError:
                pass
            del new_dict[k]

        self.cached_frame_dict = new_dict

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
            if hasattr(self, '_apply_file_saved_zoom'):
                self._apply_file_saved_zoom()

        self.sync_progress_bar()

        # Safely wait for the thread to completely exit and clear reference
        if self.extraction_thread:
            self.extraction_thread.wait()
            self.extraction_thread = None

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

        is_zoomed = getattr(self, 'is_zoomed_nav', False)
        self.progressBar.set_zoomed(is_zoomed)

        if is_zoomed:
            start_f, end_f = self.get_active_loop_range()
            self.progressBar.setRange(start_f, max(start_f, end_f))
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
        
        self.isMirrored = False
        self.isMirroredVertical = False
        self.rotationAngle = 0
        
        if hasattr(self, '_last_adj_params'):
            delattr(self, '_last_adj_params')
        self.update_pixmap_from_cache()
        self.apply_transformations(fit=True)
        if not getattr(self, 'is_loading_video', False):
            self.save_current_markers()

    def _get_adj_lut(self, b, c, g):
        # Cache the LUT to avoid re-calculation for every frame
        params = (b, c, g)
        if hasattr(self, '_last_adj_params') and self._last_adj_params == params:
            return self._adj_lut
        
        # Create LUT: 0-255 mapping
        x = np.arange(256, dtype=np.float32)
        
        # Apply Contrast and Brightness
        lut = x * c + b
        
        # Apply Gamma
        if g != 1.0:
            lut = np.clip(lut, 0, 255)
            lut = 255.0 * np.power(lut / 255.0, 1.0 / g)
            
        self._adj_lut = np.clip(lut, 0, 255).astype(np.uint8)
        self._last_adj_params = params
        return self._adj_lut

    def update_pixmap_from_cache(self):
        if self.current_cache_index in getattr(self, 'cached_frame_dict', {}):
            file_path = self.cached_frame_dict[self.current_cache_index]
            pixmap = QPixmap(file_path)

            # Apply image adjustments
            b = self.brightnessSlider.value()
            c = self.contrastSlider.value() / 100.0
            g = self.gammaSlider.value() / 100.0
            s = self.saturationSlider.value() / 100.0

            gpu_enabled = self.config.get('gpu_acceleration', False)
            if gpu_enabled:
                if hasattr(self, 'pixmapItem'):
                    self.pixmapItem.update_params(b, c, g, s)
            elif b != 0 or c != 1.0 or g != 1.0 or s != 1.0:
                img = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
                width, height = img.width(), img.height()

                ptr = img.bits()
                ptr.setsize(img.sizeInBytes())
                arr = np.frombuffer(ptr, np.uint8).reshape((height, width, 4))

                if b != 0 or c != 1.0 or g != 1.0:
                    lut = self._get_adj_lut(b, c, g)
                    arr[:, :, :3] = lut[arr[:, :, :3]]

                if s != 1.0:
                    b_chan = arr[:, :, 0].astype(np.float32)
                    g_chan = arr[:, :, 1].astype(np.float32)
                    r_chan = arr[:, :, 2].astype(np.float32)
                    
                    gray = (0.299 * r_chan + 0.587 * g_chan + 0.114 * b_chan)
                    
                    arr[:, :, 0] = np.clip(gray + s * (b_chan - gray), 0, 255).astype(np.uint8)
                    arr[:, :, 1] = np.clip(gray + s * (g_chan - gray), 0, 255).astype(np.uint8)
                    arr[:, :, 2] = np.clip(gray + s * (r_chan - gray), 0, 255).astype(np.uint8)

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
