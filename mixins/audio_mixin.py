import os
import logging
import subprocess
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtMultimedia import QMediaPlayer
from qfluentwidgets import InfoBar, InfoBarPosition
from translations import tr
from workers.threads import AudioExtractionThread
from utils import safe_rmtree, mark_temp_dir_owner, get_ffmpeg_path

logger = logging.getLogger("BoomerangPlayer")


class AudioMixin:
    def init_audio_state(self):
        self._audio_generation = 0
        self.audio_extract_thread = None
        self.prefetch_extract_thread = None
        self._reset_audio_chunk_state()

        # Debounce timer for EQ slider drag updates (250ms)
        self.eq_debounce_timer = QTimer(self)
        self.eq_debounce_timer.setSingleShot(True)
        self.eq_debounce_timer.setInterval(250)
        self.eq_debounce_timer.timeout.connect(self.apply_equalizer_filter)

        self.setup_media_player_intercept()

    def _reset_audio_chunk_state(self):
        self.original_audio_path_1 = None
        self.original_audio_path_2 = None
        self.active_original_path = None

        self.filtered_audio_path_1 = None
        self.filtered_audio_path_2 = None
        self.active_filtered_path = None

        self.audio_start_ms = 0.0
        self.audio_end_ms = 0.0
        self.audio_duration_ms = 0.0

        self.current_audio_track_index = 0
        self.is_loading_audio_chunk = False
        self.has_prefetched_chunk = False
        self.prefetched_original_path = None
        self.prefetched_start_ms = 0.0
        self.prefetched_end_ms = 0.0
        self.prefetched_duration_ms = 0.0
        self.pending_target_pos_ms = None
        self.pending_audio_start_ms = 0.0
        self.pending_audio_end_ms = 0.0

        self._pending_media_source = None
        self._pending_media_pos_ms = None
        self._pending_media_autoplay = False
        self._pending_media_is_chunk = False

    def _cancel_and_wait_thread(self, thread_attr):
        thread = getattr(self, thread_attr, None)
        if thread is not None:
            try:
                thread.finished_extraction.disconnect()
            except (TypeError, RuntimeError):
                pass
            if thread.isRunning():
                if hasattr(thread, 'cancel'):
                    thread.cancel()
                if not thread.wait(300):
                    thread.terminate()
                    thread.wait(50)
            setattr(self, thread_attr, None)

    def setup_media_player_intercept(self):
        if not hasattr(self, 'mediaPlayer') or self.mediaPlayer is None:
            return

        # Prevent double interception which leads to infinite recursion
        if getattr(self.mediaPlayer.setPosition, '__func__', None) == self.custom_set_position.__func__:
            return

        self.orig_set_position = self.mediaPlayer.setPosition
        self.orig_position = self.mediaPlayer.position

        self.mediaPlayer.setPosition = self.custom_set_position
        self.mediaPlayer.position = self.custom_position

    def _load_audio_source(self, path, target_pos_ms=None, auto_play=False, is_chunk_switch=False):
        """Load a media source and defer seek/play until QMediaPlayer reaches LoadedMedia."""
        if not hasattr(self, 'mediaPlayer') or not self.mediaPlayer or not path:
            return

        norm_path = os.path.normpath(path)
        self._pending_media_source = norm_path
        self._pending_media_pos_ms = int(target_pos_ms) if target_pos_ms is not None else None
        self._pending_media_autoplay = bool(auto_play)
        self._pending_media_is_chunk = bool(is_chunk_switch)
        self.is_loading_audio_chunk = bool(is_chunk_switch)

        try:
            self.mediaPlayer.stop()
        except Exception:
            pass
        self.mediaPlayer.setSource(QUrl.fromLocalFile(norm_path))

        if self.mediaPlayer.mediaStatus() in (
            QMediaPlayer.MediaStatus.LoadedMedia,
            QMediaPlayer.MediaStatus.BufferedMedia,
        ):
            self._apply_pending_media_state()

    def _apply_pending_media_state(self):
        """Apply deferred seek, rate, mute, and play/pause state once media finishes loading."""
        pending_src = getattr(self, '_pending_media_source', None)
        if not pending_src or not hasattr(self, 'mediaPlayer') or not self.mediaPlayer:
            return

        loaded_path = self.mediaPlayer.source().toLocalFile()
        if not loaded_path or os.path.normcase(os.path.normpath(loaded_path)) != os.path.normcase(pending_src):
            return

        pending_pos = self._pending_media_pos_ms
        pending_autoplay = self._pending_media_autoplay

        self._pending_media_source = None
        self._pending_media_pos_ms = None
        self._pending_media_autoplay = False
        self._pending_media_is_chunk = False
        self.is_loading_audio_chunk = False

        is_fwd = getattr(self, 'isForward', True)
        should_play = bool((getattr(self, 'is_playing', False) or pending_autoplay) and is_fwd)

        fps = getattr(self, 'fps', 0.0)
        if should_play and fps > 0:
            abs_pos_ms = int((getattr(self, 'current_cache_index', 0) * 1000.0) / fps)
        elif pending_pos is not None:
            abs_pos_ms = int(pending_pos)
        elif fps > 0:
            abs_pos_ms = int((getattr(self, 'current_cache_index', 0) * 1000.0) / fps)
        else:
            abs_pos_ms = 0

        if self.active_original_path is not None and os.path.exists(self.active_original_path):
            rel_pos = max(0, int(abs_pos_ms - self.audio_start_ms))
        else:
            rel_pos = max(0, int(abs_pos_ms))

        dur = self.mediaPlayer.duration()
        if dur > 0:
            rel_pos = min(rel_pos, max(0, dur - 1))

        self.orig_set_position(rel_pos)

        speed_slider = getattr(self, 'speedSlider', None)
        if speed_slider is not None:
            self.mediaPlayer.setPlaybackRate(speed_slider.value() / 100.0)

        if hasattr(self, 'audioOutput') and self.audioOutput:
            self.audioOutput.setMuted(getattr(self, 'userMutedIntent', False) if is_fwd else True)

        if should_play:
            self.mediaPlayer.play()
        else:
            self.mediaPlayer.pause()

    def _sync_audio_to_position(self, pos_ms, ensure_playing=False):
        """Seek QMediaPlayer safely and ensure playback resumes when expected."""
        if not hasattr(self, 'mediaPlayer') or not self.mediaPlayer:
            return

        self.mediaPlayer.setPosition(int(pos_ms))

        if ensure_playing and getattr(self, 'is_playing', False) and getattr(self, 'isForward', True):
            if (getattr(self, '_pending_media_source', None) is not None
                    or self.mediaPlayer.mediaStatus() == QMediaPlayer.MediaStatus.LoadingMedia):
                self._pending_media_autoplay = True
                self._pending_media_pos_ms = int(pos_ms)
                return

            if (self.audio_extract_thread and self.audio_extract_thread.isRunning()
                    and self.active_original_path is not None
                    and not (self.audio_start_ms <= pos_ms <= self.audio_end_ms + 50)):
                return

            if hasattr(self, 'audioOutput') and self.audioOutput:
                self.audioOutput.setMuted(getattr(self, 'userMutedIntent', False))

            speed_slider = getattr(self, 'speedSlider', None)
            if speed_slider is not None:
                self.mediaPlayer.setPlaybackRate(speed_slider.value() / 100.0)

            if self.mediaPlayer.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
                self.mediaPlayer.play()

    def custom_set_position(self, pos_ms):
        if (getattr(self, '_pending_media_source', None) is not None
                or (hasattr(self, 'mediaPlayer') and self.mediaPlayer
                    and self.mediaPlayer.mediaStatus() == QMediaPlayer.MediaStatus.LoadingMedia)):
            self._pending_media_pos_ms = max(0, int(pos_ms))
            return

        if self.active_original_path is None or not os.path.exists(self.active_original_path):
            pos = max(0, int(pos_ms))
            dur = self.mediaPlayer.duration()
            if dur > 0:
                pos = min(pos, max(0, dur - 1))
            self.orig_set_position(pos)
            return

        if self.audio_start_ms <= pos_ms <= self.audio_end_ms + 50:
            rel_pos = max(0, int(pos_ms - self.audio_start_ms))
            dur = self.mediaPlayer.duration()
            if dur > 0:
                rel_pos = min(rel_pos, max(0, dur - 1))
            self.orig_set_position(rel_pos)
        else:
            if hasattr(self, 'audio_extract_thread') and self.audio_extract_thread and self.audio_extract_thread.isRunning():
                if getattr(self, 'pending_audio_start_ms', 0.0) <= pos_ms <= getattr(self, 'pending_audio_end_ms', 0.0) + 50:
                    self.pending_target_pos_ms = int(pos_ms)
                    return

            target_sec = pos_ms / 1000.0
            start_sec = max(0.0, target_sec - 10.0)
            duration_sec = 300.0
            if self.total_frames > 0 and self.fps > 0:
                total_duration_sec = self.total_frames / self.fps
                if start_sec + duration_sec > total_duration_sec:
                    duration_sec = max(0.0, total_duration_sec - start_sec)

            source_path = getattr(self, 'currentVideoPath', None) or self.currentFilePath
            self.prepare_audio_track(
                source_path,
                self.current_audio_track_index,
                start_sec=start_sec,
                duration_sec=duration_sec,
                target_pos_ms=pos_ms
            )

    def custom_position(self):
        if self.active_original_path is not None and os.path.exists(self.active_original_path):
            return self.orig_position() + self.audio_start_ms
        return self.orig_position()

    def update_duration(self, duration):
        if (getattr(self, 'is_loading_audio_chunk', False)
                or getattr(self, '_pending_media_is_chunk', False)
                or (self.active_original_path is not None and getattr(self, 'total_frames', 0) > 0)
                or (duration <= 0 and getattr(self, 'currentFilePath', None) and getattr(self, 'total_frames', 0) > 0)):
            return
        super().update_duration(duration)

    def advance_frame(self):
        try:
            super().advance_frame()
        except AttributeError:
            pass

        if (self.fps > 0 and self.is_playing and self.isForward
                and self.active_original_path is not None
                and getattr(self, 'audio_end_ms', 0) > 0
                and getattr(self, 'total_frames', 0) > 0):
            total_dur_ms = (self.total_frames * 1000.0) / self.fps
            if self.audio_end_ms >= total_dur_ms - 100:
                return

            current_pos_ms = (self.current_cache_index * 1000.0) / self.fps

            if current_pos_ms >= self.audio_end_ms:
                if getattr(self, 'has_prefetched_chunk', False) and self.prefetched_original_path and os.path.exists(self.prefetched_original_path):
                    self.activate_prefetched_chunk(current_pos_ms)
                else:
                    self.custom_set_position(current_pos_ms)
            elif self.audio_end_ms - current_pos_ms <= 5000:
                is_extracting = ((hasattr(self, 'prefetch_extract_thread') and self.prefetch_extract_thread and self.prefetch_extract_thread.isRunning())
                                 or (hasattr(self, 'audio_extract_thread') and self.audio_extract_thread and self.audio_extract_thread.isRunning()))

                next_start_sec = self.audio_end_ms / 1000.0
                total_dur_sec = self.total_frames / self.fps

                if next_start_sec < total_dur_sec and not is_extracting and not getattr(self, 'has_prefetched_chunk', False):
                    self.pre_fetch_next_chunk(next_start_sec)

    def pre_fetch_next_chunk(self, next_start_sec):
        duration_sec = 300.0
        total_duration_sec = self.total_frames / self.fps
        if next_start_sec + duration_sec > total_duration_sec:
            duration_sec = max(0.0, total_duration_sec - next_start_sec)

        if duration_sec <= 0:
            return

        if self.active_original_path == self.original_audio_path_1:
            target_original = self.original_audio_path_2
        else:
            target_original = self.original_audio_path_1

        self._cancel_and_wait_thread('prefetch_extract_thread')
        gen = getattr(self, '_audio_generation', 0)
        ffmpeg_path = get_ffmpeg_path()
        source_path = getattr(self, 'currentVideoPath', None) or self.currentFilePath

        self.prefetch_extract_thread = AudioExtractionThread(
            source_path, ffmpeg_path, target_original,
            self.current_audio_track_index, next_start_sec, duration_sec
        )
        self.prefetch_extract_thread.finished_extraction.connect(
            lambda p, st, d, g=gen: self.on_prefetch_extracted(p, st, d, g)
        )
        self.prefetch_extract_thread.start()

    def on_prefetch_extracted(self, path, start_time, duration, gen=None):
        if gen is not None and gen != getattr(self, '_audio_generation', 0):
            return
        if not path or not os.path.exists(path):
            logger.debug("[AudioMixin] Pre-fetch extraction failed.")
            return

        self.prefetched_original_path = path
        self.prefetched_start_ms = start_time * 1000.0
        self.prefetched_end_ms = (start_time + duration) * 1000.0
        self.prefetched_duration_ms = duration * 1000.0
        self.has_prefetched_chunk = True
        logger.debug(f"[AudioMixin] Pre-fetched next chunk into {path} (start: {start_time}s)")

    def activate_prefetched_chunk(self, current_pos_ms):
        self.active_original_path = self.prefetched_original_path
        self.audio_start_ms = self.prefetched_start_ms
        self.audio_end_ms = self.prefetched_end_ms
        self.audio_duration_ms = self.prefetched_duration_ms
        self.has_prefetched_chunk = False

        was_playing = getattr(self, 'is_playing', False) and getattr(self, 'isForward', True)
        if self.config.get('audio_eq_enabled', False):
            self.pending_target_pos_ms = current_pos_ms
            self.apply_equalizer_filter()
        else:
            self._load_audio_source(
                self.active_original_path,
                target_pos_ms=current_pos_ms,
                auto_play=was_playing,
                is_chunk_switch=True
            )
        logger.debug(f"[AudioMixin] Pre-fetched chunk activated at {self.audio_start_ms / 1000.0}s")

    def recreate_media_player(self):
        super().recreate_media_player()
        self.setup_media_player_intercept()

    def cleanup_temp_audio(self):
        self._audio_generation = getattr(self, '_audio_generation', 0) + 1
        self._cancel_and_wait_thread('audio_extract_thread')
        self._cancel_and_wait_thread('prefetch_extract_thread')

        if hasattr(self, 'mediaPlayer') and self.mediaPlayer:
            try:
                self.mediaPlayer.stop()
            except Exception:
                pass
            self.mediaPlayer.setSource(QUrl())

        self._reset_audio_chunk_state()

        if hasattr(self, 'current_temp_dir') and self.current_temp_dir and os.path.exists(self.current_temp_dir):
            safe_rmtree(self.current_temp_dir, retries=5, delay=0.15)
            self.current_temp_dir = None

    def closeEvent(self, event):
        self.cleanup_temp_audio()
        try:
            super().closeEvent(event)
        except AttributeError:
            pass

    def load_video(self, filePath):
        self.cleanup_temp_audio()
        super().load_video(filePath)

        is_static_image = (
            filePath.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff'))
            and not getattr(self, 'is_motion_photo', False)
        )
        has_audio = hasattr(self, 'audio_tracks_info') and len(self.audio_tracks_info) > 0

        if not is_static_image and has_audio:
            self.populate_audio_tracks_ui()
            needs_extraction = (
                (not getattr(self, 'is_audio_only', False))
                or self.config.get('audio_eq_enabled', False)
                or self.current_audio_track_index != 0
            )
            if needs_extraction:
                target_ms = 0
                if getattr(self, 'fps', 0) > 0 and getattr(self, 'current_cache_index', 0) > 0:
                    target_ms = int((self.current_cache_index * 1000) / self.fps)
                start_sec = max(0.0, (target_ms / 1000.0) - 10.0)
                duration_sec = 300.0
                if self.total_frames > 0 and self.fps > 0:
                    total_duration_sec = self.total_frames / self.fps
                    duration_sec = min(300.0, max(0.0, total_duration_sec - start_sec))
                source_path = getattr(self, 'currentVideoPath', None) or filePath
                self.prepare_audio_track(
                    source_path,
                    self.current_audio_track_index,
                    start_sec=start_sec,
                    duration_sec=duration_sec,
                    target_pos_ms=target_ms
                )
        else:
            if hasattr(self, 'audioTrackCombo'):
                self.audioTrackCombo.blockSignals(True)
                self.audioTrackCombo.clear()
                self.audioTrackCombo.addItem(tr('off'), -1)
                self.audioTrackCombo.blockSignals(False)

    def prepare_audio_track(self, video_path, track_index=0, start_sec=0.0, duration_sec=300.0, target_pos_ms=None):
        self._cancel_and_wait_thread('audio_extract_thread')
        self._cancel_and_wait_thread('prefetch_extract_thread')
        self._audio_generation = getattr(self, '_audio_generation', 0) + 1
        gen = self._audio_generation
        self.has_prefetched_chunk = False

        if not hasattr(self, 'current_temp_dir') or not self.current_temp_dir:
            import uuid
            import tempfile
            self.current_temp_dir = os.path.join(tempfile.gettempdir(), f"mem_cache_{uuid.uuid4().hex}")
            mark_temp_dir_owner(self.current_temp_dir)
        os.makedirs(self.current_temp_dir, exist_ok=True)

        self.original_audio_path_1 = os.path.normpath(os.path.join(self.current_temp_dir, "original_audio_1.wav"))
        self.original_audio_path_2 = os.path.normpath(os.path.join(self.current_temp_dir, "original_audio_2.wav"))
        self.filtered_audio_path_1 = os.path.normpath(os.path.join(self.current_temp_dir, "filtered_audio_1.wav"))
        self.filtered_audio_path_2 = os.path.normpath(os.path.join(self.current_temp_dir, "filtered_audio_2.wav"))

        if self.active_original_path == self.original_audio_path_1:
            target_original = self.original_audio_path_2
        else:
            target_original = self.original_audio_path_1

        self.current_audio_track_index = track_index
        self.pending_target_pos_ms = target_pos_ms if target_pos_ms is not None else int(start_sec * 1000)
        self.pending_audio_start_ms = start_sec * 1000.0
        self.pending_audio_end_ms = (start_sec + duration_sec) * 1000.0

        ffmpeg_path = get_ffmpeg_path()

        self.audio_extract_thread = AudioExtractionThread(
            video_path, ffmpeg_path, target_original, track_index, start_sec, duration_sec
        )
        self.audio_extract_thread.finished_extraction.connect(
            lambda p, st, d, g=gen: self.on_audio_extracted(p, st, d, g)
        )
        self.audio_extract_thread.start()

    def on_audio_extracted(self, path, start_time, duration, gen=None):
        if gen is not None and gen != getattr(self, '_audio_generation', 0):
            return
        if not path or not os.path.exists(path) or os.path.getsize(path) <= 44:
            logger.warning("[AudioMixin] Audio extraction failed or returned invalid path.")
            return

        self.active_original_path = path
        self.audio_start_ms = start_time * 1000.0
        self.audio_end_ms = (start_time + duration) * 1000.0
        self.audio_duration_ms = duration * 1000.0

        self.populate_audio_tracks_ui()

        if self.config.get('audio_eq_enabled', False):
            self.apply_equalizer_filter()
        else:
            should_play = bool(getattr(self, 'is_playing', False) and getattr(self, 'isForward', True))
            if should_play and getattr(self, 'fps', 0) > 0:
                pos = int((self.current_cache_index * 1000.0) / self.fps)
            else:
                pos = getattr(self, 'pending_target_pos_ms', self.audio_start_ms)
                if pos is None:
                    pos = self.audio_start_ms
            self.pending_target_pos_ms = None
            self._load_audio_source(
                self.active_original_path,
                target_pos_ms=pos,
                auto_play=should_play,
                is_chunk_switch=True
            )

    def populate_audio_tracks_ui(self):
        if not hasattr(self, 'audioTrackCombo') or not hasattr(self, 'audio_tracks_info'):
            return
        self.audioTrackCombo.blockSignals(True)
        self.audioTrackCombo.clear()

        for t in self.audio_tracks_info:
            idx = t['index']
            lang = t['language']
            codec = t['codec']
            channels = t['channels']
            title = t['title']

            label = f"Track {idx}: {lang.upper()} ({codec}, {channels}ch)"
            if title:
                label += f" - {title}"
            self.audioTrackCombo.addItem(label, idx)

        track_idx = getattr(self, 'current_audio_track_index', 0)
        if 0 <= track_idx < self.audioTrackCombo.count():
            self.audioTrackCombo.setCurrentIndex(track_idx)
        self.audioTrackCombo.blockSignals(False)

    def on_audio_track_changed(self, idx):
        if idx < 0 or idx >= len(getattr(self, 'audio_tracks_info', [])):
            return
        track_info = self.audio_tracks_info[idx]
        logger.debug(f"[AudioMixin] Audio track changed. Re-extracting track {track_info['index']}...")

        pos = self.mediaPlayer.position()  # Virtual absolute position
        target_sec = pos / 1000.0
        start_sec = max(0.0, target_sec - 10.0)
        duration_sec = 300.0
        if self.total_frames > 0 and self.fps > 0:
            total_duration_sec = self.total_frames / self.fps
            if start_sec + duration_sec > total_duration_sec:
                duration_sec = max(0.0, total_duration_sec - start_sec)

        source_path = getattr(self, 'currentVideoPath', None) or self.currentFilePath
        self.prepare_audio_track(source_path, track_info['index'], start_sec, duration_sec, target_pos_ms=pos)

    def apply_equalizer_filter(self):
        if not hasattr(self, 'active_original_path') or not self.active_original_path or not os.path.exists(self.active_original_path):
            return

        # Alternate between filtered_audio_1 and filtered_audio_2 to bypass Windows file locks
        if self.active_filtered_path == self.filtered_audio_path_1:
            target_path = self.filtered_audio_path_2
        else:
            target_path = self.filtered_audio_path_1

        gains = self.config.get('audio_eq_gains', [0] * 10)
        freqs = [31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]
        filter_str = ",".join(f"equalizer=f={f}:width_type=o:w=1:g={g}" for f, g in zip(freqs, gains))

        ffmpeg_path = get_ffmpeg_path()
        cmd = [
            ffmpeg_path, "-y", "-i", self.active_original_path,
            "-af", filter_str,
            target_path
        ]

        try:
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            subprocess.run(cmd, creationflags=creationflags, check=True)

            self.active_filtered_path = target_path
            should_play = bool(getattr(self, 'is_playing', False) and getattr(self, 'isForward', True))
            if should_play and getattr(self, 'fps', 0) > 0:
                pos = int((self.current_cache_index * 1000.0) / self.fps)
            else:
                pos = getattr(self, 'pending_target_pos_ms', None)
                if pos is None:
                    pos = self.mediaPlayer.position()
            self.pending_target_pos_ms = None

            self._load_audio_source(
                self.active_filtered_path,
                target_pos_ms=pos,
                auto_play=should_play,
                is_chunk_switch=True
            )
            logger.debug(f"[AudioMixin] Equalizer applied. Output written to {target_path}")
        except Exception as e:
            logger.warning(f"[AudioMixin] Error filtering audio with equalizer: {e}")
            self.pending_target_pos_ms = None

    def on_audio_eq_toggle_changed(self, checked):
        self.config['audio_eq_enabled'] = checked
        self.config.save()

        if checked:
            if hasattr(self, 'active_original_path') and self.active_original_path and os.path.exists(self.active_original_path):
                self.apply_equalizer_filter()
            elif getattr(self, 'currentFilePath', None) and getattr(self, 'audio_tracks_info', None):
                pos = self.mediaPlayer.position()
                target_sec = pos / 1000.0
                start_sec = max(0.0, target_sec - 10.0)
                duration_sec = 300.0
                if self.total_frames > 0 and self.fps > 0:
                    total_duration_sec = self.total_frames / self.fps
                    duration_sec = min(300.0, max(0.0, total_duration_sec - start_sec))
                source_path = getattr(self, 'currentVideoPath', None) or self.currentFilePath
                self.prepare_audio_track(
                    source_path,
                    self.current_audio_track_index,
                    start_sec=start_sec,
                    duration_sec=duration_sec,
                    target_pos_ms=pos
                )
        else:
            self.active_filtered_path = None
            raw_source = None
            is_chunk = False
            if hasattr(self, 'active_original_path') and self.active_original_path and os.path.exists(self.active_original_path):
                raw_source = self.active_original_path
                is_chunk = True
            elif getattr(self, 'is_audio_only', False):
                candidate = getattr(self, 'currentVideoPath', None) or getattr(self, 'currentFilePath', None)
                if candidate and os.path.exists(candidate):
                    raw_source = candidate

            if raw_source:
                should_play = bool(getattr(self, 'is_playing', False) and getattr(self, 'isForward', True))
                pos = int((self.current_cache_index * 1000.0) / self.fps) if (should_play and getattr(self, 'fps', 0) > 0) else self.mediaPlayer.position()
                self._load_audio_source(
                    raw_source,
                    target_pos_ms=pos,
                    auto_play=should_play,
                    is_chunk_switch=is_chunk
                )
                logger.debug("[AudioMixin] Equalizer disabled. Reverted to raw audio.")

    def on_audio_eq_preset_changed(self, idx):
        if idx < 0:
            return
        presets = {
            'Flat': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            'Bass Boost': [6, 5, 4, 2, 0, 0, 0, 0, 0, 0],
            'Treble Boost': [0, 0, 0, 0, 0, 0, 0, 2, 4, 6],
            'Vocal': [0, -2, 2, 3, 2, 1, 0, 0, 0, 0],
            'Pop': [-1, 1, 3, 4, 2, -1, -1, 0, 0, 0],
            'Rock': [4, 3, -1, -2, -1, 2, 3, 4, 4, 0],
            'Jazz': [3, 2, 1, 2, -1, -1, 1, 2, 0, 0],
            'Classical': [4, 3, 2, 2, -1, -1, 0, 1, 2, 3]
        }
        preset_name = self.audioEqPresetCombo.itemData(idx)
        if not preset_name:
            preset_name = self.audioEqPresetCombo.itemText(idx)
        gains = presets.get(preset_name, [0] * 10)

        self.config['audio_eq_preset'] = preset_name
        self.config['audio_eq_gains'] = gains
        self.config.save()

        # Update sliders & labels in UI
        if hasattr(self, 'eq_sliders'):
            for i, slider in enumerate(self.eq_sliders):
                slider.blockSignals(True)
                slider.setValue(gains[i])
                slider.blockSignals(False)

                label = self.eq_labels[i]
                gain_val = gains[i]
                label.setText(f"{gain_val:+d}" if gain_val != 0 else "0")

        if self.config.get('audio_eq_enabled', False):
            self.eq_debounce_timer.start()

    def on_eq_slider_changed(self, val):
        slider = self.sender()
        if not slider:
            return
        band_idx = slider.property("band_idx")
        if band_idx is None:
            return

        # Update label
        self.eq_labels[band_idx].setText(f"{val:+d}" if val != 0 else "0")

        # Update configuration
        gains = list(self.config.get('audio_eq_gains', [0] * 10))
        gains[band_idx] = val
        self.config['audio_eq_gains'] = gains
        self.config.save()

        # Mark preset as custom if values deviate
        self.config['audio_eq_preset'] = 'Custom'
        self.config.save()
        self.update_audio_presets_ui()

        if self.config.get('audio_eq_enabled', False):
            self.eq_debounce_timer.start()

    def reset_equalizer(self):
        gains = [0] * 10
        self.config['audio_eq_preset'] = 'Flat'
        self.config['audio_eq_gains'] = gains
        self.config.save()

        # Update UI components
        self.update_audio_presets_ui()
        if hasattr(self, 'eq_sliders'):
            for i, slider in enumerate(self.eq_sliders):
                slider.blockSignals(True)
                slider.setValue(0)
                slider.blockSignals(False)
                self.eq_labels[i].setText("0")

        if self.config.get('audio_eq_enabled', False):
            self.eq_debounce_timer.start()

        # Show notification
        InfoBar.success(
            title=tr('audio_eq_enable'),
            content=tr('reset_eq') + " " + tr('ok'),
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=1500,
            parent=self
        )

    def toggle_audio_panel(self):
        if not hasattr(self, 'audioContainer'):
            return
        is_visible = self.audioContainer.isVisible()

        # Hide mutually exclusive sidebars on the right side
        if not is_visible:
            if hasattr(self, 'playlistContainer') and self.playlistContainer.isVisible():
                self.playlistContainer.hide()
            if hasattr(self, 'drawingContainer') and self.drawingContainer.isVisible():
                self.drawingContainer.hide()

        self.audioContainer.setVisible(not is_visible)

        if hasattr(self, 'update_sidebar_fullscreen_state'):
            self.update_sidebar_fullscreen_state()
        if hasattr(self, 'update_sidebar_margins'):
            self.update_sidebar_margins()

        if not is_visible and not getattr(self, 'is_full_screen', False):
            sizes = self.mainSplitter.sizes()
            # Under new layout: index 4 is audioContainer
            if len(sizes) > 4 and sizes[4] < 260:
                sizes[4] = 260
                self.mainSplitter.setSizes(sizes)
