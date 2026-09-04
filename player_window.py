import os
import sys
import warnings

from PyQt6.QtCore import Qt, QTimer, QElapsedTimer
from PyQt6.QtGui import QIcon, QColor, QPalette
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

# Silence qfluentwidgets during import
import contextlib
import io

with contextlib.redirect_stdout(io.StringIO()):
    import qfluentwidgets
    from qfluentwidgets import FluentWindow
    
    qfluentwidgets.HELP_MESSAGE = False

from PyQt6.QtCore import qInstallMessageHandler
from utils import get_resource_path, qt_message_handler, load_markers, VERSION
from translations import set_lang
from mixins.cache_mixin import CacheMixin
from mixins.playback_mixin import PlaybackMixin
from mixins.loader_mixin import LoaderMixin
from mixins.transform_mixin import TransformMixin
from mixins.volume_mixin import VolumeMixin
from mixins.marker_mixin import MarkerMixin
from mixins.export_frame_mixin import ExportFrameMixin
from mixins.export_segment_mixin import ExportSegmentMixin
from mixins.playlist_mixin import PlaylistMixin
from mixins.drawing_mixin import DrawingMixin
from mixins.settings_mixin import SettingsMixin
from mixins.global_settings_mixin import GlobalSettingsMixin
from mixins.ipc_sync_mixin import IPCSyncMixin
from mixins.ui_mixin import UIMixin
from mixins.subtitle_mixin import SubtitleMixin
from mixins.audio_mixin import AudioMixin
from mixins.adjustment_mixin import AdjustmentMixin
from mixins.image_adj_settings_mixin import ImageAdjSettingsMixin

qInstallMessageHandler(qt_message_handler)


class PlayerWindow(
    AudioMixin,
    CacheMixin, PlaybackMixin, LoaderMixin, TransformMixin, VolumeMixin,
    MarkerMixin, ExportFrameMixin, ExportSegmentMixin, PlaylistMixin, DrawingMixin,
    SettingsMixin, GlobalSettingsMixin, IPCSyncMixin, UIMixin,
    SubtitleMixin, AdjustmentMixin, ImageAdjSettingsMixin,
    FluentWindow
):
    """
    Main application window inheriting 18 mixins.
    
    WARNING: cooperative multiple inheritance is used here. Lifecycle methods like closeEvent
    and load_video depend on Method Resolution Order (MRO) chaining (e.g. calling super().closeEvent(event)
    or super().load_video(filePath)). Altering the order of mixins or introducing new ones
    might break the chaining and lifecycle hooks if not carefully managed.
    """
    def __init__(self):
        # Load config & language
        from config import Configuration
        self.config = Configuration()
        set_lang(self.config.get('language', 'en'))
        
        # Asynchronously detect best hardware decoder at startup
        from utils import detect_best_hwaccel_async
        detect_best_hwaccel_async(self.config)

        # Attributes that must exist before super().__init__() (triggers resize)
        self.videoItem = None
        self.view = None

        from qfluentwidgets import setTheme, Theme, setThemeColor
        setTheme(Theme.LIGHT if self.config.get('inverse_text', False) else Theme.DARK)
        
        self.accent_color = self.config.get('accent_color', '#00f2ff')
        from PyQt6.QtGui import QColor
        setThemeColor(QColor(self.accent_color))

        super().__init__()
        self.BORDER_WIDTH = 8  # Wider resize grip (default 5 is too narrow, especially on HiDPI)
        self.setWindowIcon(QIcon(get_resource_path("resources/app_icon.ico")))
        self.setWindowTitle(f"Boomerang Player v{VERSION}")
        self.titleBar.setFixedHeight(32)
        
        # Target the top-level window directly to avoid cascading
        bg_col = self.config.get('bg_color', '#202020')
        self.setStyleSheet(f"PlayerWindow {{ background-color: {bg_col}; }}")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(True)
        from PyQt6.QtGui import QPalette
        win_pal = self.palette()
        win_pal.setColor(QPalette.ColorRole.Window, QColor(bg_col))
        self.setPalette(win_pal)
        
        self.widgetLayout.setContentsMargins(0, 32, 0, 0)

        # Add a left margin to the logo by inserting spacing at the beginning of the layout (prevents squeezing)
        self.titleBar.hBoxLayout.insertSpacing(0, 12)

        # Remove titleLabel from the layout so we can position it manually and center it perfectly relative to the window width
        if hasattr(self.titleBar, 'titleLabel') and self.titleBar.titleLabel:
            self.titleBar.hBoxLayout.removeWidget(self.titleBar.titleLabel)

        # ---- Application state ----------------------------------------
        self.active_skins_dialog = None
        self.currentFilePath = None
        self.currentVideoPath = None

        self.playlistData = load_markers()
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
        self.is_loading_video = False
        self.isSyncLocked = False

        # ---- Media player ---------------------------------------------
        self.mediaPlayer = QMediaPlayer()
        self.mediaPlayer.setPitchCompensation(True)
        self.audioOutput = QAudioOutput()
        self.mediaPlayer.setAudioOutput(self.audioOutput)

        # ---- System volume --------------------------------------------
        from utils import get_system_volume_control
        self.volume_ctrl = get_system_volume_control()

        # ---- Cache / playback variables --------------------------------
        self.cached_frame_dict = {}
        self.current_temp_dir = None
        self.extraction_thread = None
        self.cached_file_path = None
        self.current_cache_index = 0
        self.last_extracted_center = -1
        self.cache_window_half = self.config.get('cache_window', 900)
        self.is_zoomed_loop = False
        self.is_zoomed_window = False
        self.zoom_window_anchor = 0
        self.total_frames = 0
        self.is_playing = False
        self.is_scrubbing = False
        self.was_playing_before_cache_miss = False

        # ---- Shortcuts ------------------------------------------------
        self.shortcuts = self.config.get('shortcuts', {})
        if 'act_full_screen' not in self.shortcuts:
            self.shortcuts['act_full_screen'] = int(Qt.Key.Key_F)

        # ---- Build UI (UIMixin) ----------------------------------------
        self.init_ui()
        if hasattr(self, 'view') and self.view:
            self.view.strokesChanged.connect(self.save_drawings_to_markers)
        self.init_subtitle_state()
        self.init_audio_state()
        if hasattr(self, 'refresh_custom_styles'):
            self.refresh_custom_styles()
        
        # Load palette color
        palette = self.config.get('palette', ['#000000', '#FFFFFF', '#FF0000', '#FFFF00', '#00FF00', '#0000FF'])
        active_idx = self.config.get('active_color_index', 2)
        if 0 <= active_idx < len(palette):
            self.view.pen_color = QColor(palette[active_idx])
        
        # Update preview
        self.update_pen_preview()

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

        # ---- UDP Multi-Instance Sync ----------------------------------
        self.init_ipc_sync()

        # ---- Window geometry based on screen dimensions ----------------
        self.init_window_geometry()

    def init_window_geometry(self):
        """Set initial window size and position based on screen dimensions (one tier smaller than screen)."""
        from PyQt6.QtGui import QCursor
        from PyQt6.QtWidgets import QApplication

        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if not screen:
            self.resize(1440, 810)
            return

        avail = screen.availableGeometry()
        sw = avail.width()
        sh = avail.height()

        # Resolution tiers (one category smaller than current screen resolution):
        # 4K UHD (>= 3840) -> 2560 x 1440
        # QHD 2K (>= 2560) -> 1920 x 1080
        # Full HD (>= 1920) -> 1440 x 810 (e.g. 1920 -> 1440)
        # HD+ (>= 1600) -> 1280 x 720
        # HD (>= 1280) -> 1024 x 576
        # Smaller (< 1280) -> 960 x 540
        if sw >= 3840:
            w, h = 2560, 1440
        elif sw >= 2560:
            w, h = 1920, 1080
        elif sw >= 1920:
            w, h = 1440, 810
        elif sw >= 1600:
            w, h = 1280, 720
        elif sw >= 1280:
            w, h = 1024, 576
        else:
            w, h = 960, 540

        # Safety clamp to ensure window fits inside available screen work area with margin
        max_w = int(sw * 0.9)
        max_h = int(sh * 0.9)
        if w > max_w or h > max_h:
            scale = min(max_w / w, max_h / h)
            w = int(w * scale)
            h = int(h * scale)

        self.resize(w, h)

        # Center window in the available workspace of the active monitor
        x = avail.x() + (avail.width() - w) // 2
        y = avail.y() + (avail.height() - h) // 2
        self.move(x, y)



    def refresh_window_frame(self):
        hwnd = int(self.winId())
        if not hwnd:
            return
        import sys
        if sys.platform == 'win32' and not self.isMaximized():
            try:
                from qfluentwidgets import isDarkTheme
                if hasattr(self, 'windowEffect'):
                    if getattr(self, 'isMicaEffectEnabled', lambda: False)():
                        self.windowEffect.setMicaEffect(hwnd, isDarkTheme())
                    else:
                        self.windowEffect.addShadowEffect(hwnd)
                import win32gui
                import win32con
                win32gui.SetWindowPos(
                    hwnd, None, 0, 0, 0, 0,
                    win32con.SWP_NOMOVE | win32con.SWP_NOSIZE |
                    win32con.SWP_NOACTIVATE | win32con.SWP_FRAMECHANGED
                )
            except Exception:
                pass
        title = getattr(self, '_original_window_title', self.windowTitle())
        self.customSetTitle(title)

    def setWindowTitle(self, title):
        super().setWindowTitle(title)
        self.customSetTitle(title)

    def customSetTitle(self, title):
        self._original_window_title = title
        if hasattr(self, 'titleBar') and hasattr(self.titleBar, 'titleLabel') and self.titleBar.titleLabel:
            from PyQt6.QtGui import QFontMetrics
            from PyQt6.QtCore import Qt
            
            title_lbl = self.titleBar.titleLabel
            max_w = max(100, self.width() - 320)
            metrics = QFontMetrics(title_lbl.font())
            elided = metrics.elidedText(title, Qt.TextElideMode.ElideRight, max_w)
            title_lbl.setText(elided)
            title_lbl.adjustSize()
            
            margins = self.titleBar.hBoxLayout.contentsMargins()
            content_h = self.titleBar.height() - margins.top() - margins.bottom()
            x = (self.titleBar.width() - title_lbl.width()) // 2
            y = margins.top() + (content_h - title_lbl.height()) // 2
            title_lbl.move(x, y)
            self.titleBar.update()



    def event(self, event):
        from PyQt6.QtCore import QEvent
        if event.type() in (QEvent.Type.WindowActivate, QEvent.Type.ActivationChange, QEvent.Type.FocusIn):
            self.refresh_window_frame()
        return super().event(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Fix the title bar position and size when navigationInterface is hidden
        if hasattr(self, 'titleBar') and not getattr(self, 'is_full_screen', False):
            if not self.isMaximized():
                self.titleBar.move(0, 0)
                self.titleBar.resize(self.width(), self.titleBar.height())
            
            # Manually center titleLabel strictly relative to the window width, applying elide to prevent overlaps
            if hasattr(self.titleBar, 'titleLabel') and self.titleBar.titleLabel:
                full_text = getattr(self, '_original_window_title', self.windowTitle())
                self.customSetTitle(full_text)

        if getattr(self, 'is_full_screen', False):
            # Reposition title bar overlay in fullscreen
            if hasattr(self, 'titleBar') and self.titleBar.isVisible():
                self.titleBar.move(0, 0)
                self.titleBar.resize(self.width(), self.titleBar.height())
            # Reposition controls card overlay in fullscreen
            if hasattr(self, 'controlsCard') and self.controlsCard.parent() == self:
                h = max(80, self.controlsCard.sizeHint().height())
                self.controlsCard.setGeometry(0, self.height() - h, self.width(), h)
        else:
            # In windowed mode, ensure controlsCard is inside playerLayout if it was reparented to self
            if hasattr(self, 'controlsCard') and self.controlsCard.parent() == self:
                if hasattr(self, 'playerLayout') and hasattr(self, 'playerInterface'):
                    self.controlsCard.setParent(self.playerInterface)
                    self.playerLayout.addWidget(self.controlsCard, stretch=0)
                    self.controlsCard.show()

        if hasattr(self, 'update_sidebar_fullscreen_state'):
            self.update_sidebar_fullscreen_state()
        if hasattr(self, 'update_sidebar_margins'):
            self.update_sidebar_margins()
        if hasattr(self, 'position_subtitle_label'):
            self.position_subtitle_label()
        if hasattr(self, 'playerInterface'):
            self.playerInterface.update()
        self.update()

