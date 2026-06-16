import os
import subprocess
from PyQt6.QtCore import Qt, QTimer, QUrl, QThread, pyqtSignal
from qfluentwidgets import InfoBar, InfoBarPosition
from translations import tr
from workers.threads import AudioExtractionThread


class AudioMixin:
    def init_audio_state(self):
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
        self.audio_extract_thread = None
        self.prefetch_extract_thread = None
        self.is_loading_audio_chunk = False
        self.has_prefetched_chunk = False
        self.pending_target_pos_ms = None

        # Debounce timer for EQ slider drag updates (250ms)
        self.eq_debounce_timer = QTimer(self)
        self.eq_debounce_timer.setSingleShot(True)
        self.eq_debounce_timer.setInterval(250)
        self.eq_debounce_timer.timeout.connect(self.apply_equalizer_filter)

        self.setup_media_player_intercept()

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

    def custom_set_position(self, pos_ms):
        if self.active_original_path is None or not os.path.exists(self.active_original_path):
            self.orig_set_position(pos_ms)
            return

        if self.audio_start_ms <= pos_ms <= self.audio_end_ms:
            rel_pos = pos_ms - self.audio_start_ms
            self.orig_set_position(max(0, int(rel_pos)))
        else:
            if hasattr(self, 'audio_extract_thread') and self.audio_extract_thread and self.audio_extract_thread.isRunning():
                if getattr(self, 'pending_audio_start_ms', 0.0) <= pos_ms <= getattr(self, 'pending_audio_end_ms', 0.0):
                    return

            target_sec = pos_ms / 1000.0
            start_sec = max(0.0, target_sec - 10.0)
            duration_sec = 300.0
            if self.total_frames > 0 and self.fps > 0:
                total_duration_sec = self.total_frames / self.fps
                if start_sec + duration_sec > total_duration_sec:
                    duration_sec = max(0.0, total_duration_sec - start_sec)

            self.prepare_audio_track(
                self.currentFilePath,
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
        if getattr(self, 'is_loading_audio_chunk', False):
            return
        super().update_duration(duration)

    def advance_frame(self):
        try:
            super().advance_frame()
        except AttributeError:
            pass

        if self.fps > 0 and self.is_playing and self.isForward:
            if hasattr(self, 'audio_end_ms') and self.audio_end_ms > 0:
                current_pos_ms = (self.current_cache_index * 1000.0) / self.fps

                if current_pos_ms >= self.audio_end_ms:
                    if getattr(self, 'has_prefetched_chunk', False) and self.prefetched_original_path and os.path.exists(self.prefetched_original_path):
                        self.activate_prefetched_chunk(current_pos_ms)
                    else:
                        self.custom_set_position(current_pos_ms)
                elif self.audio_end_ms - current_pos_ms <= 5000:
                    is_extracting = (hasattr(self, 'prefetch_extract_thread') and self.prefetch_extract_thread and self.prefetch_extract_thread.isRunning()) or \
                                    (hasattr(self, 'audio_extract_thread') and self.audio_extract_thread and self.audio_extract_thread.isRunning())
                    
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

        if hasattr(self, 'prefetch_extract_thread') and self.prefetch_extract_thread and self.prefetch_extract_thread.isRunning():
            self.prefetch_extract_thread.terminate()
            self.prefetch_extract_thread.wait()

        base_dir = os.path.dirname(os.path.abspath(__file__))
        ffmpeg_path = os.path.join(base_dir, "..", "ffmpeg.exe" if os.name == 'nt' else "ffmpeg")
        ffmpeg_path = os.path.normpath(ffmpeg_path)
        if not os.path.exists(ffmpeg_path):
            ffmpeg_path = "ffmpeg"

        self.prefetch_extract_thread = AudioExtractionThread(
            self.currentFilePath, ffmpeg_path, target_original, 
            self.current_audio_track_index, next_start_sec, duration_sec
        )
        self.prefetch_extract_thread.finished_extraction.connect(self.on_prefetch_extracted)
        self.prefetch_extract_thread.start()

    def on_prefetch_extracted(self, path, start_time, duration):
        if not path or not os.path.exists(path):
            print("[AudioMixin] Pre-fetch extraction failed.")
            return
        
        self.prefetched_original_path = path
        self.prefetched_start_ms = start_time * 1000.0
        self.prefetched_end_ms = (start_time + duration) * 1000.0
        self.prefetched_duration_ms = duration * 1000.0
        self.has_prefetched_chunk = True
        print(f"[AudioMixin] Pre-fetched next chunk into {path} (start: {start_time}s)")

    def activate_prefetched_chunk(self, current_pos_ms):
        self.active_original_path = self.prefetched_original_path
        self.audio_start_ms = self.prefetched_start_ms
        self.audio_end_ms = self.prefetched_end_ms
        self.audio_duration_ms = self.prefetched_duration_ms
        self.has_prefetched_chunk = False

        rel_pos = current_pos_ms - self.audio_start_ms
        was_playing = self.is_playing

        self.is_loading_audio_chunk = True
        try:
            if self.config.get('audio_eq_enabled', False):
                self.pending_target_pos_ms = current_pos_ms
                self.apply_equalizer_filter()
            else:
                self.mediaPlayer.setSource(QUrl.fromLocalFile(self.active_original_path))
                self.orig_set_position(max(0, int(rel_pos)))
                if was_playing:
                    self.mediaPlayer.play()
        finally:
            self.is_loading_audio_chunk = False
        print(f"[AudioMixin] Pre-fetched chunk activated smoothly at {self.audio_start_ms / 1000.0}s")

    def recreate_media_player(self):
        super().recreate_media_player()
        self.setup_media_player_intercept()

    def cleanup_temp_audio(self):
        if hasattr(self, 'audio_extract_thread') and self.audio_extract_thread and self.audio_extract_thread.isRunning():
            self.audio_extract_thread.terminate()
            self.audio_extract_thread.wait()
        if hasattr(self, 'prefetch_extract_thread') and self.prefetch_extract_thread and self.prefetch_extract_thread.isRunning():
            self.prefetch_extract_thread.terminate()
            self.prefetch_extract_thread.wait()

        if hasattr(self, 'mediaPlayer'):
            self.mediaPlayer.setSource(QUrl())

        if hasattr(self, 'current_temp_dir') and self.current_temp_dir and os.path.exists(self.current_temp_dir):
            import shutil
            try:
                shutil.rmtree(self.current_temp_dir, ignore_errors=True)
            except Exception as e:
                print(f"[AudioMixin] Error cleaning up temp audio directory {self.current_temp_dir}: {e}")
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

        is_image = filePath.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff'))
        has_audio = hasattr(self, 'audio_tracks_info') and len(self.audio_tracks_info) > 0

        if not is_image and has_audio:
            duration_sec = 300.0
            if self.total_frames > 0 and self.fps > 0:
                total_duration_sec = self.total_frames / self.fps
                duration_sec = min(300.0, total_duration_sec)
            self.prepare_audio_track(filePath, 0, start_sec=0.0, duration_sec=duration_sec)
        else:
            if hasattr(self, 'audioTrackCombo'):
                self.audioTrackCombo.blockSignals(True)
                self.audioTrackCombo.clear()
                self.audioTrackCombo.addItem(tr('off'), -1)
                self.audioTrackCombo.blockSignals(False)

    def prepare_audio_track(self, video_path, track_index=0, start_sec=0.0, duration_sec=300.0, target_pos_ms=None):
        if not hasattr(self, 'current_temp_dir') or not self.current_temp_dir:
            import uuid
            import tempfile
            self.current_temp_dir = os.path.join(tempfile.gettempdir(), f"mem_cache_{uuid.uuid4().hex}")
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
        self.pending_audio_start_ms = start_sec * 1000
        self.pending_audio_end_ms = (start_sec + duration_sec) * 1000

        if hasattr(self, 'audio_extract_thread') and self.audio_extract_thread and self.audio_extract_thread.isRunning():
            self.audio_extract_thread.terminate()
            self.audio_extract_thread.wait()
        if hasattr(self, 'prefetch_extract_thread') and self.prefetch_extract_thread and self.prefetch_extract_thread.isRunning():
            self.prefetch_extract_thread.terminate()
            self.prefetch_extract_thread.wait()
        self.has_prefetched_chunk = False

        # Find FFmpeg binary path
        base_dir = os.path.dirname(os.path.abspath(__file__))
        ffmpeg_path = os.path.join(base_dir, "..", "ffmpeg.exe" if os.name == 'nt' else "ffmpeg")
        ffmpeg_path = os.path.normpath(ffmpeg_path)
        if not os.path.exists(ffmpeg_path):
            ffmpeg_path = "ffmpeg"

        self.audio_extract_thread = AudioExtractionThread(
            video_path, ffmpeg_path, target_original, track_index, start_sec, duration_sec
        )
        self.audio_extract_thread.finished_extraction.connect(self.on_audio_extracted)
        self.audio_extract_thread.start()

    def on_audio_extracted(self, path, start_time, duration):
        if not path or not os.path.exists(path):
            print("[AudioMixin] Audio extraction failed or returned invalid path.")
            return

        self.active_original_path = path
        self.audio_start_ms = start_time * 1000.0
        self.audio_end_ms = (start_time + duration) * 1000.0
        self.audio_duration_ms = duration * 1000.0

        self.populate_audio_tracks_ui()

        self.is_loading_audio_chunk = True
        try:
            if self.config.get('audio_eq_enabled', False):
                self.apply_equalizer_filter()
            else:
                pos = getattr(self, 'pending_target_pos_ms', self.audio_start_ms)
                if pos is None:
                    pos = self.audio_start_ms
                rel_pos = pos - self.audio_start_ms
                was_playing = self.is_playing
                
                self.mediaPlayer.setSource(QUrl.fromLocalFile(self.active_original_path))
                self.orig_set_position(max(0, int(rel_pos)))
                if was_playing:
                    self.mediaPlayer.play()
        finally:
            self.is_loading_audio_chunk = False
            self.pending_target_pos_ms = None

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
        print(f"[AudioMixin] Audio track changed. Re-extracting track {track_info['index']}...")
        
        # Calculate appropriate start and duration
        pos = self.mediaPlayer.position() # Virtual absolute position
        target_sec = pos / 1000.0
        start_sec = max(0.0, target_sec - 10.0)
        duration_sec = 300.0
        if self.total_frames > 0 and self.fps > 0:
            total_duration_sec = self.total_frames / self.fps
            if start_sec + duration_sec > total_duration_sec:
                duration_sec = max(0.0, total_duration_sec - start_sec)
        
        self.prepare_audio_track(self.currentFilePath, track_info['index'], start_sec, duration_sec, target_pos_ms=pos)

    def apply_equalizer_filter(self):
        if not hasattr(self, 'active_original_path') or not self.active_original_path or not os.path.exists(self.active_original_path):
            return

        # Alternate between filtered_audio_1 and filtered_audio_2 to bypass Windows file locks
        if self.active_filtered_path == self.filtered_audio_path_1:
            target_path = self.filtered_audio_path_2
        else:
            target_path = self.filtered_audio_path_1

        # Retrieve band gains
        gains = self.config.get('audio_eq_gains', [0]*10)
        freqs = [31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]

        # Construct filter string: "equalizer=f=31:width_type=o:w=1:g=X,equalizer=f=62:..."
        filters = []
        for f, g in zip(freqs, gains):
            filters.append(f"equalizer=f={f}:width_type=o:w=1:g={g}")
        filter_str = ",".join(filters)

        base_dir = os.path.dirname(os.path.abspath(__file__))
        ffmpeg_path = os.path.join(base_dir, "..", "ffmpeg.exe" if os.name == 'nt' else "ffmpeg")
        ffmpeg_path = os.path.normpath(ffmpeg_path)
        if not os.path.exists(ffmpeg_path):
            ffmpeg_path = "ffmpeg"

        cmd = [
            ffmpeg_path, "-y", "-i", self.active_original_path,
            "-af", filter_str,
            target_path
        ]

        try:
            creationflags = 0
            if os.name == 'nt':
                creationflags = subprocess.CREATE_NO_WINDOW
            subprocess.run(cmd, creationflags=creationflags, check=True)

            self.active_filtered_path = target_path
            
            # Switch QMediaPlayer source smoothly while preserving playback position
            pos = getattr(self, 'pending_target_pos_ms', None)
            if pos is None:
                pos = self.mediaPlayer.position() # Virtual absolute position
            
            rel_pos = pos - self.audio_start_ms
            was_playing = self.is_playing
            
            self.is_loading_audio_chunk = True
            try:
                self.mediaPlayer.setSource(QUrl.fromLocalFile(self.active_filtered_path))
                self.orig_set_position(max(0, int(rel_pos)))
                if was_playing:
                    self.mediaPlayer.play()
            finally:
                self.is_loading_audio_chunk = False
                self.pending_target_pos_ms = None
            print(f"[AudioMixin] Equalizer applied. Output written to {target_path}")
        except Exception as e:
            print(f"[AudioMixin] Error filtering audio with equalizer: {e}")
            self.pending_target_pos_ms = None

    def on_audio_eq_toggle_changed(self, checked):
        self.config['audio_eq_enabled'] = checked
        self.config.save()

        if checked:
            self.apply_equalizer_filter()
        else:
            # Revert to original audio (unfiltered)
            if hasattr(self, 'active_original_path') and self.active_original_path and os.path.exists(self.active_original_path):
                pos = self.mediaPlayer.position() # Virtual absolute position
                rel_pos = pos - self.audio_start_ms
                was_playing = self.is_playing
                
                self.is_loading_audio_chunk = True
                try:
                    self.mediaPlayer.setSource(QUrl.fromLocalFile(self.active_original_path))
                    self.orig_set_position(max(0, int(rel_pos)))
                    if was_playing:
                        self.mediaPlayer.play()
                finally:
                    self.is_loading_audio_chunk = False
                print("[AudioMixin] Equalizer disabled. Reverted to raw audio.")

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
        gains = presets.get(preset_name, [0]*10)
        
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
        gains = list(self.config.get('audio_eq_gains', [0]*10))
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
            if len(sizes) > 4 and sizes[4] < 250:
                sizes[4] = 250
                self.mainSplitter.setSizes(sizes)
