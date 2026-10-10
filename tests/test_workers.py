import sys
import os
import unittest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QImage
from workers.threads import ThumbnailThread, AudioExtractionThread

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

class TestWorkers(unittest.TestCase):
    def test_audio_extraction_thread_cancel(self):
        thread = AudioExtractionThread("dummy.mp4", "ffmpeg", "output.wav")
        self.assertFalse(thread._is_cancelled)
        
        mock_proc = MagicMock()
        thread.process = mock_proc
        thread.cancel()
        
        self.assertTrue(thread._is_cancelled)
        mock_proc.kill.assert_called_once()

    def test_thumbnail_thread_image_loading(self):
        # Create a small dummy image in temp folder
        import tempfile
        tmp_dir = tempfile.mkdtemp()
        img_path = os.path.join(tmp_dir, "test.png")
        
        qimg = QImage(100, 100, QImage.Format.Format_RGB32)
        qimg.fill(0xFF00FF)
        qimg.save(img_path)

        thread = ThumbnailThread(img_path)
        emitted_results = []
        thread.thumbnail_ready.connect(lambda path, img: emitted_results.append((path, img)))
        
        thread.run()
        
        self.assertEqual(len(emitted_results), 1)
        res_path, res_img = emitted_results[0]
        self.assertEqual(res_path, img_path)
        self.assertFalse(res_img.isNull())
        self.assertEqual(res_img.width(), 160)
        self.assertEqual(res_img.height(), 160)

        # Cleanup
        try:
            os.remove(img_path)
            os.rmdir(tmp_dir)
        except OSError:
            pass

    def test_thumbnail_thread_cancel(self):
        thread = ThumbnailThread("dummy.mp4")
        mock_proc = MagicMock()
        thread.process = mock_proc
        thread.cancel()
        self.assertTrue(thread._is_cancelled)
        mock_proc.kill.assert_called_once()

    def test_process_monitor_thread_cancel(self):
        from workers.threads import ProcessMonitorThread
        mock_proc = MagicMock()
        thread = ProcessMonitorThread(mock_proc, "output.mp4")
        thread.cancel()
        self.assertTrue(thread._is_cancelled)
        mock_proc.kill.assert_called_once()
