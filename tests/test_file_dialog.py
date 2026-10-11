import sys
import unittest
from PyQt6.QtWidgets import QApplication, QListWidgetItem
from PyQt6.QtGui import QImage, QPixmap
from mixins.file_dialog import MediaFileDialog


app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)


class TestMediaFileDialog(unittest.TestCase):
    def setUp(self):
        self.config = {
            'inverse_text': False,
            'accent_color': '#00f2ff',
            'bg_color': '#202020',
            'panel_opacity': 100,
        }
        self.dialog = MediaFileDialog(None, self.config)

    def tearDown(self):
        self.dialog.close()

    def test_on_thumb_with_image(self):
        item = QListWidgetItem()
        path = "test_video.mp4"
        self.dialog._thumb_items_by_path[path] = item
        self.dialog._thumb_pending.add(path)

        img = QImage(160, 160, QImage.Format.Format_ARGB32)
        img.fill(0)

        # _on_thumb receives (item, path, pixmap)
        self.dialog._on_thumb(item, path, img)

        self.assertNotIn(path, self.dialog._thumb_pending)
        self.assertIn(path, self.dialog._thumb_done)
        self.assertFalse(item.icon().isNull())

    def test_on_thumb_with_str_does_not_crash(self):
        # Even if a string or invalid type is passed, it should not raise AttributeError
        item = QListWidgetItem()
        path = "dummy.mp4"
        self.dialog._thumb_items_by_path[path] = item
        self.dialog._thumb_pending.add(path)

        # Should not raise AttributeError: 'str' object has no attribute 'isNull'
        self.dialog._on_thumb(item, path, "invalid_str_payload")

        self.assertNotIn(path, self.dialog._thumb_pending)
        self.assertIn(path, self.dialog._thumb_done)
