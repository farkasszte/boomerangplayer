from PyQt6.QtWidgets import QSlider
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QPainter, QColor, QPen


class EqBandSlider(QSlider):
    """Vertical slider that paints accent only between 0 and the handle."""

    def __init__(self, accent_color='#00f2ff', parent=None):
        super().__init__(Qt.Orientation.Vertical, parent)
        self._accent = QColor(accent_color)
        self._neutral = QColor('#444')
        self._handle_color = QColor(accent_color)
        self.setRange(-12, 12)

    def setAccentColor(self, color):
        self._accent = QColor(color)
        self._handle_color = QColor(color)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        groove_x = w // 2
        groove_w = 4
        handle_w, handle_h = 14, 10
        margin = (handle_w - groove_w) // 2

        groove_top = margin
        groove_bot = h - margin
        groove_h = groove_bot - groove_top

        min_val, max_val = self.minimum(), self.maximum()
        val = self.value()

        def val_to_y(v):
            ratio = (v - min_val) / (max_val - min_val)
            return int(groove_bot - ratio * groove_h)

        center_y = val_to_y(0)
        handle_y = val_to_y(val)

        # Draw groove (full, neutral)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._neutral)
        painter.drawRoundedRect(groove_x - groove_w // 2, groove_top, groove_w, groove_h, 2, 2)

        # Draw accent between 0 and handle
        if val > 0:
            accent_top = center_y
            accent_bot = handle_y + handle_h // 2
            accent_rect = QRect(groove_x - groove_w // 2, accent_top, groove_w, accent_bot - accent_top)
        elif val < 0:
            accent_top = handle_y - handle_h // 2
            accent_bot = center_y
            accent_rect = QRect(groove_x - groove_w // 2, accent_top, groove_w, accent_bot - accent_top)
        else:
            accent_rect = QRect()

        if not accent_rect.isNull():
            painter.setBrush(self._accent)
            painter.drawRoundedRect(accent_rect, 2, 2)

        # Draw handle
        handle_rect = QRect(groove_x - handle_w // 2, handle_y - handle_h // 2, handle_w, handle_h)
        painter.setBrush(self._handle_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(handle_rect, 2, 2)

        painter.end()
