import os
import sys
import time
import shutil
import tempfile
import subprocess
import unittest

from PyQt6.QtWidgets import QApplication
from PyQt6.QtMultimedia import QMediaPlayer

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

from player_window import PlayerWindow
from utils import get_ffmpeg_path


def _wait_until(predicate, timeout_ms=4000, step_ms=25):
    deadline = time.monotonic() + (timeout_ms / 1000.0)
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(step_ms / 1000.0)
    app.processEvents()
    return predicate()


class TestAudioPlayback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp_dir = tempfile.mkdtemp(prefix="bp_audio_test_")
        ffmpeg = get_ffmpeg_path()
        cls.plain_mp3 = os.path.join(cls.tmp_dir, "plain.mp3")
        cls.art_mp3 = os.path.join(cls.tmp_dir, "with_art.mp3")
        cls.short_mp3 = os.path.join(cls.tmp_dir, "short.mp3")
        cover_jpg = os.path.join(cls.tmp_dir, "cover.jpg")

        subprocess.run(
            [ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=4", "-c:a", "libmp3lame", cls.plain_mp3],
            capture_output=True, check=True
        )
        subprocess.run(
            [ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=1.2", "-c:a", "libmp3lame", cls.short_mp3],
            capture_output=True, check=True
        )
        subprocess.run(
            [ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=red:s=64x64:d=1", "-vframes", "1", cover_jpg],
            capture_output=True, check=True
        )
        subprocess.run(
            [
                ffmpeg, "-y", "-i", cls.plain_mp3, "-i", cover_jpg,
                "-map", "0:a", "-map", "1:v", "-c", "copy",
                "-id3v2_version", "3", "-disposition:v", "attached_pic", cls.art_mp3
            ],
            capture_output=True, check=True
        )

        cls.win = PlayerWindow()
        cls.orig_eq_enabled = cls.win.config.get("audio_eq_enabled", False)
        cls.orig_loop_idx = cls.win.loopCombo.currentIndex()
        cls.win.audioOutput.setVolume(0.0)

    @classmethod
    def tearDownClass(cls):
        cls.win.stop_playback()
        cls.win.cleanup_temp_audio()
        cls.win.cleanup_cache()
        cls.win.config["audio_eq_enabled"] = cls.orig_eq_enabled
        cls.win.config.save()
        cls.win.config.flush()
        shutil.rmtree(cls.tmp_dir, ignore_errors=True)

    def setUp(self):
        self.win.stop_playback()
        self.win.cleanup_temp_audio()
        self.win.cleanup_cache()
        self.win.config["audio_eq_enabled"] = False
        self.win.userMutedIntent = False
        self.win.audioOutput.setMuted(False)
        self.win.audioOutput.setVolume(0.0)
        self.win.loopCombo.setCurrentIndex(3)

    def tearDown(self):
        self.win.stop_playback()
        self.win.cleanup_temp_audio()
        self.win.cleanup_cache()

    def test_ffprobe_classifies_plain_and_album_art_mp3_as_audio_only(self):
        for path in (self.plain_mp3, self.art_mp3):
            self.win.load_video(path)
            self.assertTrue(self.win.is_audio_only, f"Expected is_audio_only=True for {path}")
            self.assertEqual(self.win.fps, 30.0)
            # 4.0s * 30fps = ~120 frames (not MP3 packet count ~155+)
            self.assertGreaterEqual(self.win.total_frames, 115)
            self.assertLessEqual(self.win.total_frames, 125)
            self.assertIn(0, self.win.cached_frame_dict)
            ok = _wait_until(lambda: not self.win.is_loading_video, timeout_ms=1000)
            self.assertTrue(ok)

    def test_plain_mp3_immediate_play_and_stays_direct(self):
        self.win.load_video(self.plain_mp3)
        self.win.play_pause()

        ok = _wait_until(
            lambda: (
                self.win.mediaPlayer.playbackState() == QMediaPlayer.PlaybackState.PlayingState
                and self.win.mediaPlayer.position() > 50
            ),
            timeout_ms=4000
        )
        self.assertTrue(ok)
        self.assertTrue(self.win.is_playing)
        self.assertFalse(self.win.audioOutput.isMuted())
        self.assertIsNone(self.win.active_original_path)
        self.assertTrue(_wait_until(lambda: not self.win.is_loading_video, timeout_ms=1000))

    def test_album_art_mp3_plays_smoothly(self):
        self.win.load_video(self.art_mp3)
        self.win.play_pause()

        ok = _wait_until(
            lambda: (
                self.win.mediaPlayer.playbackState() == QMediaPlayer.PlaybackState.PlayingState
                and self.win.mediaPlayer.position() > 50
            ),
            timeout_ms=4000
        )
        self.assertTrue(ok)
        self.assertTrue(self.win.is_audio_only)
        self.assertFalse(self.win.audioOutput.isMuted())

    def test_mp3_with_eq_enabled_at_load_switches_without_silence(self):
        self.win.config["audio_eq_enabled"] = True
        self.win.load_video(self.plain_mp3)
        self.win.play_pause()

        ok = _wait_until(
            lambda: (
                self.win.active_filtered_path is not None
                and self.win._pending_media_source is None
                and self.win.mediaPlayer.playbackState() == QMediaPlayer.PlaybackState.PlayingState
                and self.win.mediaPlayer.mediaStatus() == QMediaPlayer.MediaStatus.BufferedMedia
            ),
            timeout_ms=5000
        )
        self.assertTrue(ok)
        self.assertFalse(self.win.audioOutput.isMuted())

    def test_mp3_enable_and_disable_eq_mid_playback(self):
        self.win.load_video(self.plain_mp3)
        self.win.play_pause()

        self.assertTrue(
            _wait_until(
                lambda: (
                    self.win.mediaPlayer.playbackState() == QMediaPlayer.PlaybackState.PlayingState
                    and self.win.mediaPlayer.position() > 200
                ),
                timeout_ms=4000
            )
        )

        # Enable EQ mid-playback -> triggers on-demand extraction + filter + seamless resume
        self.win.on_audio_eq_toggle_changed(True)
        self.assertTrue(
            _wait_until(
                lambda: (
                    self.win.active_filtered_path is not None
                    and self.win._pending_media_source is None
                    and self.win.mediaPlayer.playbackState() == QMediaPlayer.PlaybackState.PlayingState
                ),
                timeout_ms=5000
            )
        )
        self.assertFalse(self.win.audioOutput.isMuted())

        # Disable EQ mid-playback -> reverts to unfiltered audio and keeps playing
        self.win.on_audio_eq_toggle_changed(False)
        self.assertTrue(
            _wait_until(
                lambda: (
                    self.win.active_filtered_path is None
                    and self.win._pending_media_source is None
                    and self.win.mediaPlayer.playbackState() == QMediaPlayer.PlaybackState.PlayingState
                ),
                timeout_ms=4000
            )
        )
        self.assertFalse(self.win.audioOutput.isMuted())

    def test_forward_loop_wrap_resumes_after_end_of_media(self):
        self.win.loopCombo.setCurrentIndex(1)  # Forward loop
        self.win.load_video(self.short_mp3)
        self.win.play_pause()

        self.assertTrue(
            _wait_until(
                lambda: self.win.mediaPlayer.playbackState() == QMediaPlayer.PlaybackState.PlayingState,
                timeout_ms=3000
            )
        )

        # Jump near the end, let QMediaPlayer hit EndOfMedia if needed, and verify forward loop keeps playing
        near_end = max(0, self.win.total_frames - 4)
        self.win.set_position(near_end)

        ok = _wait_until(
            lambda: self.win.current_cache_index < max(5, near_end // 2),
            timeout_ms=2500
        )
        self.assertTrue(ok)
        self.assertTrue(
            _wait_until(
                lambda: (
                    self.win.mediaPlayer.playbackState() == QMediaPlayer.PlaybackState.PlayingState
                    and self.win.mediaPlayer.position() > 40
                ),
                timeout_ms=2500
            )
        )

    def test_backward_then_reload_forward_unmutes(self):
        self.win.load_video(self.plain_mp3)
        self.assertTrue(_wait_until(lambda: self.win._pending_media_source is None, timeout_ms=2000))

        self.win.play_pause_backward()
        self.assertTrue(self.win.audioOutput.isMuted())

        self.win.load_video(self.plain_mp3)
        self.win.play_pause()
        ok = _wait_until(
            lambda: self.win.mediaPlayer.playbackState() == QMediaPlayer.PlaybackState.PlayingState,
            timeout_ms=4000
        )
        self.assertTrue(ok)
        self.assertFalse(self.win.audioOutput.isMuted())

    def test_volume_set_and_toggle_mute_sync(self):
        self.win.toggle_mute()
        self.assertTrue(self.win.userMutedIntent)
        self.assertTrue(self.win.audioOutput.isMuted())

        self.win.set_volume(75)
        self.assertFalse(self.win.userMutedIntent)
        self.assertFalse(self.win.audioOutput.isMuted())

        self.win.set_volume(0)
        self.assertTrue(self.win.userMutedIntent)
        self.assertTrue(self.win.audioOutput.isMuted())

    def test_cleanup_temp_audio_resets_state_and_ignores_stale_extraction(self):
        self.win.active_original_path = self.plain_mp3
        self.win.audio_start_ms = 1000.0
        self.win.audio_end_ms = 5000.0
        self.win.has_prefetched_chunk = True
        stale_gen = self.win._audio_generation

        self.win.cleanup_temp_audio()

        self.assertIsNone(self.win.active_original_path)
        self.assertIsNone(self.win.active_filtered_path)
        self.assertEqual(self.win.audio_start_ms, 0.0)
        self.assertEqual(self.win.audio_end_ms, 0.0)
        self.assertFalse(self.win.has_prefetched_chunk)
        self.assertGreater(self.win._audio_generation, stale_gen)

        # Stale signal from before cleanup must be ignored
        self.win.on_audio_extracted(self.plain_mp3, 0.0, 4.0, gen=stale_gen)
        self.assertIsNone(self.win.active_original_path)


if __name__ == "__main__":
    unittest.main()
