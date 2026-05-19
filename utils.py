import os
import sys
import json
from PyQt6.QtCore import Qt
VERSION = "1.6"

def get_base_path():
    """ Get the directory where the application is located (next to .exe if bundled) """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def format_time(ms):
    if ms is None: return "0:00"
    ms = int(ms)
    seconds = (ms // 1000) % 60
    minutes = (ms // (1000 * 60)) % 60
    hours = (ms // (1000 * 60 * 60))
    if hours > 0:
        return f"{hours}:{minutes:02}:{seconds:02}"
    return f"{minutes}:{seconds:02}"

def qt_message_handler(mode, context, message):
    # Suppress common but harmless Qt warnings that clutter the console
    suppressed = [
        "QFont::setPointSize: Point size <= 0",
    ]
    if any(s in message for s in suppressed):
        return
    if not message.strip():
        return
    # Print non-suppressed messages so real Qt errors are visible
    import sys
    print(message, file=sys.stderr)

DEFAULT_CONFIG = {
    'language': 'en',
    'audio_device': '',
    'shortcuts': {
        'play_pause': Qt.Key.Key_Space,
        'smart_mark': Qt.Key.Key_S,
        'toggle_loop': Qt.Key.Key_L,
        'next_frame': Qt.Key.Key_Period,
        'prev_frame': Qt.Key.Key_Comma,
        'toggle_mute': Qt.Key.Key_M,
        'act_full_screen': Qt.Key.Key_F
    },
    'palette': ['#000000', '#FFFFFF', '#FF0000', '#FFFF00', '#00FF00', '#0000FF'],
    'active_color_index': 2 # Default to Red
}

def get_config_path():
    return os.path.join(get_base_path(), "config.json")

def get_markers_path():
    return os.path.join(get_base_path(), "markers.json")

def load_config():
    path = get_config_path()
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # Merge with default to ensure all keys exist
                merged = DEFAULT_CONFIG.copy()
                merged.update(config)
                # Ensure shortcuts are properly merged too
                if 'shortcuts' in config:
                    merged['shortcuts'] = DEFAULT_CONFIG['shortcuts'].copy()
                    merged['shortcuts'].update(config['shortcuts'])
                return merged
        except Exception as e:
            print(f"Error loading config: {e}")
    return DEFAULT_CONFIG.copy()

def save_config(config):
    path = get_config_path()
    try:
        # Don't save markers_data to config anymore
        config_to_save = config.copy()
        if 'markers_data' in config_to_save:
            del config_to_save['markers_data']
            
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(config_to_save, f, indent=4)
    except Exception as e:
        print(f"Error saving config: {e}")

def load_markers():
    path = get_markers_path()
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading markers: {e}")
    return {}

def save_markers(markers_data):
    path = get_markers_path()
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(markers_data, f, indent=4)
    except Exception as e:
        print(f"Error saving markers: {e}")

def cleanup_nvidia_dxcache():
    """ Garbage collect Nvidia DXCache (.nvph) files to prevent disk exhaustion.
    Only files older than 15 minutes are targeted, and locked files are safely skipped.
    Runs asynchronously in a background daemon thread to avoid blocking startup.
    """
    import threading
    
    def worker():
        try:
            local_app_data = os.environ.get('LOCALAPPDATA')
            if not local_app_data:
                return
            
            dxcache_dir = os.path.join(local_app_data, 'Nvidia', 'DXCache')
            if not os.path.exists(dxcache_dir) or not os.path.isdir(dxcache_dir):
                return
            
            import time
            now = time.time()
            deleted_count = 0
            freed_bytes = 0
            
            for filename in os.listdir(dxcache_dir):
                if filename.lower().endswith('.nvph'):
                    file_path = os.path.join(dxcache_dir, filename)
                    try:
                        # Safety check: only delete files older than 15 minutes (900 seconds)
                        mtime = os.path.getmtime(file_path)
                        if now - mtime > 900:
                            file_size = os.path.getsize(file_path)
                            os.remove(file_path)
                            deleted_count += 1
                            freed_bytes += file_size
                    except (PermissionError, OSError):
                        # File is locked or in use, skip it
                        continue
            
            if deleted_count > 0:
                print(f"[DXCache GC] Cleaned up {deleted_count} .nvph files, freeing {freed_bytes / (1024 * 1024):.2f} MB.")
        except Exception as e:
            print(f"[DXCache GC] Error running cache cleanup: {e}")

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

