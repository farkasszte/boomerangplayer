import os
import json
from PyQt6.QtCore import Qt
from utils import get_config_path, DEFAULT_CONFIG, validate_config, logger

class Configuration(dict):
    """
    A dictionary-compatible Configuration Manager that automatically merges defaults,
    validates settings, and supports persistence operations.
    """
    def __init__(self):
        self._loading = True
        super().__init__()
        self.load()

    def load(self):
        self._loading = True
        try:
            self.clear()
            self.update(DEFAULT_CONFIG)
            
            path = get_config_path()
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        validated = validate_config(data)
                        self.update(validated)
                except Exception as e:
                    logger.error(f"Error loading configuration in Configuration class: {e}")
        finally:
            self._loading = False

    def save(self):
        path = get_config_path()
        try:
            config_to_save = validate_config(self)
            if 'markers_data' in config_to_save:
                del config_to_save['markers_data']
                
            temp_path = path + ".tmp"
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(config_to_save, f, indent=4)
            os.replace(temp_path, path)
        except Exception as e:
            logger.error(f"Error saving configuration in Configuration class: {e}")

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
        if not getattr(self, '_loading', False):
            self.save()

    def update(self, *args, **kwargs):
        was_loading = getattr(self, '_loading', False)
        self._loading = True
        try:
            super().update(*args, **kwargs)
        finally:
            self._loading = was_loading
        if not self._loading:
            self.save()
