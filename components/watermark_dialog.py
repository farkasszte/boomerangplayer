"""
WatermarkPropertiesDialog — configuration dialog for watermarks in the drawing view.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSlider
from qfluentwidgets import PushButton
from styles import ACTION_BTN_STYLE
from translations import tr


class WatermarkPropertiesDialog(QDialog):
    def __init__(self, item, parent=None):
        super().__init__(parent)
        self.item = item
        self.setWindowTitle(tr('watermark_properties'))
        self.setFixedWidth(300)
        self.setStyleSheet("background: #202020; color: white;")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)
        
        # Opacity Slider
        opacity_layout = QHBoxLayout()
        self.opacity_lbl = QLabel(f"{tr('watermark_opacity_title')}: {int(item.opacity() * 100)}%")
        self.opacity_lbl.setStyleSheet("color: white; font-size: 12px; border: none;")
        opacity_layout.addWidget(self.opacity_lbl)
        
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(int(item.opacity() * 100))
        
        layout.addLayout(opacity_layout)
        layout.addWidget(self.slider)
        
        # Live preview connection
        self.slider.valueChanged.connect(self.on_opacity_changed)
        
        # Scale Slider
        scale_layout = QHBoxLayout()
        self.scale_lbl = QLabel(f"{tr('watermark_scale')}: 100%")
        self.scale_lbl.setStyleSheet("color: white; font-size: 12px; border: none;")
        scale_layout.addWidget(self.scale_lbl)
        
        self.scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.scale_slider.setRange(10, 300)
        self.scale_slider.setValue(100)
        
        layout.addLayout(scale_layout)
        layout.addWidget(self.scale_slider)
        
        self.scale_slider.valueChanged.connect(self.on_scale_changed)
        self.original_pixmap = item.pixmap()
        self.original_scale = 1.0
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.delete_btn = PushButton(tr('delete'))
        self.delete_btn.setStyleSheet(ACTION_BTN_STYLE)
        self.delete_btn.clicked.connect(self.on_delete)
        self.ok_btn = PushButton(tr('ok'))
        self.ok_btn.setStyleSheet(ACTION_BTN_STYLE)
        self.ok_btn.clicked.connect(self.accept)
        
        btn_layout.addWidget(self.delete_btn)
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.ok_btn)
        layout.addLayout(btn_layout)
        
    def on_opacity_changed(self, val):
        opacity = val / 100.0
        self.item.setOpacity(opacity)
        self.opacity_lbl.setText(f"{tr('watermark_opacity_title')}: {val}%")
        
    def on_scale_changed(self, val):
        scale = val / 100.0
        w = int(self.original_pixmap.width() * scale)
        h = int(self.original_pixmap.height() * scale)
        scaled_pix = self.original_pixmap.scaled(
            max(1, w), max(1, h),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.item.setPixmap(scaled_pix)
        self.scale_lbl.setText(f"{tr('watermark_scale')}: {val}%")
        
    def on_delete(self):
        self.done(2)
