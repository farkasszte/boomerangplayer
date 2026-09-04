import unittest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QPaintEvent
import sys

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

from player_window import PlayerWindow
from mixins.ui_mixin import PlayerInterface


class TestUIRendering(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.win = PlayerWindow()

    def test_player_interface_attributes(self):
        pi = self.win.playerInterface
        self.assertIsInstance(pi, PlayerInterface)
        self.assertTrue(pi.testAttribute(Qt.WidgetAttribute.WA_StyledBackground))
        self.assertTrue(pi.testAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent))
        self.assertTrue(pi.autoFillBackground())

    def test_player_interface_paint_event(self):
        pi = self.win.playerInterface
        event = QPaintEvent(QRect(0, 0, 100, 100))
        # Ensure paintEvent executes cleanly without error
        try:
            pi.paintEvent(event)
        except Exception as e:
            self.fail(f"paintEvent raised exception: {e}")

    def test_controls_card_attributes(self):
        cc = self.win.controlsCard
        self.assertTrue(cc.testAttribute(Qt.WidgetAttribute.WA_StyledBackground))
        self.assertTrue(cc.autoFillBackground())

    def test_stacked_widget_attributes(self):
        sw = self.win.stackedWidget
        self.assertTrue(sw.testAttribute(Qt.WidgetAttribute.WA_StyledBackground))
        self.assertTrue(sw.autoFillBackground())


if __name__ == '__main__':
    unittest.main()
