"""
VolumeMixin — volume control, mute toggle, flyout popup.
"""

from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QSlider
from qfluentwidgets import FluentIcon
from styles import FLUENT_SLIDER_STYLE
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QMainWindow, QLabel, QPushButton
    from PyQt6.QtMultimedia import QAudioOutput
    VolumeMixinBase = QMainWindow
else:
    VolumeMixinBase = object


class VolumeMixin(VolumeMixinBase):
    if TYPE_CHECKING:
        audioOutput: QAudioOutput
        volumeValueLabel: QLabel
        volumeButton: QPushButton
        userMutedIntent: bool
        volumePopup: QFrame

    def set_volume(self, volume):
        self.audioOutput.setVolume(volume / 100.0)
        self.volumeValueLabel.setText(f"{volume}%")
        is_muted = volume == 0
        self.userMutedIntent = is_muted
         ignore [bad-argument-type]
        self.volumeButton.setIcon(FluentIcon.MUTE if is_muted else FluentIcon.VOLUME)

    def toggle_mute(self):
        is_muted = not self.audioOutput.isMuted()
        self.audioOutput.setMuted(is_muted)
        self.userMutedIntent = is_muted
         ignore [bad-argument-type]
        self.volumeButton.setIcon(FluentIcon.MUTE if is_muted else FluentIcon.VOLUME)
        if is_muted:
            self.volumeValueLabel.setText("0%")
        else:
            vol = int(self.audioOutput.volume() * 100)
            self.volumeValueLabel.setText(f"{vol}%")

    def show_volume_flyout(self):
        self.volumePopup = QFrame(
            None, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
        )
        self.volumePopup.setObjectName("volumePopup")
        self.volumePopup.setStyleSheet("""
            #volumePopup {
                background: #202020;
                border: 1px solid #333;
                border-radius: 8px;
            }
        """)
        layout = QVBoxLayout(self.volumePopup)
        layout.setContentsMargins(10, 15, 10, 15)

        slider = QSlider(Qt.Orientation.Vertical)
        slider.setRange(0, 100)

        current_vol = int(self.audioOutput.volume() * 100)

        slider.setValue(current_vol)
        slider.setFixedHeight(150)
        slider.setStyleSheet(FLUENT_SLIDER_STYLE)
        slider.valueChanged.connect(self.set_volume)

        layout.addWidget(slider, 0, Qt.AlignmentFlag.AlignCenter)

        self.volumePopup.adjustSize()
        global_pos = self.volumeValueLabel.mapToGlobal(QPoint(0, 0))
        x = global_pos.x() + (self.volumeValueLabel.width() - self.volumePopup.width()) // 2
        y = global_pos.y() - self.volumePopup.height() - 8

        self.volumePopup.move(x, y)
        self.volumePopup.show()
