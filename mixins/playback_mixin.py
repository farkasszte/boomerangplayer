"""
PlaybackMixin — play/pause, frame advance, seeking, media events with Multi-Instance UDP Sync hooks.
"""

import os
from PyQt6.QtCore import Qt, QTimer, QElapsedTimer
from PyQt6.QtMultimedia import QMediaPlayer
from utils import format_time


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QMainWindow, QPushButton, QSlider
    from PyQt6.QtMultimedia import QMediaPlayer
    from config import Configuration
    PlaybackMixinBase = QMainWindow
else:
    PlaybackMixinBase = object


class PlaybackMixin(PlaybackMixinBase):
    if TYPE_CHECKING:
        is_playing: bool
        was_playing_before_cache_miss: bool
        frame_accumulator: float
        last_advance_ms: int
        mediaPlayer: QMediaPlayer
        currentFilePath: str | None
        currentVideoPath: str | None
        video_codec: str | None
        last_transform_state: tuple | None
        is_motion_photo: bool
        motion_photo_original_path: str | None
        cached_frame_dict: dict
        current_cache_index: int
        fps: float
        total_frames: int
        playButton: QPushButton
        config: Configuration
        speedSlider: QSlider
        
        cleanup_cache: callable
        save_current_markers: callable
        update_pixmap_from_cache: callable
        apply_transformations: callable
        sync_progress_bar: callable
        start_full_extraction: callable
        load_markers_for_current: callable


    # ------------------------------------------------------------------ #
    # Play / pause / stop                                                  #
    # ------------------------------------------------------------------ #

    def play_pause(self):
        self._toggle_playback(True)

    def play_pause_backward(self):
        self._toggle_playback(False)

    def _toggle_playback(self, target_forward):
        if self.is_playing:
            if self.isForward == target_forward:
                self.stop_playback()
            else:
                self.stop_playback()
                self.isForward = target_forward
                self._start_playback()
        else:
            self.isForward = target_forward
            self._start_playback()

    def _start_playback(self):
        if not getattr(self, 'cached_frame_dict', None):
            return
        self.is_playing = True
        self.update_play_icons()

        self.frame_accumulator = 0.0
        
        self.elapsedTimer.start()
        self.last_advance_ms = 0

        
        self.playbackTimer.start(10)

        if self.isForward and self.fps > 0:
            audio_pos = int((self.current_cache_index * 1000) / self.fps)
            self.mediaPlayer.setPosition(audio_pos)
            
            self.audioOutput.setMuted(self.userMutedIntent)
            # Ensure the playback rate is set before calling play
            rate = self.speedSlider.value() / 100.0
            self.mediaPlayer.setPlaybackRate(rate)
            self.mediaPlayer.play()
        else:
            self.mediaPlayer.pause()
            
            self.audioOutput.setMuted(True)

        if not getattr(self, '_block_broadcast', False):
            
            self.broadcast_sync_event("play", {"isForward": self.isForward, "speed": self.speedSlider.value()})

    def stop_playback(self):
        self.is_playing = False
        
        self.playbackTimer.stop()
        self.mediaPlayer.pause()
        self.update_play_icons()

        if not getattr(self, '_block_broadcast', False):
            
            self.broadcast_sync_event("pause", None)

    # ------------------------------------------------------------------ #
    # Frame advance (timer callback)                                       #
    # ------------------------------------------------------------------ #

    def handle_loop_cycle(self):
        self.loop_count = getattr(self, 'loop_count', 0) + 1
        if self.config.get('advance_playlist_after_loop', False):
            limit = self.config.get('advance_playlist_loop_count', 1)
            if self.loop_count >= limit:
                self.loop_count = 0
                self.advance_playlist()
                return True
        return False

    def advance_playlist(self):
        if not hasattr(self, 'playlistList') or self.playlistList.count() == 0:
            return
        
        current_idx = -1
        for i in range(self.playlistList.count()):
            item = self.playlistList.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == self.currentFilePath:
                current_idx = i
                break
        
        if current_idx != -1 and current_idx + 1 < self.playlistList.count():
            next_item = self.playlistList.item(current_idx + 1)
            self.playlistList.setCurrentItem(next_item)
            self.autoplay_next = True
            self.load_video(next_item.data(Qt.ItemDataRole.UserRole))
        else:
            self.stop_playback()

    def advance_frame(self):
        if not getattr(self, 'cached_frame_dict', None) or self.fps <= 0:
            return

        
        current_ms = self.elapsedTimer.elapsed()
        delta_ms = current_ms - self.last_advance_ms
        self.last_advance_ms = current_ms

        delta_ms = min(delta_ms, 100)

        
        rate = self.speedSlider.value() / 100.0
        frames_to_advance = (delta_ms * self.fps * rate) / 1000.0

        if not hasattr(self, 'frame_accumulator'):
            self.frame_accumulator = 0.0
        self.frame_accumulator += frames_to_advance

        int_delta = int(self.frame_accumulator)
        if int_delta < 1:
            return

        # Save state in case of a hold-frame cache miss
        old_index = self.current_cache_index
        old_forward = self.isForward
        old_accumulator = self.frame_accumulator

        self.frame_accumulator -= int_delta

        
        loop_mode = self.loopCombo.currentIndex()
        if loop_mode == 0:
            start_frame = 0
            end_frame = max(0, self.total_frames - 1)
        else:
            if getattr(self, 'needs_range_update', True):
                
                self.active_loop_start, self.active_loop_end = self.get_active_loop_range()
                self.needs_range_update = False
                
                self.update_loop_frames_label()

            start_frame = self.active_loop_start
            end_frame = self.active_loop_end

        if self.isForward:
            self.current_cache_index += int_delta
            if self.current_cache_index > end_frame:
                if loop_mode in (1, 2, 3):
                    if loop_mode != 3:
                        if self.handle_loop_cycle():
                            return

                    if loop_mode == 3:  # Ping-pong
                        self.isForward = False
                        self.current_cache_index = end_frame - (self.current_cache_index - end_frame)
                        self.mediaPlayer.pause()
                        
                        self.audioOutput.setMuted(True)
                    else:
                        self.current_cache_index = start_frame + (self.current_cache_index - end_frame - 1)

                    if self.fps > 0:
                        self.mediaPlayer.setPosition(
                            int(self.current_cache_index * 1000 / self.fps)
                        )
                        
                        self.audioOutput.setVolume(self.audioOutput.volume())
                else:
                    self.current_cache_index = end_frame
                    if self.config.get('advance_playlist_after_loop', False):
                        self.advance_playlist()
                    else:
                        self.stop_playback()
        else:
            self.current_cache_index -= int_delta
            if self.current_cache_index < start_frame:
                if loop_mode == 3:  # Ping-pong
                    if self.handle_loop_cycle():
                        return

                    self.isForward = True
                    self.current_cache_index = start_frame + (start_frame - self.current_cache_index)
                    
                    self.audioOutput.setVolume(self.audioOutput.volume())
                    if self.fps > 0:
                        self.mediaPlayer.setPosition(
                            int(self.current_cache_index * 1000 / self.fps)
                        )
                        
                        self.audioOutput.setMuted(self.userMutedIntent)
                        # Ensure the playback rate is set before calling play
                        rate = self.speedSlider.value() / 100.0
                        self.mediaPlayer.setPlaybackRate(rate)
                        self.mediaPlayer.play()
                elif loop_mode == 2:  # Backward loop
                    if self.handle_loop_cycle():
                        return

                    self.current_cache_index = end_frame - (start_frame - self.current_cache_index - 1)
                else:
                    self.current_cache_index = start_frame
                    if self.config.get('advance_playlist_after_loop', False):
                        self.advance_playlist()
                    else:
                        self.stop_playback()

        self.current_cache_index = max(0, min(max(0, self.total_frames - 1), self.current_cache_index))

        if self.current_cache_index not in self.cached_frame_dict and not getattr(self, 'is_audio_only', False):
            # Restore state so we don't skip the missing frame once playback resumes
            self.current_cache_index = old_index
            self.isForward = old_forward
            self.frame_accumulator = old_accumulator

            self.was_playing_before_cache_miss = self.is_playing
            self.stop_playback()
            
            self.loadingOverlay.show()

            
            if self.extraction_thread and self.extraction_thread.isRunning():
                t_start = getattr(self.extraction_thread, 'player_start', -1)
                t_end = getattr(self.extraction_thread, 'player_end', -1)
                # Ensure we check the frame we *want* to display, which is old_index + int_delta
                target_frame = old_index + int_delta if old_forward else old_index - int_delta
                if t_start <= target_frame <= t_end:
                    # Thread is already extracting the needed frames. Just wait.
                    return
            
            # Thread is NOT running or NOT covering the needed frame. Force extraction.
            # We request extraction centered on the frame we wanted to reach
            target_frame = old_index + int_delta if old_forward else old_index - int_delta
            
            self.request_frame_extraction(target_frame, force=True)
            return

        self.update_pixmap_from_cache()
        
        self.check_sliding_window()
        self.sync_progress_bar()
        
        self.update_chronometer()

    # ------------------------------------------------------------------ #
    # Seeking / stepping                                                   #
    # ------------------------------------------------------------------ #

    def set_position(self, index):
        self.current_cache_index = index
        self.needs_range_update = True
        self.isForward = True

        if index not in getattr(self, 'cached_frame_dict', {}) and not getattr(self, 'is_audio_only', False):
            
            self.loadingOverlay.show()
            
            self.request_frame_extraction(index, force=True)
        else:
            self.update_pixmap_from_cache()
            
            self.check_sliding_window()
            
            self.update_chronometer()

        if self.fps > 0:
            ms = int((index * 1000) / self.fps)
            
            self.currentTimeLabel.setText(format_time(ms))

        if not getattr(self, '_block_broadcast', False):
            
            self.broadcast_sync_event("seek", index)

    def on_slider_pressed(self):
        self.is_scrubbing = True

    def on_slider_released(self):
        self.is_scrubbing = False
        if self.fps > 0:
            pos = int((self.current_cache_index * 1000) / self.fps)
            self.mediaPlayer.setPosition(pos)
        self.update_pixmap_from_cache()
        
        self.update_chronometer()

    def step_frame(self, direction):
        self.current_cache_index += direction
        
        max_frame = self.progressBar.maximum() if self.progressBar.maximum() > 0 else 0
        self.current_cache_index = max(0, min(max_frame, self.current_cache_index))

        if self.current_cache_index not in getattr(self, 'cached_frame_dict', {}) and not getattr(self, 'is_audio_only', False):
            
            self.loadingOverlay.show()
            
            self.request_frame_extraction(self.current_cache_index, force=True)
            return

        self.update_pixmap_from_cache()
        
        self.check_sliding_window()
        
        self.update_chronometer()

        if not getattr(self, '_block_broadcast', False):
            
            self.broadcast_sync_event("step", direction)

    # ------------------------------------------------------------------ #
    # Media player signal handlers                                        #
    # ------------------------------------------------------------------ #

    def update_play_icons(self):
        if self.is_playing:
            if self.isForward:
                
                self.playButton.setIcon(self.pauseIcon)
                
                self.playBackwardButton.setIcon(self.flippedPlayIcon)
            else:
                
                self.playButton.setIcon(self.normalPlayIcon)
                
                self.playBackwardButton.setIcon(self.pauseIcon)
        else:
            
            self.playButton.setIcon(self.normalPlayIcon)
            
            self.playBackwardButton.setIcon(self.flippedPlayIcon)

    def handle_state_change(self, state):
        is_paused_or_stopped = not self.is_playing
        if hasattr(self, 'stepBackButton'):
            self.stepBackButton.setEnabled(is_paused_or_stopped)
            
            self.stepForwardButton.setEnabled(is_paused_or_stopped)
        self.update_play_icons()

        # Re-apply locked speed when transitioning to playing state
        if state == QMediaPlayer.PlaybackState.PlayingState:
            is_speed_locked = getattr(self, 'isSpeedLocked', False)
            speed_slider = getattr(self, 'speedSlider', None)
            if speed_slider is not None and is_speed_locked:
                speed_val = speed_slider.value()
                self.mediaPlayer.setPlaybackRate(speed_val / 100.0)

    def update_duration(self, duration):
        # Use ffprobe nb_frames if available to prevent drift/over-estimation
        if hasattr(self, 'ffprobe_nb_frames') and self.ffprobe_nb_frames > 0:
            self.total_frames = self.ffprobe_nb_frames
            if self.fps > 0:
                duration = (self.total_frames * 1000.0) / self.fps
        elif self.fps > 0:
            self.total_frames = int((duration / 1000.0) * self.fps)
            
        
        self.totalTimeLabel.setText(format_time(duration))
        self.sync_progress_bar()

        last_valid_frame = max(0, self.total_frames - 1)
        self.markers = [m for m in self.markers if m <= last_valid_frame]
        
        self.progressBar.update_markers(self.markers)
        
        self.update_loop_frames_label()

    def handle_status_change(self, status):
        if status in (QMediaPlayer.MediaStatus.LoadedMedia, QMediaPlayer.MediaStatus.BufferedMedia):
            if status == QMediaPlayer.MediaStatus.LoadedMedia:
                self.handle_metadata_change()
            
            # Apply current speed slider value to the media player
            speed_slider = getattr(self, 'speedSlider', None)
            if speed_slider is not None:
                speed_val = speed_slider.value()
                self.mediaPlayer.setPlaybackRate(speed_val / 100.0)

            
            if self.view and self.pixmapItem and self.last_transform_state is None:
                self.apply_transformations(fit=True)
                if hasattr(self, '_apply_file_saved_zoom'):
                    self._apply_file_saved_zoom()

    def handle_metadata_change(self):
        pass

    def on_speed_slider_changed(self, value):
        snapped = round(value / 5) * 5
        if snapped != value:
            
            self.speedSlider.setValue(snapped)
            return
        rate = snapped / 100.0
        self.mediaPlayer.setPlaybackRate(rate)
        if hasattr(self, 'speedValueLabel') and self.speedValueLabel:
            if hasattr(self.speedValueLabel, 'setValue'):
                self.speedValueLabel.blockSignals(True)
                self.speedValueLabel.setValue(snapped)
                self.speedValueLabel.blockSignals(False)
            else:
                self.speedValueLabel.setText(f"{snapped}%")

        if not getattr(self, '_block_broadcast', False):
            
            self.broadcast_sync_event("speed", snapped)

    # ------------------------------------------------------------------ #
    # Window close                                                         #
    # ------------------------------------------------------------------ #

    def closeEvent(self, event):
        self.cleanup_cache()
        
        try:
            from utils import get_markers_path
            path = get_markers_path()
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            print(f"Error removing markers.json on exit: {e}")
            
        super().closeEvent(event)



    def on_user_zoom_changed(self, zoom_level):
        if self.is_loading_video:
            return
        
        self.sync_zoom_ui(zoom_level)
