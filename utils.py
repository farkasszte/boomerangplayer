import os
import sys
import json
import subprocess
from PyQt6.QtCore import Qt
VERSION = "3.1"

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

def get_ffmpeg_path():
    path = get_resource_path("ffmpeg.exe" if os.name == 'nt' else "ffmpeg")
    if os.path.exists(path):
        return os.path.normpath(path)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_dir, "ffmpeg.exe" if os.name == 'nt' else "ffmpeg")
    if os.path.exists(path):
        return os.path.normpath(path)
    return "ffmpeg"

def get_ffprobe_path():
    path = get_resource_path("ffprobe.exe" if os.name == 'nt' else "ffprobe")
    if os.path.exists(path):
        return os.path.normpath(path)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_dir, "ffprobe.exe" if os.name == 'nt' else "ffprobe")
    if os.path.exists(path):
        return os.path.normpath(path)
    return "ffprobe"

def detect_best_hwaccel_async(config):
    """
    Detects the best hardware decoding method supported by the system ffmpeg
    by generating a tiny video in the temp folder and trying to decode it.
    """
    import threading
    import tempfile
    import subprocess
    
    def worker():
        try:
            ffmpeg_path = get_ffmpeg_path()
            dummy_file = os.path.join(tempfile.gettempdir(), "boomerang_dummy.mp4")
            
            if os.path.exists(dummy_file):
                try:
                    os.remove(dummy_file)
                except OSError:
                    pass
            
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            gen_cmd = [
                ffmpeg_path, "-y", "-f", "lavfi", "-i", "testsrc=size=64x64:rate=1",
                "-t", "1", "-pix_fmt", "yuv420p", dummy_file
            ]
            
            res = subprocess.run(gen_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creationflags, timeout=5)
            if res.returncode != 0 or not os.path.exists(dummy_file):
                print("[GPU Detect] Failed to generate dummy video for testing.")
                return
            
            hwaccels_to_test = ['cuda', 'd3d11va', 'dxva2']
            best_accel = 'auto'
            
            for accel in hwaccels_to_test:
                test_cmd = [
                    ffmpeg_path, "-y", "-hwaccel", accel, "-i", dummy_file, "-f", "null", "-"
                ]
                try:
                    res_test = subprocess.run(test_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creationflags, timeout=3)
                    if res_test.returncode == 0:
                        best_accel = accel
                        print(f"[GPU Detect] Hardware acceleration '{accel}' is verified and working.")
                        break
                except Exception:
                    continue
            
            try:
                os.remove(dummy_file)
            except OSError:
                pass
            
            config['detected_hwaccel'] = best_accel
            try:
                from utils import save_config
                save_config(config)
            except Exception:
                pass
                
        except Exception as e:
            print(f"[GPU Detect] Error during detection: {e}")
            
    threading.Thread(target=worker, daemon=True).start()

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
        'act_full_screen': Qt.Key.Key_F,
        'sub_delay_minus': Qt.Key.Key_BracketLeft,
        'sub_delay_plus': Qt.Key.Key_BracketRight
    },
    'palette': ['#000000', '#FFFFFF', '#FF0000', '#FFFF00', '#00FF00', '#0000FF'],
    'active_color_index': 2, # Default to Red
    'audio_eq_enabled': False,
    'audio_eq_preset': 'Flat',
    'audio_eq_gains': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    'subtitle_outline_enabled': False,
    'subtitle_outline_width': 2,
    'subtitle_outline_color': 'Black',
    'subtitle_shadow_enabled': False,
    'subtitle_shadow_blur': 5,
    'subtitle_shadow_dx': 2,
    'subtitle_shadow_dy': 2,
    'subtitle_shadow_color': 'Black',
    'subtitle_v_offset': 5,
    'subtitle_h_offset': 0,
    'detected_hwaccel': 'auto'
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


def cleanup_old_mem_cache():
    """ Scans the system temporary directory for any stale mem_cache_ directories
    left over from previous sessions (now unlocked) and deletes them.
    Runs asynchronously in a background daemon thread.
    """
    import threading
    import tempfile
    import shutil
    
    def worker():
        try:
            temp_dir = tempfile.gettempdir()
            if not os.path.exists(temp_dir) or not os.path.isdir(temp_dir):
                return
            
            cleaned_count = 0
            for item in os.listdir(temp_dir):
                if item.startswith("mem_cache_"):
                    item_path = os.path.join(temp_dir, item)
                    if os.path.isdir(item_path):
                        try:
                            shutil.rmtree(item_path, ignore_errors=True)
                            cleaned_count += 1
                        except Exception:
                            pass
            if cleaned_count > 0:
                print(f"[MemCache GC] Cleaned up {cleaned_count} stale cache directories from previous sessions.")
        except Exception as e:
            print(f"[MemCache GC] Error cleaning up stale cache directories: {e}")
            
    threading.Thread(target=worker, daemon=True).start()


def log_debug(msg):
    # Debug logging to file is muted for production/release.
    # Uncomment print below if console debug logs are needed:
    # print(f"[DEBUG] {msg}", flush=True)
    pass

def send_to_recycle_bin(path):
    """ Moves the specified file to the Windows Recycle Bin (Lomtár) using ctypes SHFileOperationW.
    Returns True if successful, False otherwise.
    """
    log_debug(f"send_to_recycle_bin called for path: {path}")
    if os.name != 'nt':
        try:
            if os.path.exists(path):
                os.remove(path)
                log_debug("Non-Windows deletion succeeded")
                return True
        except Exception as e:
            log_debug(f"Non-Windows deletion failed: {e}")
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

    import time
    for attempt in range(30):
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
            if result == 0 and not fileop.fAnyOperationsAborted:
                log_debug(f"ctypes SHFileOperationW succeeded on attempt {attempt}")
                return True
            else:
                log_debug(f"ctypes SHFileOperationW failed on attempt {attempt} with code {result} (aborted: {fileop.fAnyOperationsAborted})")
                print(f"[send_to_recycle_bin] (attempt {attempt}) SHFileOperationW returned code {result} (aborted: {fileop.fAnyOperationsAborted})")
                
                # Robust fallback: use PowerShell COM Shell.Application object to move the file to the Recycle Bin
                try:
                    ps_cmd = [
                        "powershell", "-NoProfile", "-Command",
                        f'(New-Object -ComObject Shell.Application).NameSpace(10).MoveHere("{abs_path}")'
                    ]
                    creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                    res = subprocess.run(ps_cmd, creationflags=creationflags, capture_output=True, text=True, timeout=5)
                    if not os.path.exists(abs_path):
                        log_debug(f"PowerShell fallback succeeded on attempt {attempt}")
                        print(f"[send_to_recycle_bin] PowerShell fallback succeeded on attempt {attempt}")
                        return True
                    else:
                        log_debug(f"PowerShell fallback run but file still exists. stdout: {res.stdout.strip()}, stderr: {res.stderr.strip()}")
                except Exception as ex:
                    log_debug(f"PowerShell fallback failed: {ex}")
                    print(f"[send_to_recycle_bin] PowerShell fallback failed: {ex}")
        except Exception as e:
            log_debug(f"Error in send_to_recycle_bin try-except: {e}")
            print(f"Error in send_to_recycle_bin (attempt {attempt}): {e}")
        time.sleep(0.1)
    log_debug("All 30 attempts to delete failed")
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


import re

def clean_subtitle_text(text):
    """
    Cleans subtitle text by removing HTML-like tags (<...>) and curly-brace style tags ({...}).
    """
    # Remove HTML-like tags
    text = re.sub(r'<[^>]+>', '', text)
    # Remove curly-brace styles (MicroDVD, ASS styles, etc.)
    text = re.sub(r'\{[^}]*\}', '', text)
    return text.strip()

def parse_subtitle_file(filepath, fps=30.0):
    """
    Parses SRT, VTT, SUB, or ASS/SSA files.
    Returns a list of dicts: [{'start': ms, 'end': ms, 'text': '...'}]
    """
    if not os.path.exists(filepath):
        return []

    ext = os.path.splitext(filepath)[1].lower()
    
    content = ""
    for enc in ['utf-8', 'utf-8-sig', 'cp1250', 'iso-8859-2', 'latin-1']:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                content = f.read()
            break
        except Exception:
            continue
            
    if not content:
        return []

    if ext == '.srt':
        return parse_srt(content)
    elif ext == '.vtt':
        return parse_vtt(content)
    elif ext == '.sub':
        return parse_sub(content, fps)
    elif ext in ('.ssa', '.ass'):
        return parse_ass(content)
        
    return []

def time_to_ms(h, m, s, ms):
    return int(h) * 3600000 + int(m) * 60000 + int(s) * 1000 + int(ms)

def parse_srt(content):
    subtitles = []
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    pattern = re.compile(
        r'(?:\d+\n)?(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})\n([\s\S]*?)(?=\n\n|\n*$)'
    )
    for match in pattern.finditer(content):
        sh, sm, ss, sms, eh, em, es, ems, text = match.groups()
        start = time_to_ms(sh, sm, ss, sms)
        end = time_to_ms(eh, em, es, ems)
        text_clean = clean_subtitle_text(text)
        if text_clean:
            subtitles.append({'start': start, 'end': end, 'text': text_clean})
    return subtitles

def parse_vtt(content):
    subtitles = []
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    timestamp_pattern = re.compile(
        r'(\d{2}:\d{2}:\d{2}\.\d{3}|\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3}|\d{2}:\d{2}\.\d{3})\n([\s\S]*?)(?=\n\n|\n*$)'
    )
    
    def parse_vtt_timestamp(ts):
        parts = ts.split(':')
        if len(parts) == 3:
            h, m, s_ms = parts
            s, ms = s_ms.split('.')
            return time_to_ms(h, m, s, ms)
        elif len(parts) == 2:
            m, s_ms = parts
            s, ms = s_ms.split('.')
            return time_to_ms(0, m, s, ms)
        return 0

    for match in timestamp_pattern.finditer(content):
        start_ts, end_ts, text = match.groups()
        start = parse_vtt_timestamp(start_ts)
        end = parse_vtt_timestamp(end_ts)
        text_clean = clean_subtitle_text(text)
        if text_clean:
            subtitles.append({'start': start, 'end': end, 'text': text_clean})
    return subtitles

def parse_sub(content, fps=30.0):
    subtitles = []
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    pattern = re.compile(r'^\{(\d+)\}\{(\d+)\}(.*)$', re.MULTILINE)
    if fps <= 0:
        fps = 30.0
    for match in pattern.finditer(content):
        start_frame, end_frame, text = match.groups()
        start = int(int(start_frame) * 1000 / fps)
        end = int(int(end_frame) * 1000 / fps)
        text_clean = clean_subtitle_text(text.replace('|', '\n'))
        if text_clean:
            subtitles.append({'start': start, 'end': end, 'text': text_clean})
    return subtitles

def parse_ass(content):
    subtitles = []
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    lines = content.split('\n')
    dialogue_pattern = re.compile(r'^Dialogue:\s*[^,]*,([^,]*),([^,]*),([^,]*),([^,]*),([^,]*),([^,]*),([^,]*),([^,]*),([\s\S]*)$')
    
    def parse_ass_timestamp(ts):
        parts = ts.split(':')
        if len(parts) == 3:
            h, m, s_cs = parts
            s, cs = s_cs.split('.')
            return int(h) * 3600000 + int(m) * 60000 + int(s) * 1000 + int(cs) * 10
        return 0

    for line in lines:
        match = dialogue_pattern.match(line)
        if match:
            start_ts, end_ts, _, _, _, _, _, _, text = match.groups()
            start = parse_ass_timestamp(start_ts)
            end = parse_ass_timestamp(end_ts)
            clean_text = clean_subtitle_text(text.replace('\\N', '\n').replace('\\n', '\n'))
            if clean_text:
                subtitles.append({'start': start, 'end': end, 'text': clean_text})
    return subtitles


def get_embedded_subtitles_info(filepath):
    """
    Scans a file using ffprobe for subtitle streams.
    Returns a list of dicts: [{'index': int, 'codec': str, 'language': str, 'title': str}]
    """
    try:
        ffprobe_path = get_ffprobe_path()
        cmd = [
            ffprobe_path, "-v", "error",
            "-show_entries", "stream=index,codec_type,codec_name:stream_tags=language,title",
            "-of", "json", filepath
        ]

        creationflags = 0
        if os.name == 'nt':
            creationflags = subprocess.CREATE_NO_WINDOW

        result = subprocess.check_output(cmd, creationflags=creationflags).decode('utf-8', errors='ignore')
        data = json.loads(result)
        streams = data.get('streams', [])
        
        subtitle_streams = []
        for s in streams:
            if s.get('codec_type') == 'subtitle':
                tags = s.get('tags', {})
                lang = tags.get('language', 'und')
                title = tags.get('title', '')
                codec = s.get('codec_name', 'unknown')
                subtitle_streams.append({
                    'index': s.get('index'),
                    'codec': codec,
                    'language': lang,
                    'title': title
                })
        return subtitle_streams
    except Exception as e:
        print(f"Error querying embedded subtitles: {e}")
        return []

def extract_embedded_subtitle(filepath, stream_index):
    """
    Extracts subtitle stream from video to SRT format text using ffmpeg.
    """
    try:
        ffmpeg_path = get_ffmpeg_path()
        cmd = [
            ffmpeg_path, "-y", "-i", filepath,
            "-map", f"0:{stream_index}",
            "-f", "srt", "-"
        ]

        creationflags = 0
        if os.name == 'nt':
            creationflags = subprocess.CREATE_NO_WINDOW

        result = subprocess.check_output(cmd, creationflags=creationflags).decode('utf-8', errors='ignore')
        return result
    except Exception as e:
        print(f"Error extracting embedded subtitle stream {stream_index}: {e}")
        return ""





