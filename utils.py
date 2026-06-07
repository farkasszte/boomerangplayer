import os
import sys
import json
from PyQt6.QtCore import Qt
VERSION = "2.5"

def get_base_path():
    """ Get the directory where the application is located (next to .exe if bundled) """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        # pyrefly: ignore [missing-attribute]
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


def format_chrono_time(ms):
    """Format milliseconds as MM:SS.mmm for chronometer display."""
    if ms is None:
        return "00:00.000"
    ms = int(ms)
    minutes = (ms // (1000 * 60)) % 60
    seconds = (ms // 1000) % 60
    millis = ms % 1000
    return f"{minutes:02}:{seconds:02}.{millis:03d}"

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
    'panel_opacity': 100,
    'speed_locked': False,
    'inverse_text': False,
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
                
                # Force gpu_acceleration to True as we rely on the internal fallback now
                merged['gpu_acceleration'] = True
                
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
    """ Garbage collect ONLY the Nvidia DXCache (.nvph) files created by our application.
    Runs asynchronously in a background daemon thread.
    - At startup: deletes files from the previous session (now unlocked) and records current files.
    - After 5 seconds: scans again to detect which new files were created by this session.
    """
    import threading
    import time
    import json
    
    def worker():
        try:
            local_app_data = os.environ.get('LOCALAPPDATA')
            if not local_app_data:
                return
            
            dxcache_dir = os.path.join(local_app_data, 'Nvidia', 'DXCache')
            if not os.path.exists(dxcache_dir) or not os.path.isdir(dxcache_dir):
                return
            
            # Step 1: Clean up files from previous sessions
            session_path = os.path.join(get_base_path(), "dxcache_session.json")
            config = load_config()
            old_files = config.get('dxcache_files', [])
            
            # Migrate old dxcache_session.json file if it exists and delete it
            if os.path.exists(session_path):
                try:
                    with open(session_path, 'r') as f:
                        migrated_files = json.load(f)
                        if isinstance(migrated_files, list):
                            old_files = list(set(old_files + migrated_files))
                    os.remove(session_path)
                except Exception:
                    pass
            
            deleted_count = 0
            remaining_old_files = []
            for filepath in old_files:
                if os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                        deleted_count += 1
                    except (PermissionError, OSError):
                        # Still locked, keep in the list
                        remaining_old_files.append(filepath)
            
            if deleted_count > 0:
                print(f"[DXCache GC] Cleaned up {deleted_count} stale cache files from previous session.")
            
            # Step 2: Record current files to detect new ones
            try:
                initial_files = set(os.listdir(dxcache_dir))
            except OSError:
                return
                
            # Step 3: Wait for OpenGL / Shaders to compile and initialize (5 seconds)
            time.sleep(5)
            
            # Step 4: Scan again to detect our session files
            try:
                current_files = set(os.listdir(dxcache_dir))
            except OSError:
                return
                
            new_files = current_files - initial_files
            session_filepaths = []
            for filename in new_files:
                if filename.lower().endswith('.nvph'):
                    session_filepaths.append(os.path.join(dxcache_dir, filename))
            
            # Save our session files (merge with any remaining old locked files)
            combined_files = list(set(remaining_old_files + session_filepaths))
            try:
                config = load_config()
                config['dxcache_files'] = combined_files
                save_config(config)
            except Exception:
                pass
                
        except Exception as e:
            print(f"[DXCache GC] Error during cache tracking: {e}")
            
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()


def send_to_recycle_bin(path):
    """ Moves the specified file to the Windows Recycle Bin (Lomtár) using ctypes SHFileOperationW.
    Returns True if successful, False otherwise.
    """
    if os.name != 'nt':
        try:
            if os.path.exists(path):
                os.remove(path)
                return True
        except Exception as e:
            print(f"Error deleting file: {e}")
            return False
        return False

    import ctypes
    from ctypes import wintypes

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _pack_ = 1 if ctypes.sizeof(ctypes.c_void_p) == 4 else 8
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("wFunc", wintypes.UINT),
            ("pFrom", wintypes.LPCWSTR),
            ("pTo", wintypes.LPCWSTR),
            ("fFlags", ctypes.c_ushort),
            ("fAnyOperationsAborted", wintypes.BOOL),
            ("hNameMappings", wintypes.LPVOID),
            ("lpszProgressTitle", wintypes.LPCWSTR)
        ]

    FO_DELETE = 3
    FOF_ALLOWUNDO = 0x0040
    FOF_NOCONFIRMATION = 0x0010

    if not os.path.exists(path):
        return False

    try:
        abs_path = os.path.abspath(path)
        p_from = abs_path + "\0\0"

        fileop = SHFILEOPSTRUCTW()
        fileop.hwnd = None
        fileop.wFunc = FO_DELETE
        fileop.pFrom = p_from
        fileop.pTo = None
        fileop.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION
        fileop.fAnyOperationsAborted = False
        fileop.hNameMappings = None
        fileop.lpszProgressTitle = None

        shell32 = ctypes.windll.shell32
        result = shell32.SHFileOperationW(ctypes.byref(fileop))
        return result == 0 and not fileop.fAnyOperationsAborted
    except Exception as e:
        print(f"Error in send_to_recycle_bin: {e}")
        return False


def get_embedded_video_offset(file_path):
    """
    Checks if a JPG/JPEG file has an appended/embedded MP4 video.
    Returns the offset of the video file start if found, otherwise None.
    """
    if not file_path.lower().endswith(('.jpg', '.jpeg')):
        return None
    try:
        if not os.path.exists(file_path):
            return None
        with open(file_path, 'rb') as f:
            data = f.read()
        
        idx = data.find(b'ftyp')
        if idx != -1:
            box_start = idx - 4
            if box_start >= 0:
                box_size = int.from_bytes(data[box_start:idx], 'big')
                if 8 <= box_size <= 1024:
                    return box_start
    except Exception as e:
        print(f"Error checking embedded video: {e}")
    return None



