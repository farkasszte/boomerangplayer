"""
WatermarkPropertiesDialog — configuration dialog for watermarks in the drawing view.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel
from .no_wheel_slider import NoWheelSlider
from qfluentwidgets import PushButton
from styles import ACTION_BTN_STYLE, get_color_tokens
from translations import tr


def _apply_dwm(dialog, bg, fg):
    import sys
    if sys.platform != 'win32':
        return
    try:
        import ctypes
        from PyQt6.QtGui import QColor
        hwnd = int(dialog.winId())
        def _ref(c):
            color = QColor(c)
            return color.red() | (color.green() << 8) | (color.blue() << 16)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 35, ctypes.byref(ctypes.c_int(_ref(bg))), 4)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 36, ctypes.byref(ctypes.c_int(_ref(fg))), 4)
    except Exception:
        pass


class WatermarkPropertiesDialog(QDialog):
    def __init__(self, item, parent=None):
        super().__init__(parent)
        self.item = item
        # Try to get tokens from parent player, fallback to defaults
        config = getattr(parent, 'config', None)
        if config:
            t = get_color_tokens(
                config.get('accent_color', '#00f2ff'),
                config.get('bg_color', '#202020'),
                config.get('inverse_text', False)
            )
        else:
            t = get_color_tokens()
        self.setWindowTitle(tr('watermark_properties'))
        self.setFixedWidth(300)
        self.setStyleSheet(f"background: {t['bg']}; color: {t['fg']};")
        _apply_dwm(self, t['bg'], t['fg'])
        if config:
            opacity = config.get('panel_opacity', 100)
            self.setWindowOpacity(opacity / 100.0)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        
        # Opacity Slider
        opacity_layout = QHBoxLayout()
        self.opacity_lbl = QLabel(f"{tr('watermark_opacity_title')}: {int(item.opacity() * 100)}%")
        self.opacity_lbl.setStyleSheet(f"color: {t['fg']}; font-size: 12px; border: none;")
        opacity_layout.addWidget(self.opacity_lbl)
        
        self.slider = NoWheelSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(int(item.opacity() * 100))
        
        layout.addLayout(opacity_layout)
        layout.addWidget(self.slider)
        
        # Live preview connection
        self.slider.valueChanged.connect(self.on_opacity_changed)
        
        # Scale Slider
        scale_layout = QHBoxLayout()
        self.scale_lbl = QLabel(f"{tr('watermark_scale')}: 100%")
        self.scale_lbl.setStyleSheet(f"color: {t['fg']}; font-size: 12px; border: none;")
        scale_layout.addWidget(self.scale_lbl)
        
        self.scale_slider = NoWheelSlider(Qt.Orientation.Horizontal)
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
