from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QPen, QColor
from PyQt6.QtWidgets import QSlider

class MarkerSlider(QSlider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.markers = []
        self.is_zoomed = False
        
    def update_markers(self, markers):
        self.markers = sorted(list(set(markers)))
        self.update()

    def set_zoomed(self, enabled):
        self.is_zoomed = enabled
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            r = self.maximum() - self.minimum()
            if r > 0:
                val = self.minimum() + (r * event.position().x()) / self.width()
                self.setValue(int(val))
                self.sliderMoved.emit(int(val))
        super().mousePressEvent(event)

    def paintEvent(self, event):
        if self.maximum() <= self.minimum():
            super().paintEvent(event)
            return

        w = self.width()
        h = self.height()
        r = self.maximum() - self.minimum()

        # 1. Draw Zoom Highlight BACKGROUND before the slider itself
        if self.is_zoomed:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            # Use a very subtle dark cyan tint for the background
            painter.setOpacity(0.15)
            painter.setBrush(QColor(0, 242, 255))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(0, 0, w, h)
            # Draw a slightly more visible border
            painter.setOpacity(0.4)
            painter.setPen(QPen(QColor(0, 242, 255), 1))
            painter.drawRect(0, 0, w-1, h-1)
            painter.end()

        # 2. Draw the standard QSlider (groove, sub-page/accent, handle)
        super().paintEvent(event)

        # 3. Draw Markers OVER the slider
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(0, 153, 255))
        pen.setWidth(2)
        painter.setPen(pen)
        
        for m in self.markers:
            if self.minimum() < m < self.maximum():
                mx = int(((m - self.minimum()) / r) * w)
                painter.drawLine(mx, 0, mx, h)
        painter.end()
