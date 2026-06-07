"""
PlaybackMixin — play/pause, frame advance, seeking, file loading, media events with Multi-Instance UDP Sync hooks.
"""

import os
import subprocess
import json
from PyQt6.QtCore import Qt, QUrl, QTimer, QElapsedTimer, QPointF
from PyQt6.QtMultimedia import QMediaPlayer
from qfluentwidgets import FluentIcon
from utils import get_resource_path, format_time, VERSION, get_embedded_video_offset
from translations import tr


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QMainWindow, QPushButton
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
        
        # pyrefly: ignore [not-a-type]
        cleanup_cache: callable
        # pyrefly: ignore [not-a-type]
        save_current_markers: callable
        # pyrefly: ignore [not-a-type]
        update_pixmap_from_cache: callable
        # pyrefly: ignore [not-a-type]
        apply_transformations: callable
        # pyrefly: ignore [not-a-type]
        sync_progress_bar: callable
        # pyrefly: ignore [not-a-type]
        start_full_extraction: callable
        # pyrefly: ignore [not-a-type]
        load_markers_for_current: callable
    # ------------------------------------------------------------------ #
    # File / video loading                                                 #
    # ------------------------------------------------------------------ #

    def open_file(self):
        from PyQt6.QtWidgets import QFileDialog
        fileNames, _ = QFileDialog.getOpenFileNames(
            self, tr('add_files_title'), "",
            f"{tr('media_files')} (*.mp4 *.mkv *.avi *.mov *.jpg *.jpeg *.png *.bmp *.webp *.tiff);;{tr('json_files')} (*.json);;{tr('bpl_files')} (*.bpl)"
        )
        if fileNames:
            playlist_files = [f for f in fileNames if f.lower().endswith(('.json', '.bpl'))]
            media_files = [f for f in fileNames if not f.lower().endswith(('.json', '.bpl'))]
            
            if playlist_files:
                # pyrefly: ignore [missing-attribute]
                self.load_playlist_by_path(playlist_files[0])
                if media_files:
                    # pyrefly: ignore [missing-attribute]
                    self.add_files_to_playlist(media_files)
            else:
                # pyrefly: ignore [missing-attribute]
                self.add_files_to_playlist(media_files)
                if self.mediaPlayer.playbackState() == QMediaPlayer.PlaybackState.StoppedState:
                    self.load_video(media_files[0])

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
            # pyrefly: ignore [missing-attribute]
            self.add_files_to_playlist(sorted(files))
            if self.mediaPlayer.playbackState() == QMediaPlayer.PlaybackState.StoppedState:
                self.load_video(files[0])

    def load_video(self, filePath):
        was_playing = getattr(self, 'is_playing', False)
        self.stop_playback()
        self.was_playing_before_cache_miss = was_playing
        self.frame_accumulator = 0.0
        self.last_advance_ms = 0

        self.mediaPlayer.setSource(QUrl())
        self.cleanup_cache()
        self.save_current_markers()

        try:
            self.is_loading_video = True
            self.currentFilePath = filePath
            self.currentVideoPath = filePath
            self.video_codec = None
            self.last_transform_state = None
            self.is_motion_photo = False
            self.motion_photo_original_path = None
            if hasattr(self, 'initial_fit_done'):
                delattr(self, 'initial_fit_done')

            is_image = filePath.lower().endswith(
                ('.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff')
            )

            # Check if it has an embedded MP4 video
            embedded_offset = None
            if is_image and filePath.lower().endswith(('.jpg', '.jpeg')):
                embedded_offset = get_embedded_video_offset(filePath)

            if embedded_offset is not None:
                self.is_motion_photo = True
                self.motion_photo_original_path = filePath
                # Create a temporary directory if it doesn't exist
                if not self.current_temp_dir:
                    import tempfile
                    self.current_temp_dir = tempfile.mkdtemp(prefix="boomerang_frames_")
                
                # Extract the video portion
                temp_video_path = os.path.join(self.current_temp_dir, "extracted_video.mp4")
                try:
                    with open(filePath, 'rb') as f:
                        f.seek(embedded_offset)
                        video_data = f.read()
                    with open(temp_video_path, 'wb') as f:
                        f.write(video_data)
                    self.currentVideoPath = temp_video_path
                    is_image = False  # Treat as video now!
                    print(f"Extracted motion photo video to {temp_video_path} (offset: {embedded_offset})")
                except Exception as ex:
                    print(f"Error extracting motion photo video: {ex}")

            if is_image:
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
                self.setWindowTitle(f"Boomerang Player v{VERSION} - {os.path.basename(filePath)}")
            else:
                fps, duration_ms, total_frames = self.get_video_info(self.currentVideoPath)
                if self.is_motion_photo:
                    total_frames += 1

                if fps > 0:
                    self.fps = fps
                    print(f"ffprobe detected FPS: {self.fps}")

                if self.is_motion_photo:
                    self.cached_frame_dict = {0: filePath}
                else:
                    self.cached_frame_dict = {}

                self.current_cache_index = 0
                self.update_pixmap_from_cache()

                self.mediaPlayer.setSource(QUrl.fromLocalFile(self.currentVideoPath))
                if self.is_motion_photo:
                    self.setWindowTitle(f"Boomerang Player v{VERSION} - [Motion Photo] {os.path.basename(filePath)}")
                else:
                    self.setWindowTitle(f"Boomerang Player v{VERSION} - {os.path.basename(filePath)}")

                # Store ffprobe results for frame-accurate timing
                self.ffprobe_fps = fps
                self.ffprobe_duration = duration_ms
                self.ffprobe_nb_frames = total_frames
                self.fps = fps
                self.total_frames = total_frames

                self.update_duration(duration_ms)

                self.mediaPlayer.pause()
                # pyrefly: ignore [bad-argument-type]
                self.playButton.setIcon(FluentIcon.PLAY)
                self.playButton.setEnabled(True)

                self.start_full_extraction()

            self.load_markers_for_current()

        except Exception as e:
            print(f"Error opening file: {e}")
            from qfluentwidgets import InfoBar, InfoBarPosition
            InfoBar.error(
                title=tr('file_info_title'),
                content=f"Error opening file: {e}",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
        finally:
            # pyrefly: ignore [unbound-name]
            if not self.currentFilePath or is_image:
                pass  # Image path: flag cleared by _apply_file_saved_zoom timer
            if not hasattr(self, '_apply_file_saved_zoom'):
                self.is_loading_video = False

    def get_video_info(self, file_path):
        """Get FPS and duration using ffprobe."""
        try:
            ffprobe_path = get_resource_path("ffprobe.exe" if os.name == 'nt' else "ffprobe")
            if not os.path.exists(ffprobe_path):
                ffprobe_path = "ffprobe"

            cmd = [
                ffprobe_path, "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=codec_name,avg_frame_rate,duration,nb_frames:format=duration",
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
            
            # 1. Get FPS
            fps_str = stream.get('r_frame_rate', stream.get('avg_frame_rate', '30/1'))
            if '/' in fps_str:
                num, den = map(int, fps_str.split('/'))
                fps = num / den if den != 0 else 30.0
            else:
                fps = float(fps_str)
                
            # 2. Get Duration
            s_dur = stream.get('duration')
            f_dur = fmt.get('duration')
            duration = float(s_dur if s_dur is not None else (f_dur if f_dur is not None else 0))
            
            # 3. Get Number of Frames
            nb_frames = int(stream.get('nb_frames', 0))
            if nb_frames == 0 and duration > 0:
                nb_frames = int(duration * fps)
            
            codec = stream.get('codec_name', 'unknown')
            self.video_codec = codec
            
            print(f"[get_video_info] {os.path.basename(file_path)}: codec={codec}, fps={fps}, duration={duration}s, nb_frames={nb_frames}")
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
        # pyrefly: ignore [missing-attribute]
        self.elapsedTimer.start()
        self.last_advance_ms = 0

        # pyrefly: ignore [missing-attribute]
        self.playbackTimer.start(10)

        if self.isForward and self.fps > 0:
            audio_pos = int((self.current_cache_index * 1000) / self.fps)
            self.mediaPlayer.setPosition(audio_pos)
            # pyrefly: ignore [missing-attribute]
            self.audioOutput.setMuted(self.userMutedIntent)
            self.mediaPlayer.play()
        else:
            self.mediaPlayer.pause()
            # pyrefly: ignore [missing-attribute]
            self.audioOutput.setMuted(True)

        if not getattr(self, '_block_broadcast', False):
            # pyrefly: ignore [missing-attribute]
            self.broadcast_sync_event("play", {"isForward": self.isForward, "speed": self.speedSlider.value()})

    def stop_playback(self):
        self.is_playing = False
        # pyrefly: ignore [missing-attribute]
        self.playbackTimer.stop()
        self.mediaPlayer.pause()
        self.update_play_icons()

        if not getattr(self, '_block_broadcast', False):
            # pyrefly: ignore [missing-attribute]
            self.broadcast_sync_event("pause", None)

    # ------------------------------------------------------------------ #
    # Frame advance (timer callback)                                       #
    # ------------------------------------------------------------------ #

    def advance_frame(self):
        if not getattr(self, 'cached_frame_dict', None) or self.fps <= 0:
            return

        # pyrefly: ignore [missing-attribute]
        current_ms = self.elapsedTimer.elapsed()
        delta_ms = current_ms - self.last_advance_ms
        self.last_advance_ms = current_ms

        delta_ms = min(delta_ms, 100)

        # pyrefly: ignore [missing-attribute]
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

        # pyrefly: ignore [missing-attribute]
        loop_mode = self.loopCombo.currentIndex()
        if loop_mode == 0:
            start_frame = 0
            end_frame = max(0, self.total_frames - 1)
        else:
            if getattr(self, 'needs_range_update', True):
                # pyrefly: ignore [missing-attribute]
                self.active_loop_start, self.active_loop_end = self.get_active_loop_range()
                self.needs_range_update = False
                # pyrefly: ignore [missing-attribute]
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
                        self.mediaPlayer.pause()
                        # pyrefly: ignore [missing-attribute]
                        self.audioOutput.setMuted(True)
                    else:
                        self.current_cache_index = start_frame + (self.current_cache_index - end_frame - 1)

                    if self.fps > 0:
                        self.mediaPlayer.setPosition(
                            int(self.current_cache_index * 1000 / self.fps)
                        )
                        # pyrefly: ignore [missing-attribute]
                        self.audioOutput.setVolume(self.audioOutput.volume())
                else:
                    self.current_cache_index = end_frame
                    self.stop_playback()
        else:
            self.current_cache_index -= int_delta
            if self.current_cache_index < start_frame:
                if loop_mode == 3:  # Ping-pong
                    self.isForward = True
                    self.current_cache_index = start_frame + (start_frame - self.current_cache_index)
                    # pyrefly: ignore [missing-attribute]
                    self.audioOutput.setVolume(self.audioOutput.volume())
                    if self.fps > 0:
                        self.mediaPlayer.setPosition(
                            int(self.current_cache_index * 1000 / self.fps)
                        )
                        # pyrefly: ignore [missing-attribute]
                        self.audioOutput.setMuted(self.userMutedIntent)
                        self.mediaPlayer.play()
                elif loop_mode == 2:  # Backward loop
                    self.current_cache_index = end_frame - (start_frame - self.current_cache_index - 1)
                else:
                    self.current_cache_index = start_frame
                    self.stop_playback()

        self.current_cache_index = max(0, min(max(0, self.total_frames - 1), self.current_cache_index))

        if self.current_cache_index not in self.cached_frame_dict:
            # Restore state so we don't skip the missing frame once playback resumes
            self.current_cache_index = old_index
            self.isForward = old_forward
            self.frame_accumulator = old_accumulator

            self.was_playing_before_cache_miss = self.is_playing
            self.stop_playback()
            # pyrefly: ignore [missing-attribute]
            self.loadingOverlay.show()

            # pyrefly: ignore [missing-attribute]
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
            # pyrefly: ignore [missing-attribute]
            self.request_frame_extraction(target_frame, force=True)
            return

        self.update_pixmap_from_cache()
        # pyrefly: ignore [missing-attribute]
        self.check_sliding_window()
        self.sync_progress_bar()
        # pyrefly: ignore [missing-attribute]
        self.update_chronometer()

    # ------------------------------------------------------------------ #
    # Seeking / stepping                                                   #
    # ------------------------------------------------------------------ #

    def set_position(self, index):
        self.current_cache_index = index
        self.needs_range_update = True
        self.isForward = True

        if index not in getattr(self, 'cached_frame_dict', {}):
            # pyrefly: ignore [missing-attribute]
            self.loadingOverlay.show()
            # pyrefly: ignore [missing-attribute]
            self.request_frame_extraction(index, force=True)
        else:
            self.update_pixmap_from_cache()
            # pyrefly: ignore [missing-attribute]
            self.check_sliding_window()
            # pyrefly: ignore [missing-attribute]
            self.update_chronometer()

        if self.fps > 0:
            ms = int((index * 1000) / self.fps)
            # pyrefly: ignore [missing-attribute]
            self.currentTimeLabel.setText(format_time(ms))

        if not getattr(self, '_block_broadcast', False):
            # pyrefly: ignore [missing-attribute]
            self.broadcast_sync_event("seek", index)

    def on_slider_pressed(self):
        self.is_scrubbing = True

    def on_slider_released(self):
        self.is_scrubbing = False
        if self.fps > 0:
            pos = int((self.current_cache_index * 1000) / self.fps)
            self.mediaPlayer.setPosition(pos)
        self.update_pixmap_from_cache()
        # pyrefly: ignore [missing-attribute]
        self.update_chronometer()

    def step_frame(self, direction):
        self.current_cache_index += direction
        # pyrefly: ignore [missing-attribute]
        max_frame = self.progressBar.maximum() if self.progressBar.maximum() > 0 else 0
        self.current_cache_index = max(0, min(max_frame, self.current_cache_index))

        if self.current_cache_index not in getattr(self, 'cached_frame_dict', {}):
            # pyrefly: ignore [missing-attribute]
            self.loadingOverlay.show()
            # pyrefly: ignore [missing-attribute]
            self.request_frame_extraction(self.current_cache_index, force=True)
            return

        self.update_pixmap_from_cache()
        # pyrefly: ignore [missing-attribute]
        self.check_sliding_window()
        # pyrefly: ignore [missing-attribute]
        self.update_chronometer()

        if not getattr(self, '_block_broadcast', False):
            # pyrefly: ignore [missing-attribute]
            self.broadcast_sync_event("step", direction)

    # ------------------------------------------------------------------ #
    # Media player signal handlers                                        #
    # ------------------------------------------------------------------ #

    def update_play_icons(self):
        if self.is_playing:
            if self.isForward:
                # pyrefly: ignore [missing-attribute]
                self.playButton.setIcon(self.pauseIcon)
                # pyrefly: ignore [missing-attribute]
                self.playBackwardButton.setIcon(self.flippedPlayIcon)
            else:
                # pyrefly: ignore [missing-attribute]
                self.playButton.setIcon(self.normalPlayIcon)
                # pyrefly: ignore [missing-attribute]
                self.playBackwardButton.setIcon(self.pauseIcon)
        else:
            # pyrefly: ignore [missing-attribute]
            self.playButton.setIcon(self.normalPlayIcon)
            # pyrefly: ignore [missing-attribute]
            self.playBackwardButton.setIcon(self.flippedPlayIcon)

    def handle_state_change(self, state):
        is_paused_or_stopped = not self.is_playing
        if hasattr(self, 'stepBackButton'):
            self.stepBackButton.setEnabled(is_paused_or_stopped)
            # pyrefly: ignore [missing-attribute]
            self.stepForwardButton.setEnabled(is_paused_or_stopped)
        self.update_play_icons()

    def update_duration(self, duration):
        # Use ffprobe nb_frames if available to prevent drift/over-estimation
        if hasattr(self, 'ffprobe_nb_frames') and self.ffprobe_nb_frames > 0:
            self.total_frames = self.ffprobe_nb_frames
            if self.fps > 0:
                duration = (self.total_frames * 1000.0) / self.fps
        elif self.fps > 0:
            self.total_frames = int((duration / 1000.0) * self.fps)
            
        # pyrefly: ignore [missing-attribute]
        self.totalTimeLabel.setText(format_time(duration))
        self.sync_progress_bar()

        last_valid_frame = max(0, self.total_frames - 1)
        self.markers = [m for m in self.markers if m <= last_valid_frame]
        # pyrefly: ignore [missing-attribute]
        self.progressBar.update_markers(self.markers)
        # pyrefly: ignore [missing-attribute]
        self.update_loop_frames_label()

    def handle_status_change(self, status):
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            self.handle_metadata_change()
            # pyrefly: ignore [missing-attribute]
            if self.view and self.pixmapItem and self.last_transform_state is None:
                self.apply_transformations(fit=True)
                if hasattr(self, '_apply_file_saved_zoom'):
                    self._apply_file_saved_zoom()

    def handle_metadata_change(self):
        pass

    def on_speed_slider_changed(self, value):
        snapped = round(value / 5) * 5
        if snapped != value:
            # pyrefly: ignore [missing-attribute]
            self.speedSlider.setValue(snapped)
            return
        rate = snapped / 100.0
        self.mediaPlayer.setPlaybackRate(rate)
        # pyrefly: ignore [missing-attribute]
        self.speedValueLabel.setText(f"{snapped}%")

        if not getattr(self, '_block_broadcast', False):
            # pyrefly: ignore [missing-attribute]
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

    def _apply_file_saved_zoom(self):
        if not self.currentFilePath:
            return
        # pyrefly: ignore [missing-attribute]
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
            
        val = int(zoom * 100) if zoom < 10 else int(zoom)
        # pyrefly: ignore [missing-attribute]
        self.update_zoom(val)
        
        if hasattr(self, 'view') and self.view:
            if center_x is not None and center_y is not None:
                self.view.centerOn(QPointF(center_x, center_y))
            elif hasattr(self, 'pixmapItem') and self.pixmapItem:
                self.view.centerOn(self.pixmapItem.boundingRect().center())
            
        self.is_loading_video = False

    def on_user_zoom_changed(self, zoom_level):
        if self.is_loading_video:
            return
        # pyrefly: ignore [missing-attribute]
        self.sync_zoom_ui(zoom_level)
