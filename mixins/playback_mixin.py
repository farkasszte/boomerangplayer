"""
PlaybackMixin — play/pause, frame advance, seeking, file loading, media events.
"""

import os
import subprocess
import json
from PyQt6.QtCore import Qt, QUrl, QTimer, QElapsedTimer, QPointF
from PyQt6.QtMultimedia import QMediaPlayer
from qfluentwidgets import FluentIcon
from utils import get_resource_path, format_time
from translations import tr


class PlaybackMixin:
    # ------------------------------------------------------------------ #
    # File / video loading                                                 #
    # ------------------------------------------------------------------ #

    def open_file(self):
        from PyQt6.QtWidgets import QFileDialog
        fileNames, _ = QFileDialog.getOpenFileNames(
            self, tr('add_files_title'), "",
            f"{tr('media_files')} (*.mp4 *.mkv *.avi *.mov *.jpg *.jpeg *.png *.bmp *.webp *.tiff)"
        )
        if fileNames:
            self.add_files_to_playlist(fileNames)
            if self.mediaPlayer.playbackState() == QMediaPlayer.PlaybackState.StoppedState:
                self.load_video(fileNames[0])

    def add_folder_contents(self, type="video"):
        from PyQt6.QtWidgets import QFileDialog
        folder = QFileDialog.getExistingDirectory(self, tr('select_folder'))
        if not folder:
            return

        if type == "video":
            exts = ('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.m4v')
        else:
            exts = ('.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff')

        files = [
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if f.lower().endswith(exts)
        ]

        if files:
            self.add_files_to_playlist(sorted(files))
            if self.mediaPlayer.playbackState() == QMediaPlayer.PlaybackState.StoppedState:
                self.load_video(files[0])

    def load_video(self, filePath):
        self.save_current_markers()

        try:
            self.is_loading_video = True
            self.currentFilePath = filePath
            self.last_transform_state = None
            if hasattr(self, 'initial_fit_done'):
                delattr(self, 'initial_fit_done')

            is_image = filePath.lower().endswith(
                ('.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff')
            )

            if is_image:
                self.cleanup_cache()
                self.cached_frame_dict = {0: filePath}
                self.cached_file_path = filePath
                self.current_cache_index = 0
                self.fps = 1.0
                self.total_frames = 0
                self.sync_progress_bar()
                self.update_pixmap_from_cache()
                self.apply_transformations(fit=True)
                if hasattr(self, '_apply_file_saved_zoom'):
                    self._apply_file_saved_zoom()
                self.mediaPlayer.stop()
                self.setWindowTitle(os.path.basename(filePath))
            else:
                fps, duration_ms, total_frames = self.get_video_info(filePath)
                if fps > 0:
                    self.fps = fps
                    print(f"ffprobe detected FPS: {self.fps}")

                self.current_cache_index = 0
                self.update_pixmap_from_cache()

                self.mediaPlayer.setSource(QUrl.fromLocalFile(filePath))
                self.setWindowTitle(os.path.basename(filePath))

                # Store ffprobe results for frame-accurate timing
                self.ffprobe_fps = fps
                self.ffprobe_duration = duration_ms
                self.ffprobe_nb_frames = total_frames
                self.fps = fps
                self.total_frames = total_frames

                self.update_duration(duration_ms)

                self.mediaPlayer.pause()
                self.playButton.setIcon(FluentIcon.PLAY)
                self.playButton.setEnabled(True)

                self.start_full_extraction()

            self.load_markers_for_current()

        except Exception as e:
            print(f"Error opening file: {e}")

    def get_video_info(self, file_path):
        """Get FPS and duration using ffprobe."""
        try:
            ffprobe_path = get_resource_path("ffprobe.exe" if os.name == 'nt' else "ffprobe")
            if not os.path.exists(ffprobe_path):
                ffprobe_path = "ffprobe"

            cmd = [
                ffprobe_path, "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=avg_frame_rate,duration,nb_frames",
                "-of", "json", file_path
            ]

            creationflags = 0
            if os.name == 'nt':
                creationflags = subprocess.CREATE_NO_WINDOW

            result = subprocess.check_output(cmd, creationflags=creationflags).decode('utf-8')
            data = json.loads(result)
            if not data.get('streams'):
                return 30.0, 0, 0

            stream = data['streams'][0]
            fmt = data.get('format', {})
            
            # 1. Get FPS (Prefer r_frame_rate for playback timing)
            fps_str = stream.get('r_frame_rate', stream.get('avg_frame_rate', '30/1'))
            if '/' in fps_str:
                num, den = map(int, fps_str.split('/'))
                fps = num / den if den != 0 else 30.0
            else:
                fps = float(fps_str)
                
            # 2. Get Duration (Stream duration is for video, format is for file)
            s_dur = stream.get('duration')
            f_dur = fmt.get('duration')
            duration = float(s_dur if s_dur is not None else (f_dur if f_dur is not None else 0))
            
            # 3. Get Number of Frames
            nb_frames = int(stream.get('nb_frames', 0))
            if nb_frames == 0 and duration > 0:
                nb_frames = int(duration * fps)
            
            return fps, duration * 1000, nb_frames
        except Exception as e:
            print(f"ffprobe error: {e}")
            return 30.0, 0, 0

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
            self.mediaPlayer.play()
        else:
            self.mediaPlayer.pause()
            self.audioOutput.setMuted(True)

    def stop_playback(self):
        self.is_playing = False
        self.playbackTimer.stop()
        self.mediaPlayer.pause()
        self.update_play_icons()

    # ------------------------------------------------------------------ #
    # Frame advance (timer callback)                                       #
    # ------------------------------------------------------------------ #

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
                    if loop_mode == 3:  # Ping-pong
                        self.isForward = False
                        self.current_cache_index = end_frame - (self.current_cache_index - end_frame)
                    else:
                        self.current_cache_index = start_frame + (self.current_cache_index - end_frame - 1)

                    if self.fps > 0:
                        self.mediaPlayer.setPosition(
                            int(self.current_cache_index * 1000 / self.fps)
                        )
                        self.set_volume(self.audioOutput.volume() * 100)
                else:
                    self.current_cache_index = end_frame
                    self.stop_playback()
        else:
            self.current_cache_index -= int_delta
            if self.current_cache_index < start_frame:
                if loop_mode == 3:  # Ping-pong
                    self.isForward = True
                    self.current_cache_index = start_frame + (start_frame - self.current_cache_index)
                    self.set_volume(self.audioOutput.volume() * 100)
                    if self.fps > 0:
                        self.mediaPlayer.setPosition(
                            int(self.current_cache_index * 1000 / self.fps)
                        )
                elif loop_mode == 2:  # Backward loop
                    self.current_cache_index = end_frame - (start_frame - self.current_cache_index - 1)
                else:
                    self.current_cache_index = start_frame
                    self.stop_playback()

        self.current_cache_index = max(0, min(max(0, self.total_frames - 1), self.current_cache_index))

        if self.current_cache_index not in self.cached_frame_dict:
            self.was_playing_before_cache_miss = self.is_playing
            self.stop_playback()
            self.loadingOverlay.show()
            self.request_frame_extraction(self.current_cache_index, force=True)
            return

        self.update_pixmap_from_cache()
        self.check_sliding_window()
        self.sync_progress_bar()

    # ------------------------------------------------------------------ #
    # Seeking / stepping                                                   #
    # ------------------------------------------------------------------ #

    def set_position(self, index):
        self.current_cache_index = index
        self.needs_range_update = True
        self.isForward = True

        if index not in getattr(self, 'cached_frame_dict', {}):
            self.loadingOverlay.show()
            self.request_frame_extraction(index, force=True)
        else:
            self.update_pixmap_from_cache()
            self.check_sliding_window()

        if self.fps > 0:
            ms = int((index * 1000) / self.fps)
            self.currentTimeLabel.setText(format_time(ms))

    def on_slider_pressed(self):
        self.is_scrubbing = True

    def on_slider_released(self):
        self.is_scrubbing = False
        if self.fps > 0:
            pos = int((self.current_cache_index * 1000) / self.fps)
            self.mediaPlayer.setPosition(pos)
        self.update_pixmap_from_cache()

    def step_frame(self, direction):
        self.current_cache_index += direction
        max_frame = self.progressBar.maximum() if self.progressBar.maximum() > 0 else 0
        self.current_cache_index = max(0, min(max_frame, self.current_cache_index))

        if self.current_cache_index not in getattr(self, 'cached_frame_dict', {}):
            self.loadingOverlay.show()
            self.request_frame_extraction(self.current_cache_index, force=True)
            return

        self.update_pixmap_from_cache()
        self.check_sliding_window()

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

    def update_duration(self, duration):
        # Use ffprobe nb_frames if available to prevent drift/over-estimation
        if hasattr(self, 'ffprobe_nb_frames') and self.ffprobe_nb_frames > 0:
            self.total_frames = self.ffprobe_nb_frames
            # Sync displayed duration with actual frames
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
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            self.handle_metadata_change()
            if self.view and self.pixmapItem and self.last_transform_state is None:
                self.apply_transformations(fit=True)
                if hasattr(self, '_apply_file_saved_zoom'):
                    self._apply_file_saved_zoom()

    def handle_metadata_change(self):
        # We generally trust ffprobe more for playback FPS/Frames,
        # but QMediaPlayer can give us clues about runtime duration.
        pass

    def on_speed_slider_changed(self, value):
        snapped = round(value / 5) * 5
        if snapped != value:
            self.speedSlider.setValue(snapped)
            return
        rate = snapped / 100.0
        self.mediaPlayer.setPlaybackRate(rate)
        self.speedValueLabel.setText(f"{snapped}%")

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

    def _apply_file_saved_zoom(self):
        if not self.currentFilePath:
            return
        data = self.playlistData.get(self.currentFilePath, {})
        zoom = data.get('zoom', 100)
        center_x = data.get('centerX', data.get('scrollX', None))
        center_y = data.get('centerY', data.get('scrollY', None))
        
        current_file = self.currentFilePath
        
        QTimer.singleShot(100, lambda: self._execute_file_saved_zoom(zoom, center_x, center_y, current_file))

    def _execute_file_saved_zoom(self, zoom, center_x, center_y, target_file):
        if self.currentFilePath != target_file:
            self.is_loading_video = False
            return
            
        val = int(zoom * 100) if zoom < 10 else int(zoom) # Support both ratio and percentage formats
        self.update_zoom(val)
        
        if hasattr(self, 'view') and self.view:
            if center_x is not None and center_y is not None:
                self.view.centerOn(QPointF(center_x, center_y))
            elif hasattr(self, 'pixmapItem') and self.pixmapItem:
                self.view.centerOn(self.pixmapItem.boundingRect().center())
            
        self.is_loading_video = False

    def _save_scroll_x_state(self, val):
        if getattr(self, 'is_loading_video', False):
            return
        if hasattr(self, 'currentFilePath') and self.currentFilePath:
            if self.currentFilePath not in self.playlistData:
                self.playlistData[self.currentFilePath] = {}
            self.playlistData[self.currentFilePath]['scrollX'] = val

    def _save_scroll_y_state(self, val):
        if getattr(self, 'is_loading_video', False):
            return
        if hasattr(self, 'currentFilePath') and self.currentFilePath:
            if self.currentFilePath not in self.playlistData:
                self.playlistData[self.currentFilePath] = {}
            self.playlistData[self.currentFilePath]['scrollY'] = val

    def on_user_zoom_changed(self, zoom_level):
        if getattr(self, 'is_loading_video', False):
            return
        val = int(zoom_level * 100)
        if hasattr(self, 'currentFilePath') and self.currentFilePath:
            if self.currentFilePath not in self.playlistData:
                self.playlistData[self.currentFilePath] = {}
            self.playlistData[self.currentFilePath]['zoom'] = val
            
        self.sync_zoom_ui(zoom_level)

