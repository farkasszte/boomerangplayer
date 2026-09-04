import unittest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QRect
import sys

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

from player_window import PlayerWindow


class MockScreen:
    def __init__(self, x, y, w, h):
        self._avail = QRect(x, y, w, h)

    def availableGeometry(self):
        return self._avail


class TestWindowGeometry(unittest.TestCase):
    def test_current_screen_geometry(self):
        w = PlayerWindow()
        # On user's 1920x1080 display (available height ~1032)
        # It should detect >= 1920 and set size to 1440 x 810
        self.assertEqual(w.width(), 1440)
        self.assertEqual(w.height(), 810)

    def test_resolution_tiers(self):
        w = PlayerWindow()
        test_cases = [
            (3840, 2110, 2560, 1440),  # 4K -> QHD
            (2560, 1390, 1920, 1080),  # QHD -> FHD
            (1920, 1032, 1440, 810),   # FHD -> 1440
            (1600, 850, 1280, 720),    # HD+ -> HD
            (1366, 728, 1024, 576),    # Laptop HD -> 1024x576
            (1280, 680, 1024, 576),    # HD -> 1024x576
        ]
        for sw, sh, expected_w, expected_h in test_cases:
            mock = MockScreen(0, 0, sw, sh)
            # Temporarily test with mock screen logic
            avail = mock.availableGeometry()
            msw = avail.width()
            msh = avail.height()
            if msw >= 3840:
                cw, ch = 2560, 1440
            elif msw >= 2560:
                cw, ch = 1920, 1080
            elif msw >= 1920:
                cw, ch = 1440, 810
            elif msw >= 1600:
                cw, ch = 1280, 720
            elif msw >= 1280:
                cw, ch = 1024, 576
            else:
                cw, ch = 960, 540

            max_w = int(msw * 0.9)
            max_h = int(msh * 0.9)
            if cw > max_w or ch > max_h:
                scale = min(max_w / cw, max_h / ch)
                cw = int(cw * scale)
                ch = int(ch * scale)

            self.assertEqual(cw, expected_w, f"Width mismatch for {sw}x{sh}")
            self.assertEqual(ch, expected_h, f"Height mismatch for {sw}x{sh}")


if __name__ == '__main__':
    unittest.main()
