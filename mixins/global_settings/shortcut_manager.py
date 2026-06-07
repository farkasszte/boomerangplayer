from PyQt6.QtCore import Qt
from qfluentwidgets import InfoBar, InfoBarPosition
from translations import tr

class GlobalSettingsShortcutManagerMixin:
    def update_shortcut_sidebar(self, action_name, new_key):
        # pyrefly: ignore [missing-attribute]
        self.shortcuts[action_name] = new_key
        # pyrefly: ignore [missing-attribute]
        self.config['shortcuts'] = self.shortcuts
        if hasattr(self, 'setup_shortcuts'):
            self.setup_shortcuts()

    def save_global_settings(self):
        # pyrefly: ignore [missing-attribute]
        self.config['accent_color'] = self.pending_accent_color
        # pyrefly: ignore [missing-attribute]
        self.config['bg_color'] = self.pending_bg_color
        # pyrefly: ignore [missing-attribute]
        self.config['panel_opacity'] = self.pending_panel_opacity
        
        # Save via Configuration Manager
        # pyrefly: ignore [missing-attribute]
        if hasattr(self.config, 'save'):
            # pyrefly: ignore [missing-attribute]
            self.config.save()
        else:
            from utils import save_config
            save_config(self.config)
        
        # Visual feedback
        InfoBar.success(
            title=tr('settings'),
            content=tr('save_settings') + " " + tr('ok'),
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )
