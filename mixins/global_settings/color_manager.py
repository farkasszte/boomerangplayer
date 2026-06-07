from PyQt6.QtWidgets import QColorDialog
from PyQt6.QtGui import QColor
from translations import tr

class GlobalSettingsColorManagerMixin:
    def choose_accent_color(self):
        # pyrefly: ignore [missing-attribute]
        current_hex = self.config.get('accent_color', '#00f2ff')
        # pyrefly: ignore [bad-argument-type]
        color = QColorDialog.getColor(QColor(current_hex), self, tr('select_color'))
        if color.isValid():
            self.pending_accent_color = color.name()
            self.apply_accent_color(self.pending_accent_color)

    def apply_accent_color(self, color_hex):
        # pyrefly: ignore [missing-attribute]
        self.config['accent_color'] = color_hex
        
        from qfluentwidgets import setThemeColor
        setThemeColor(QColor(color_hex))
        
        if hasattr(self, 'refresh_custom_styles'):
            self.refresh_custom_styles()

    def choose_bg_color(self):
        current_hex = self.pending_bg_color
        # pyrefly: ignore [bad-argument-type]
        color = QColorDialog.getColor(QColor(current_hex), self, tr('choose_bg_color'))
        if color.isValid():
            self.pending_bg_color = color.name()
            self.apply_bg_color(self.pending_bg_color)

    def apply_bg_color(self, color_hex):
        # pyrefly: ignore [missing-attribute]
        self.config['bg_color'] = color_hex
        if hasattr(self, 'refresh_custom_styles'):
            self.refresh_custom_styles()
        # pyrefly: ignore [missing-attribute]
        self.update_ui_texts()

    def on_panel_opacity_changed(self, value):
        self.pending_panel_opacity = value
        if hasattr(self, 'opacityValueLabel'):
            self.opacityValueLabel.setText(f"{value}%")
        if hasattr(self, 'refresh_custom_styles'):
            self.refresh_custom_styles()

    def on_inverse_text_changed(self, checked):
        # pyrefly: ignore [missing-attribute]
        self.config['inverse_text'] = checked
        
        from qfluentwidgets import setTheme, Theme
        setTheme(Theme.LIGHT if checked else Theme.DARK)

        if hasattr(self, 'refresh_custom_styles'):
            self.refresh_custom_styles()
        # pyrefly: ignore [missing-attribute]
        self.update_ui_texts()
