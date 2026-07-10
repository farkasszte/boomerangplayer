from PyQt6.QtWidgets import QColorDialog
from PyQt6.QtGui import QColor
from translations import tr

class GlobalSettingsColorManagerMixin:
    def choose_accent_color(self):
        
        current_hex = self.config.get('accent_color', '#00f2ff')
        color = QColorDialog.getColor(QColor(current_hex), self, tr('select_color'))
        if color.isValid():
            self.pending_accent_color = color.name()
            self.apply_accent_color(self.pending_accent_color)

    def apply_accent_color(self, color_hex):
        
        self.config['accent_color'] = color_hex
        self.accent_color = color_hex
        
        from qfluentwidgets import setThemeColor
        setThemeColor(QColor(color_hex))
        
        if hasattr(self, 'refresh_custom_styles'):
            self.refresh_custom_styles()

    def choose_bg_color(self):
        current_hex = self.pending_bg_color
        color = QColorDialog.getColor(QColor(current_hex), self, tr('choose_bg_color'))
        if color.isValid():
            self.pending_bg_color = color.name()
            self.apply_bg_color(self.pending_bg_color)

    def apply_bg_color(self, color_hex):
        
        self.config['bg_color'] = color_hex

        from styles import wcag_contrast_ratio
        dark_fg = "#ffffff"
        light_fg = "#1c1c1c"

        ratio_dark = wcag_contrast_ratio(color_hex, dark_fg)
        ratio_light = wcag_contrast_ratio(color_hex, light_fg)

        current_inverse = self.config.get('inverse_text', False)

        if current_inverse:
            needs_switch = ratio_light < 1.5 and ratio_dark >= ratio_light
        else:
            needs_switch = ratio_dark < 1.5 and ratio_light >= ratio_dark

        if needs_switch:
            new_inverse = not current_inverse
            self.config['inverse_text'] = new_inverse
            if hasattr(self, 'inverseTextToggle'):
                self.inverseTextToggle.blockSignals(True)
                self.inverseTextToggle.setChecked(new_inverse)
                self.inverseTextToggle.blockSignals(False)

            from qfluentwidgets import setTheme, Theme
            setTheme(Theme.LIGHT if new_inverse else Theme.DARK)

            from PyQt6.QtCore import Qt
            from qfluentwidgets import InfoBar, InfoBarPosition
            InfoBar.info(
                title=tr('auto_theme_switch'),
                content=tr('auto_theme_switch_desc'),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )

        if hasattr(self, 'refresh_custom_styles'):
            self.refresh_custom_styles()
        
        self.update_ui_texts()

    def on_panel_opacity_changed(self, value):
        snapped = round(value / 5) * 5
        snapped = max(20, min(100, snapped))
        self.opacitySlider.blockSignals(True)
        self.opacitySlider.setValue(snapped)
        self.opacitySlider.blockSignals(False)
        self.pending_panel_opacity = snapped
        if hasattr(self, 'opacityValueLabel'):
            self.opacityValueLabel.setText(f"{snapped}%")
        if not hasattr(self, '_opacity_debounce'):
            from PyQt6.QtCore import QTimer
            self._opacity_debounce = QTimer()
            self._opacity_debounce.setSingleShot(True)
            self._opacity_debounce.setInterval(150)
            self._opacity_debounce.timeout.connect(self._apply_opacity)
        self._opacity_debounce.start()

    def _apply_opacity(self):
        if hasattr(self, 'refresh_custom_styles'):
            self.refresh_custom_styles()

    def on_inverse_text_changed(self, checked):
        
        self.config['inverse_text'] = checked
        
        from qfluentwidgets import setTheme, Theme
        setTheme(Theme.LIGHT if checked else Theme.DARK)

        if hasattr(self, 'refresh_custom_styles'):
            self.refresh_custom_styles()
        
        self.update_ui_texts()
