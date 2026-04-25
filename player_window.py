import os
import sys
import warnings

# System volume control
try:
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from comtypes import CLSCTX_ALL
    HAS_PYCAW = True
except Exception:
    HAS_PYCAW = False

from PyQt6.QtCore import Qt, QTimer, QElapsedTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

# Silence qfluentwidgets during import
_temp_stdout = sys.stdout
sys.stdout = open(os.devnull, 'w')
try:
    import qfluentwidgets
    from qfluentwidgets import FluentWindow
    qfluentwidgets.HELP_MESSAGE = False
finally:
    sys.stdout.close()
    sys.stdout = _temp_stdout

from PyQt6.QtCore import qInstallMessageHandler
from utils import get_resource_path, qt_message_handler, load_config
from translations import set_lang
from mixins.cache_mixin import CacheMixin
from mixins.playback_mixin import PlaybackMixin
from mixins.transform_mixin import TransformMixin
from mixins.volume_mixin import VolumeMixin
from mixins.marker_mixin import MarkerMixin
from mixins.playlist_mixin import PlaylistMixin
from mixins.drawing_mixin import DrawingMixin
from mixins.settings_mixin import SettingsMixin
from mixins.global_settings_mixin import GlobalSettingsMixin
from mixins.ui_mixin import UIMixin

qInstallMessageHandler(qt_message_handler)


class PlayerWindow(
    CacheMixin, PlaybackMixin, TransformMixin, VolumeMixin,
    MarkerMixin, PlaylistMixin, DrawingMixin,
    SettingsMixin, GlobalSettingsMixin, UIMixin,
    FluentWindow
):
    def __init__(self):
        # Load config & language
        self.config = load_config()
        set_lang(self.config.get('language', 'en'))

        # Attributes that must exist before super().__init__() (triggers resize)
        self.videoItem = None
        self.view = None

        from qfluentwidgets import setTheme, Theme
        setTheme(Theme.DARK)

        super().__init__()
        self.setWindowIcon(QIcon(get_resource_path("app_icon.ico")))
        self.setWindowTitle("Boomerang Player")
        self.titleBar.setFixedHeight(32)
        self.setContentsMargins(0, 0, 0, 0)
        self.widgetLayout.setContentsMargins(0, 32, 0, 0)

        # Centre title in FluentTitleBar
        self.titleBar.hBoxLayout.insertStretch(1, 1)
        self.titleBar.hBoxLayout.insertStretch(3, 1)
        self.titleBar.titleLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # ---- Application state ----------------------------------------
        self.currentFilePath = None
        self.playlistData = self.config.get('markers_data', {})
        self.isPingPong = True
        self.isForward = True
        self.zoomLevel = 1.0
        self.markers = []
        self.active_loop_start = 0
        self.active_loop_end = 0
        self.needs_range_update = True
        self.fps = 30.0
        self.userMutedIntent = False
        self.isMirrored = False
        self.isMirroredVertical = False
        self.rotationAngle = 0
        self.last_transform_state = None

        # ---- Media player ---------------------------------------------
        self.mediaPlayer = QMediaPlayer()
        self.audioOutput = QAudioOutput()
        self.mediaPlayer.setAudioOutput(self.audioOutput)

        # ---- System volume --------------------------------------------
        self.volume_ctrl = None
        if HAS_PYCAW:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                try:
                    import comtypes
                    from comtypes import CLSCTX_ALL, GUID
                    try:
                        comtypes.CoInitialize()
                    except:
                        pass

                    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
                    IID_IAudioEndpointVolume = "{5CDF2C82-841E-4546-9722-0CF74078229A}"

                    def try_link_flexible(device_obj):
                        if not device_obj:
                            return None
                        potential_targets = [device_obj]
                        try:
                            for attr in dir(device_obj):
                                try:
                                    val = getattr(device_obj, attr)
                                    if hasattr(val, 'Activate'):
                                        potential_targets.append(val)
                                except:
                                    continue
                        except:
                            pass

                        for target in potential_targets:
                            try:
                                iid = getattr(IAudioEndpointVolume, '_iid_', IID_IAudioEndpointVolume)
                                try:
                                    interface = target.Activate(GUID(iid), CLSCTX_ALL, None)
                                    if interface:
                                        return interface.QueryInterface(IAudioEndpointVolume)
                                except:
                                    continue
                            except:
                                continue
                        return None

                    try:
                        test_dev = AudioUtilities.GetSpeakers()
                        self.volume_ctrl = try_link_flexible(test_dev)
                    except:
                        pass

                    if self.volume_ctrl is None:
                        try:
                            for d in AudioUtilities.GetAllDevices():
                                self.volume_ctrl = try_link_flexible(d)
                                if self.volume_ctrl:
                                    break
                        except:
                            pass
                except:
                    pass

        # ---- Cache / playback variables --------------------------------
        self.cached_frame_dict = {}
        self.current_temp_dir = None
        self.extraction_thread = None
        self.cached_file_path = None
        self.current_cache_index = 0
        self.last_extracted_center = -1
        self.cache_window_half = 600
        self.is_zoomed_nav = False
        self.total_frames = 0
        self.is_playing = False
        self.is_scrubbing = False
        self.was_playing_before_cache_miss = False

        # ---- Build UI (UIMixin) ----------------------------------------
        self.init_ui()

        # ---- Media player signal connections ---------------------------
        self.mediaPlayer.durationChanged.connect(self.update_duration)
        self.mediaPlayer.playbackStateChanged.connect(self.handle_state_change)
        self.mediaPlayer.mediaStatusChanged.connect(self.handle_status_change)
        self.mediaPlayer.metaDataChanged.connect(self.handle_metadata_change)

        # ---- Playback timer -------------------------------------------
        self.playbackTimer = QTimer()
        self.playbackTimer.setTimerType(Qt.TimerType.PreciseTimer)
        self.playbackTimer.timeout.connect(self.advance_frame)
        self.elapsedTimer = QElapsedTimer()
        self.last_advance_ms = 0

        # ---- Shortcuts ------------------------------------------------
        self.shortcuts = self.config.get('shortcuts', {})
