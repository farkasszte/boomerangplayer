"""
CacheMixin — frame extraction and cache management.
"""

import os
import tempfile
import shutil
from PyQt6.QtGui import QImage, QPixmap


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QMainWindow, QLabel, QSlider
    from PyQt6.QtCore import QThread
    from config import Configuration
    from components import GPUPixmapItem
    CacheMixinBase = QMainWindow
else:
    CacheMixinBase = object


class CacheMixin(CacheMixinBase):
    if TYPE_CHECKING:
        current_temp_dir: str | None
        cached_frame_dict: dict
        last_extracted_center: int
        pixmapItem: GPUPixmapItem | None
        currentFilePath: str | None
        total_frames: int
        cache_window_half: int
        video_codec: str | None
        config: Configuration
        fps: float
        progressBar: QSlider
        playlistData: dict
        loadingOverlay: QLabel
        brightnessSlider: QSlider
        contrastSlider: QSlider
        gammaSlider: QSlider
        saturationSlider: QSlider
        isMirrored: bool
        isMirroredVertical: bool
        rotationAngle: int
        frameLabel: QLabel
        currentTimeLabel: QLabel
        is_playing: bool
        is_scrubbing: bool
        extraction_thread: QThread | None
    # ------------------------------------------------------------------ #
    # Cache housekeeping                                                   #
    # ------------------------------------------------------------------ #

    def cleanup_cache(self, keep_extracted_video=False):
        if hasattr(self, 'extraction_thread') and self.extraction_thread and self.extraction_thread.isRunning():
            
            self.extraction_thread.cancel()
            self.extraction_thread.wait()

        if self.current_temp_dir:
            if os.path.exists(self.current_temp_dir):
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
            else:
                self.current_temp_dir = None
        self.cached_frame_dict = {}
        self.last_extracted_center = -1
        self._last_rendered_index = -1
        self._last_base_index = -1
        if hasattr(self, '_current_base_image'):
            self._current_base_image = QImage()
        pixmap_item = getattr(self, 'pixmapItem', None)
        if pixmap_item is not None:
            pixmap_item.setPixmap(QPixmap())

    # ------------------------------------------------------------------ #
    # Extraction requests                                                  #
    # ------------------------------------------------------------------ #

    def request_frame_extraction(self, center_frame, force=False):
        if not self.currentFilePath:
            return

        if self.extraction_thread and self.extraction_thread.isRunning():
            t_start = getattr(self.extraction_thread, 'player_start', -1)
            t_end = getattr(self.extraction_thread, 'player_end', -1)
            if t_start <= center_frame <= t_end:
                print(f"[request_frame_extraction] Running thread already covers center={center_frame} (range {t_start}-{t_end}). Letting it run.")
                self.last_extracted_center = center_frame
                return

            if force:
                print(f"[request_frame_extraction] Cancelling running extraction thread for force request (center={center_frame}, running range={t_start}-{t_end}).")
                try:
                    self.extraction_thread.finished_extraction.disconnect()
                except TypeError:
                    pass
                
                self.extraction_thread.cancel()
                self.extraction_thread.wait()
                self.extraction_thread = None
            else:
                print(f"[request_frame_extraction] Aborted: extraction thread is already running.")
                return  # Already extracting

        divisor = [1, 2, 4, 6][self.config.get('prefetch_chunk_idx', 0)]
        if divisor == 1:
            start_frame = max(0, center_frame - self.cache_window_half)
            end_frame = min(max(0, self.total_frames - 1), center_frame + self.cache_window_half)
            chunk_size = self.cache_window_half * 2
        else:
            total_window = self.cache_window_half * 2
            chunk_size = max(10, total_window // divisor)
            is_forward = getattr(self, 'isForward', True)
            if is_forward:
                backward_buffer = max(5, int(chunk_size * 0.15))
                forward_buffer = chunk_size - backward_buffer
                start_frame = max(0, center_frame - backward_buffer)
                end_frame = min(max(0, self.total_frames - 1), center_frame + forward_buffer)
            else:
                forward_buffer = max(5, int(chunk_size * 0.15))
                backward_buffer = chunk_size - forward_buffer
                start_frame = max(0, center_frame - backward_buffer)
                end_frame = min(max(0, self.total_frames - 1), center_frame + forward_buffer)

        num_frames = end_frame - start_frame + 1
        if num_frames <= 0:
            return

        # Don't extract if we already have this exact range (optimisation)
        threshold = max(5, chunk_size // 4)
        if (not force and self.last_extracted_center != -1
                and abs(self.last_extracted_center - center_frame) < threshold):
            print(f"[request_frame_extraction] Aborted: optimization threshold met (last={self.last_extracted_center}, current={center_frame}, threshold={threshold}).")
            return

        # Skip extraction for frames already in cache
        missing = [i for i in range(start_frame, start_frame + num_frames)
                   if i not in self.cached_frame_dict]
        if not missing:
            print(f"[request_frame_extraction] All {num_frames} frames already cached. Skipping.")
            self.last_extracted_center = center_frame
            return

        # Store original player range before narrowing for the thread range check
        player_range_start = start_frame
        player_range_end = end_frame

        # Narrow extraction to only missing frames
        start_frame = missing[0]
        num_frames = missing[-1] - missing[0] + 1

        self.last_extracted_center = center_frame

        if not self.current_temp_dir:
            import uuid
            self.current_temp_dir = os.path.join(tempfile.gettempdir(), f"mem_cache_{uuid.uuid4().hex}")

        video_path = getattr(self, 'currentVideoPath', self.currentFilePath)

        # If it's a motion photo, player frame 0 is the original photo (already cached).
        # We only extract player frames >= 1 from the video.
        actual_start_frame = start_frame
        actual_num_frames = num_frames
        start_number = None
        if getattr(self, 'is_motion_photo', False):
            actual_start_player = max(1, start_frame)
            actual_end_player = start_frame + num_frames - 1
            if actual_start_player > actual_end_player:
                return  # Nothing to extract from the video
            actual_start_frame = actual_start_player - 1
            actual_num_frames = actual_end_player - actual_start_player + 1
            start_number = actual_start_player

        from workers.threads import FrameExtractionThread
        gpu_enabled = self.config.get('gpu_acceleration', False)
        qv_value = self.config.get('qv_value', 2)
        print(f"[request_frame_extraction] Starting FrameExtractionThread: file={video_path}, start={actual_start_frame}, num={actual_num_frames}, temp_dir={self.current_temp_dir}, qv_value={qv_value}")
        self.extraction_thread = FrameExtractionThread(
            video_path,
            actual_start_frame,
            actual_num_frames,
            self.fps,
            self.current_temp_dir,
            self,
            gpu_enabled=gpu_enabled,
            start_number=start_number,
            video_codec=self.video_codec,
            qv_value=qv_value,
            is_hdr=getattr(self, 'is_hdr', False),
            color_transfer=getattr(self, 'color_transfer', "")
        )
        
        self.extraction_thread.player_start = player_range_start
        
        self.extraction_thread.player_end = player_range_end
        self.extraction_thread.finished_extraction.connect(self.on_extraction_finished)
        self.extraction_thread.start()

    def start_full_extraction(self):
        if not self.currentFilePath:
            return

        self.cleanup_cache(keep_extracted_video=True)
        if getattr(self, 'is_playing', False):
            self.loadingOverlay.show()

        data = self.playlistData.get(self.currentFilePath, {})
        loop_mode = data.get('loopMode', self.loopCombo.currentIndex())
        if loop_mode == 2:
            start_pos = max(0, self.total_frames - 1)
        else:
            start_pos = data.get('startFrame', 0)
        self.current_cache_index = start_pos
        
        # If it's a motion photo, cache frame 0 as the high-res photo path
        if getattr(self, 'is_motion_photo', False):
            
            self.cached_frame_dict[0] = self.motion_photo_original_path

        if start_pos in self.cached_frame_dict:
            # We already have this frame in cache (e.g. frame 0 of motion photo)
            self.update_pixmap_from_cache()
            self.loadingOverlay.hide()
            
            # Silently trigger background sliding window extraction starting from start_pos
            self.last_extracted_center = -1
            self.request_frame_extraction(start_pos, force=True)
            return

        # Two-stage extraction: extract exactly 1 frame instantly
        if not self.current_temp_dir:
            import uuid
            self.current_temp_dir = os.path.join(tempfile.gettempdir(), f"mem_cache_{uuid.uuid4().hex}")
            
        video_path = getattr(self, 'currentVideoPath', self.currentFilePath)

        # Map start_pos to the correct video frame and player index if motion photo
        actual_start_frame = start_pos
        start_number = None
        if getattr(self, 'is_motion_photo', False) and start_pos >= 1:
            actual_start_frame = start_pos - 1
            start_number = start_pos

        from workers.threads import FrameExtractionThread
        gpu_enabled = self.config.get('gpu_acceleration', False)
        qv_value = self.config.get('qv_value', 2)
        self.extraction_thread = FrameExtractionThread(
            video_path,
            actual_start_frame,
            1,  # Only 1 frame!
            self.fps,
            self.current_temp_dir,
            self,
            gpu_enabled=gpu_enabled,
            start_number=start_number,
            video_codec=self.video_codec,
            qv_value=qv_value,
            is_hdr=getattr(self, 'is_hdr', False),
            color_transfer=getattr(self, 'color_transfer', "")
        )
        
        self.extraction_thread.player_start = start_pos
        
        self.extraction_thread.player_end = start_pos
        self.extraction_thread.finished_extraction.connect(self.on_first_frame_extracted)
        self.extraction_thread.start()

    def on_first_frame_extracted(self, frame_dict, temp_dir, start_frame, num_frames):
        path_safe = self.currentFilePath.encode('ascii', errors='replace').decode('ascii') if self.currentFilePath else ""
        print(f"[on_first_frame_extracted] Called with {len(frame_dict) if frame_dict else 0} frames, temp_dir={temp_dir}, currentFilePath={path_safe}")
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
        print(f"[on_first_frame_extracted] Triggering request_frame_extraction for current_cache_index={self.current_cache_index}")
        self.request_frame_extraction(self.current_cache_index, force=True)

        if getattr(self, 'autoplay_next', False):
            self.autoplay_next = False
            loop_mode = self.loopCombo.currentIndex()
            if loop_mode == 2:
                self.isForward = False
            else:
                self.isForward = True
            if hasattr(self, '_start_playback'):
                self._start_playback()
        elif getattr(self, 'was_playing_before_cache_miss', False):
            self.was_playing_before_cache_miss = False
            if hasattr(self, '_start_playback'):
                self._start_playback()

    def check_sliding_window(self):
        if self.last_extracted_center == -1:
            return

        divisor = [1, 2, 4, 6][self.config.get('prefetch_chunk_idx', 0)]
        if divisor == 1:
            chunk_size = self.cache_window_half * 2
        else:
            chunk_size = max(10, (self.cache_window_half * 2) // divisor)
        threshold = max(5, chunk_size // 4)

        dist = abs(self.current_cache_index - self.last_extracted_center)
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

        # Prune old frames to save disk/RAM (skip for short videos that fit entirely in cache)
        if self.total_frames > self.cache_window_half * 2:
            center = self.last_extracted_center
            prune_threshold = int(self.cache_window_half * 1.5)
            keys_to_delete = [k for k in new_dict if abs(k - center) > prune_threshold and (not getattr(self, 'is_motion_photo', False) or k != 0)]

            for k in keys_to_delete:
                val = new_dict[k]
                if isinstance(val, str):
                    try:
                        os.remove(val)
                    except OSError:
                        pass
                del new_dict[k]

        self.cached_frame_dict = new_dict

        self.loadingOverlay.hide()

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
            if hasattr(self, '_start_playback'):
                self._start_playback()

    # ------------------------------------------------------------------ #
    # Progress bar sync                                                    #
    # ------------------------------------------------------------------ #

    def sync_progress_bar(self):
        if not self.currentFilePath:
            return

        self.progressBar.blockSignals(True)

        is_loop = getattr(self, 'is_zoomed_loop', False)
        is_window = getattr(self, 'is_zoomed_window', False)

        if is_loop:
            self.progressBar.set_zoom_mode('loop')
            start_f, end_f = self.get_active_loop_range()
            self.progressBar.setRange(start_f, max(start_f, end_f))
        elif is_window:
            self.progressBar.set_zoom_mode('window')
            anchor = getattr(self, 'zoom_window_anchor', 0)
            half_win = getattr(self, 'cache_window_half', 900)
            start_f = max(0, anchor - half_win)
            end_f = min(max(0, self.total_frames - 1), anchor + half_win)
            self.progressBar.setRange(start_f, max(start_f, end_f))
        else:
            self.progressBar.set_zoom_mode('none')
            self.progressBar.setRange(0, max(0, self.total_frames - 1))

        self.progressBar.setValue(self.current_cache_index)
        self.progressBar.blockSignals(False)
        self.progressBar.update()


