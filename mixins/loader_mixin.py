"""
LoaderMixin — media file/folder loading, ffprobe metadata extraction, and saved zoom level recovery.
"""

import os
import subprocess
import json
import logging
from PyQt6.QtCore import Qt, QUrl, QTimer, QPointF
from PyQt6.QtMultimedia import QMediaPlayer
from utils import mark_temp_dir_owner
from qfluentwidgets import FluentIcon
from utils import get_resource_path, format_time, VERSION, get_embedded_video_offset
from translations import tr

logger = logging.getLogger("Loader")

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QMainWindow, QPushButton, QSlider, QLabel
    from PyQt6.QtMultimedia import QAudioOutput
    from config import Configuration
    from components import GPUPixmapItem
    LoaderMixinBase = QMainWindow
else:
    LoaderMixinBase = object


class LoaderMixin(LoaderMixinBase):
    if TYPE_CHECKING:
        config: Configuration
        mediaPlayer: QMediaPlayer
        audioOutput: QAudioOutput
        current_temp_dir: str | None
        currentFilePath: str | None
        currentVideoPath: str | None
        video_codec: str | None
        is_hdr: bool
        color_transfer: str
        color_primaries: str
        last_transform_state: tuple | None
        is_motion_photo: bool
        motion_photo_original_path: str | None
        is_audio_only: bool
        cached_frame_dict: dict
        cached_file_path: str | None
        current_cache_index: int
        fps: float
        total_frames: int
        playButton: QPushButton
        subtitleLabel: QLabel | None
        subtitles: list
        subtitleFilePath: str | None
        playlistData: dict
        ffprobe_fps: float
        ffprobe_duration: float
        ffprobe_nb_frames: int
        audio_tracks_info: list
        speedSlider: QSlider
        progressBar: QSlider
        view: any
        pixmapItem: GPUPixmapItem | None
        markers: list
        loadingOverlay: QLabel
        is_loading_video: bool

        load_playlist_by_path: callable
        add_files_to_playlist: callable
        stop_playback: callable
        cleanup_cache: callable
        save_current_markers: callable
        sync_progress_bar: callable
        update_pixmap_from_cache: callable
        apply_transformations: callable
        start_full_extraction: callable
        load_markers_for_current: callable
        generate_audio_placeholder: callable
        update_duration: callable
        handle_metadata_change: callable
        auto_load_subtitles_for_video: callable
        update_zoom: callable
        sync_zoom_ui: callable

    def open_media(self):
        """Custom file picker — avoids QFileDialog which corrupts DWM rendering in fullscreen."""
        from mixins.file_dialog import MediaFileDialog
        dialog = MediaFileDialog(self, self.config)
        self._open_media_dialog = dialog
        dialog.finished.connect(self._on_open_media_finished)
        dialog.show()

    def _on_open_media_finished(self, result):
        dialog = self._open_media_dialog
        if result and hasattr(dialog, 'selected_files') and dialog.selected_files:
            self._process_selected_files(dialog.selected_files)

    def _process_selected_files(self, selected):
        video_exts = ('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.m4v', '.webm', '.flv', '.mpg', '.mpeg', '.ogv')
        image_exts = ('.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff')
        audio_exts = ('.mp3', '.wav', '.aac', '.flac', '.m4a', '.ogg', '.wma')
        playlist_exts = ('.json', '.bpl')
        all_exts = video_exts + image_exts + audio_exts + playlist_exts

        files_to_add = []
        playlist_files = []
        for path in selected:
            if os.path.isdir(path):
                for f in sorted(os.listdir(path)):
                    if f.lower().endswith(all_exts):
                        fpath = os.path.join(path, f)
                        if f.lower().endswith(playlist_exts):
                            playlist_files.append(fpath)
                        else:
                            files_to_add.append(fpath)
            elif os.path.isfile(path):
                if path.lower().endswith(playlist_exts):
                    playlist_files.append(path)
                else:
                    files_to_add.append(path)

        if playlist_files:
            self.load_playlist_by_path(playlist_files[0], silent=True)
            if files_to_add:
                self.add_files_to_playlist(files_to_add)
        elif files_to_add:
            self.add_files_to_playlist(files_to_add)
            if self.mediaPlayer.playbackState() == QMediaPlayer.PlaybackState.StoppedState:
                self.load_video(files_to_add[0])

    def load_video(self, filePath):
        logger.info(f"load_video started for: {filePath}")
        was_playing = getattr(self, 'is_playing', False)
        self.stop_playback()
        self.was_playing_before_cache_miss = was_playing
        self.frame_accumulator = 0.0
        self.last_advance_ms = 0
        self.loop_count = 0

        logger.info("Setting mediaPlayer source to empty and cleaning up cache/markers")
        self.mediaPlayer.setSource(QUrl())
        self.cleanup_cache()
        self.save_current_markers()
        is_image = False
        try:
            self.is_loading_video = True
            if hasattr(self, 'subtitles'):
                self.subtitles = []
                self.subtitleFilePath = None
                if hasattr(self, 'subtitleLabel') and self.subtitleLabel:
                    self.subtitleLabel.hide()
            self.currentFilePath = filePath
            self.currentVideoPath = filePath
            self.video_codec = None
            self.is_hdr = False
            self.color_transfer = ""
            self.color_primaries = ""
            self.last_transform_state = None
            self.is_motion_photo = False
            self.motion_photo_original_path = None
            self.is_audio_only = False
            if hasattr(self, 'initial_fit_done'):
                delattr(self, 'initial_fit_done')

            is_image = filePath.lower().endswith(
                ('.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff')
            )
            logger.info(f"File recognized as image: {is_image}")

            embedded_offset = None
            if is_image and filePath.lower().endswith(('.jpg', '.jpeg')):
                logger.info("Checking for embedded video in JPEG (motion photo)...")
                embedded_offset = get_embedded_video_offset(filePath)

            if embedded_offset is not None:
                self.is_motion_photo = True
                self.motion_photo_original_path = filePath
                if not self.current_temp_dir:
                    import tempfile
                    self.current_temp_dir = tempfile.mkdtemp(prefix="boomerang_frames_")
                    mark_temp_dir_owner(self.current_temp_dir)
                
                temp_video_path = os.path.join(self.current_temp_dir, "extracted_video.mp4")
                try:
                    logger.info(f"Extracting motion photo video data starting at offset {embedded_offset}")
                    with open(filePath, 'rb') as f:
                        f.seek(embedded_offset)
                        video_data = f.read()
                    with open(temp_video_path, 'wb') as f:
                        f.write(video_data)
                    self.currentVideoPath = temp_video_path
                    is_image = False
                    logger.info(f"Successfully extracted motion photo video to {temp_video_path}")
                except Exception as ex:
                    logger.exception(f"Error extracting motion photo video")

            if is_image:
                logger.info("Processing as static image...")
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
                logger.info("Extracting video metadata using ffprobe...")
                fps, duration_ms, total_frames = self.get_video_info(self.currentVideoPath)
                if self.is_motion_photo:
                    total_frames += 1

                if fps > 0:
                    self.fps = fps
                    logger.info(f"ffprobe detected FPS: {self.fps}")

                if self.is_motion_photo:
                    self.cached_frame_dict = {0: filePath}
                else:
                    self.cached_frame_dict = {}

                self.current_cache_index = 0

                logger.info(f"Setting QMediaPlayer source to: {self.currentVideoPath}")
                self.mediaPlayer.setSource(QUrl.fromLocalFile(self.currentVideoPath))
                if self.is_motion_photo:
                    self.setWindowTitle(f"Boomerang Player v{VERSION} - [Motion Photo] {os.path.basename(filePath)}")
                elif self.is_audio_only:
                    self.setWindowTitle(f"Boomerang Player v{VERSION} - [Audio] {os.path.basename(filePath)}")
                else:
                    self.setWindowTitle(f"Boomerang Player v{VERSION} - {os.path.basename(filePath)}")

                self.ffprobe_fps = fps
                self.ffprobe_duration = duration_ms
                self.ffprobe_nb_frames = total_frames
                self.fps = fps
                self.total_frames = total_frames

                self.update_duration(duration_ms)

                self.mediaPlayer.pause()
                self.playButton.setIcon(FluentIcon.PLAY)
                self.playButton.setEnabled(True)

            logger.info("Loading saved markers for file...")
            self.load_markers_for_current()

            if not is_image:
                if hasattr(self, 'auto_load_subtitles_for_video'):
                    logger.info("Checking for subtitles...")
                    self.auto_load_subtitles_for_video(filePath)

            if not is_image:
                if self.is_audio_only:
                    logger.info("Generating placeholder for audio file...")
                    self.generate_audio_placeholder()
                    self.update_pixmap_from_cache()
                    self.apply_transformations(fit=True)
                else:
                    logger.info("Initializing cache and starting full video frame extraction...")
                    self.update_pixmap_from_cache()
                    self.start_full_extraction()

            if getattr(self, 'autoplay_next', False):
                if self.is_audio_only or is_image:
                    self.autoplay_next = False
                    loop_mode = self.loopCombo.currentIndex()
                    if loop_mode == 2:
                        self.isForward = False
                        self.current_cache_index = max(0, self.total_frames - 1)
                    else:
                        self.isForward = True
                        self.current_cache_index = 0
                    self._start_playback()
            logger.info(f"load_video completed successfully for: {filePath}")
            
            if hasattr(self, 'refresh_window_frame'):
                QTimer.singleShot(250, self.refresh_window_frame)

        except Exception as e:
            logger.exception(f"Error opening file: {filePath}")
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
            if not self.currentFilePath or is_image:
                pass
            if not hasattr(self, '_apply_file_saved_zoom'):
                self.is_loading_video = False

    def get_video_info(self, file_path):
        """Get FPS and duration using ffprobe, supporting both video and audio-only files."""
        logger.info(f"get_video_info started for: {file_path}")
        try:
            ffprobe_path = get_resource_path("ffprobe.exe" if os.name == 'nt' else "ffprobe")
            if not os.path.exists(ffprobe_path):
                ffprobe_path = "ffprobe"

            cmd = [
                ffprobe_path, "-v", "error",
                "-show_entries", "stream=index,codec_type,codec_name,avg_frame_rate,duration,nb_frames,channels,color_space,color_transfer,color_primaries:stream_tags=language,title:format=duration",
                "-of", "json", file_path
            ]

            creationflags = 0
            if os.name == 'nt':
                creationflags = subprocess.CREATE_NO_WINDOW

            result = subprocess.check_output(cmd, creationflags=creationflags).decode('utf-8')
            data = json.loads(result)
            streams = data.get('streams', [])
            
            self.audio_tracks_info = []
            audio_idx = 0
            for s in streams:
                if s.get('codec_type') == 'audio':
                    tags = s.get('tags', {})
                    lang = tags.get('language', 'und')
                    title = tags.get('title', '')
                    codec = s.get('codec_name', 'unknown')
                    channels = s.get('channels', 2)
                    self.audio_tracks_info.append({
                        'index': audio_idx,
                        'stream_index': s.get('index'),
                        'codec': codec,
                        'language': lang,
                        'title': title,
                        'channels': channels
                    })
                    audio_idx += 1
            
            video_stream = next((s for s in streams if s.get('codec_type') == 'video'), None)
            audio_stream = next((s for s in streams if s.get('codec_type') == 'audio'), None)
            
            self.is_audio_only = (video_stream is None and audio_stream is not None)
            
            self.is_hdr = False
            self.color_transfer = ""
            self.color_primaries = ""
            if video_stream:
                self.color_transfer = video_stream.get('color_transfer', '')
                self.color_primaries = video_stream.get('color_primaries', '')
                if self.color_transfer in ('smpte2084', 'arib-std-b67') or self.color_primaries == 'bt2020':
                    self.is_hdr = True
            
            if not self.is_hdr and file_path:
                bn = os.path.basename(file_path).lower()
                if '.hdr.' in bn or '_hdr_' in bn or bn.endswith('hdr') or 'hdr10' in bn:
                    self.is_hdr = True

            stream = video_stream if video_stream is not None else audio_stream
            if not stream:
                return 30.0, 0, 0

            fmt = data.get('format', {})
            
            if self.is_audio_only:
                fps = 30.0
            else:
                fps_str = stream.get('avg_frame_rate') or stream.get('r_frame_rate') or '30/1'
                if '/' in fps_str:
                    num, den = map(int, fps_str.split('/'))
                    fps = num / den if den != 0 else 30.0
                else:
                    fps = float(fps_str)
                
            s_dur = stream.get('duration')
            f_dur = fmt.get('duration')
            duration = float(s_dur if s_dur is not None else (f_dur if f_dur is not None else 0))
            
            nb_frames_val = stream.get('nb_frames', 0)
            if nb_frames_val == 'N/A' or nb_frames_val is None:
                nb_frames = 0
            else:
                try:
                    nb_frames = int(nb_frames_val)
                except (ValueError, TypeError):
                    nb_frames = 0
            if nb_frames == 0 and duration > 0:
                nb_frames = int(duration * fps)
            
            codec = stream.get('codec_name', 'unknown')
            self.video_codec = codec
            
            logger.info(f"[get_video_info] {os.path.basename(file_path)}: codec={codec}, is_audio_only={self.is_audio_only}, fps={fps}, duration={duration}s, nb_frames={nb_frames}")
            return fps, duration * 1000, nb_frames
        except Exception as e:
            logger.error(f"ffprobe error: {e}", exc_info=True)
            return 30.0, 0, 0

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
            
        val = int(zoom * 100) if zoom < 10 else int(zoom)
        self.update_zoom(val)
        
        if hasattr(self, 'view') and self.view:
            if center_x is not None and center_y is not None:
                self.view.centerOn(QPointF(center_x, center_y))
            elif hasattr(self, 'pixmapItem') and self.pixmapItem:
                self.view.centerOn(self.pixmapItem.boundingRect().center())
            
        self.is_loading_video = False
