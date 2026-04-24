"""
PlaybackMixin — play/pause, frame advance, seeking, file loading, media events.
"""

import os
import subprocess
import json
from PyQt6.QtCore import Qt, QUrl, QTimer, QElapsedTimer
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
            self.currentFilePath = filePath
            self.zoomSlider.setValue(100)
            self.view.set_scroll_state(0, 0)
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

                if duration_ms > 0:
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

            avg_fps = stream.get('avg_frame_rate', '30/1')
            if '/' in avg_fps:
                num, den = map(int, avg_fps.split('/'))
                fps = num / den if den != 0 else 30.0
            else:
                fps = float(avg_fps)

            duration = float(stream.get('duration', 0))
            if duration == 0:
                cmd_fmt = [ffprobe_path, "-v", "error", "-show_entries",
                           "format=duration", "-of", "json", file_path]
                result_fmt = subprocess.check_output(
                    cmd_fmt, creationflags=creationflags
                ).decode('utf-8')
                data_fmt = json.loads(result_fmt)
                duration = float(data_fmt.get('format', {}).get('duration', 0))

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
        if self.is_playing:
            self.stop_playback()
        else:
            self.is_playing = True
            self.playButton.setIcon(FluentIcon.PAUSE)

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
                self.audioOutput.setMuted(True)

    def stop_playback(self):
        self.is_playing = False
        self.playbackTimer.stop()
        self.mediaPlayer.pause()
        self.playButton.setIcon(FluentIcon.PLAY)

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

    def handle_state_change(self, state):
        is_paused_or_stopped = not self.is_playing
        if hasattr(self, 'stepBackButton'):
            self.stepBackButton.setEnabled(is_paused_or_stopped)
            self.stepForwardButton.setEnabled(is_paused_or_stopped)

        if self.is_playing:
            self.playButton.setIcon(FluentIcon.PAUSE)
        else:
            self.playButton.setIcon(FluentIcon.PLAY)

    def update_duration(self, duration):
        if self.fps > 0:
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

    def handle_metadata_change(self):
        from PyQt6.QtMultimedia import QMediaMetaData
        meta = self.mediaPlayer.metaData()
        fps = meta.value(QMediaMetaData.Key.VideoFrameRate)
        if fps and float(fps) > 0:
            self.fps = float(fps)
            print(f"Detected FPS: {self.fps}")
            self.update_loop_frames_label()

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
        super().closeEvent(event)
