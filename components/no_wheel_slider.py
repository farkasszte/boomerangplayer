from PyQt6.QtWidgets import QSlider


class NoWheelSlider(QSlider):
    def wheelEvent(self, event):
        event.ignore()
