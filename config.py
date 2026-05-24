import os
import json
from PyQt6.QtCore import Qt
from utils import get_config_path, DEFAULT_CONFIG

class Configuration(dict):
    """
    A dictionary-compatible Configuration Manager that automatically merges defaults,
    validates settings, and supports persistence operations.
    """
    def __init__(self):
        super().__init__()
        self.load()

    def load(self):
        self.clear()
        self.update(DEFAULT_CONFIG)
        
        path = get_config_path()
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # Prevent custom dictionary pollution and merge carefully
                    for k, v in data.items():
                        if k == 'shortcuts' and isinstance(v, dict):
                            # Merge shortcuts specifically
                            merged_shortcuts = DEFAULT_CONFIG['shortcuts'].copy()
                            merged_shortcuts.update(v)
                            self['shortcuts'] = merged_shortcuts
                        elif k == 'palette' and isinstance(v, list):
                            # Ensure palette is a valid list of hex colors
                            valid_palette = []
                            for color in v:
                                if isinstance(color, str) and color.startswith('#'):
                                    valid_palette.append(color.upper())
                            if valid_palette:
                                self['palette'] = valid_palette
                        else:
                            self[k] = v
            except Exception as e:
                print(f"Error loading configuration in Configuration class: {e}")

    def save(self):
        path = get_config_path()
        try:
            config_to_save = dict(self).copy()
            if 'markers_data' in config_to_save:
                del config_to_save['markers_data']
                
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(config_to_save, f, indent=4)
        except Exception as e:
            print(f"Error saving configuration in Configuration class: {e}")

    def __setitem__(self, key, value):
        # Validation Hooks
        if key == 'accent_color':
            if not isinstance(value, str) or not value.startswith('#'):
                value = '#00F2FF' # Reset to cyan fallback
            else:
                value = value.upper()
        elif key == 'bg_color':
            if not isinstance(value, str) or not value.startswith('#'):
                value = '#202020' # Reset to dark grey fallback
            else:
                value = value.upper()
        elif key == 'active_color_index':
            try:
                value = int(value)
            except (ValueError, TypeError):
                value = 2 # Reset to Red index
        elif key == 'panel_opacity':
            try:
                value = max(20, min(100, int(value)))
            except (ValueError, TypeError):
                value = 100
        
        super().__setitem__(key, value)
