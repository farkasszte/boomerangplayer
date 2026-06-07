"""
UIMixin — top-level init_ui orchestrator, playlist sidebar, drawing sidebar,
          controls bar, keyboard events.
"""

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFrame,
                              QSplitter, QLabel, QGridLayout,
                              QGraphicsScene, QGraphicsView,
                              QAbstractItemView)
from qfluentwidgets import (FluentIcon, ToolButton, CaptionLabel,
                             SwitchButton, PushButton)
from components import DropListWidget, MarkerSlider, ZoomView, GPUPixmapItem
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from styles import (FLUENT_SLIDER_STYLE, COMPACT_BTN_STYLE, MENU_STYLE,
                    ACTION_BTN_STYLE, TOOL_BTN_STYLE)
from translations import tr
from PyQt6.QtWidgets import QMenu, QButtonGroup, QSlider
from PyQt6.QtMultimedia import QMediaDevices
import qfluentwidgets
import ctypes

# Import sub-mixins
from mixins.ui.playlist_sidebar_ui import PlaylistSidebarUIMixin
from mixins.ui.drawing_sidebar_ui import DrawingSidebarUIMixin
from mixins.ui.controls_card_ui import ControlsCardUIMixin
from mixins.ui.style_mixin import StyleUIMixin
from mixins.ui.shortcut_mixin import ShortcutUIMixin
from mixins.ui.fullscreen_mixin import FullscreenUIMixin

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QMainWindow, QStackedWidget, QHBoxLayout
    from qfluentwidgets import NavigationInterface
    from PyQt6.QtMultimedia import QAudioOutput
    from config import Configuration
    UIMixinBase = QMainWindow
else:
    UIMixinBase = object

# pyrefly: ignore [inconsistent-inheritance]
class UIMixin(
    PlaylistSidebarUIMixin,
    DrawingSidebarUIMixin,
    ControlsCardUIMixin,
    StyleUIMixin,
    ShortcutUIMixin,
    FullscreenUIMixin,
    UIMixinBase
):
    if TYPE_CHECKING:
        stackedWidget: QStackedWidget
        navigationInterface: NavigationInterface
        hBoxLayout: QHBoxLayout
        config: Configuration
        audioOutput: QAudioOutput
        pixmapItem: GPUPixmapItem | None
        # pyrefly: ignore [not-a-type]
        update_ui_texts: callable

    def init_ui(self):
        # Main interface widget
        self.playerInterface = QWidget()
        self.playerLayout = QVBoxLayout(self.playerInterface)
        self.playerLayout.setContentsMargins(0, 0, 0, 0)
        self.playerLayout.setSpacing(0)

        self.mainSplitter = QSplitter(Qt.Orientation.Horizontal)
        self.mainSplitter.setHandleWidth(1)
        self.mainSplitter.setStyleSheet("QSplitter::handle { background: transparent; }")

        self.scene = QGraphicsScene()
        self.view = ZoomView(self.scene, self.playerInterface)
        # pyrefly: ignore [missing-attribute]
        self.view.filesDropped.connect(self.handle_view_drop)
        # pyrefly: ignore [missing-attribute]
        self.view.zoomChanged.connect(self.on_user_zoom_changed)
        self.view.setStyleSheet("border: none; background: black;")

        # Build all sidebars (mixin methods)
        # pyrefly: ignore [missing-attribute]
        self.init_global_settings_sidebar()
        # pyrefly: ignore [missing-attribute]
        self.init_video_settings_sidebar()
        self._init_playlist_sidebar()
        self._init_drawing_sidebar()

        # pyrefly: ignore [missing-attribute]
        self.mainSplitter.addWidget(self.globalSettingsContainer)
        # pyrefly: ignore [missing-attribute]
        self.mainSplitter.addWidget(self.settingsContainer)
        self.mainSplitter.addWidget(self.view)
        self.mainSplitter.addWidget(self.playlistContainer)
        self.mainSplitter.addWidget(self.drawingContainer)
        self.mainSplitter.setStretchFactor(2, 1)
        self.mainSplitter.setSizes([0, 0, 10000, 250, 0])

        self.playerLayout.addWidget(self.mainSplitter, stretch=1)

        # Pen preview (needs to happen after drawing sidebar is built)
        # pyrefly: ignore [missing-attribute]
        self.update_pen_preview()

        self.pixmapItem = GPUPixmapItem()
        self.update_gpu_state()
        self.scene.addItem(self.pixmapItem)

        # Loading overlay
        from styles import get_styles
        default_styles = get_styles(self.config.get('accent_color', '#00f2ff'), self.config.get('bg_color', '#202020'))

        self.loadingOverlay = QLabel(tr('caching'), self.view)
        self.loadingOverlay.setStyleSheet(default_styles['LOADING_OVERLAY_STYLE'])
        self.loadingOverlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loadingOverlay.hide()

        # Dynamic show/setText overrides to keep overlay geometry and font synchronized with the video frame bounds
        orig_show = self.loadingOverlay.show
        orig_setText = self.loadingOverlay.setText
        
        def custom_show():
            orig_show()
            if hasattr(self, 'update_loading_overlay_geometry'):
                self.update_loading_overlay_geometry()
                
        def custom_setText(text):
            orig_setText(text)
            if hasattr(self, 'update_loading_overlay_geometry'):
                self.update_loading_overlay_geometry()
                
        self.loadingOverlay.show = custom_show
        # pyrefly: ignore [bad-assignment]
        self.loadingOverlay.setText = custom_setText

        # Chronometer Overlay
        self.chronometerOverlay = QFrame(self.view)
        self.chronometerOverlay.setStyleSheet(default_styles['CHRONO_OVERLAY_STYLE'])
        self.chronometerOverlayLayout = QVBoxLayout(self.chronometerOverlay)
        self.chronometerOverlayLayout.setContentsMargins(12, 10, 12, 10)
        self.chronometerOverlayLayout.setSpacing(4)
        
        self.chronoTimeLabel = QLabel("00:00.000")
        accent = self.config.get('accent_color', '#00f2ff')
        self.chronoTimeLabel.setStyleSheet(f"font-size: 24px; font-weight: bold; font-family: 'Segoe UI Semibold', 'Courier New'; color: {accent};")
        self.chronoSectionLabel = QLabel("")
        self.chronoSectionLabel.setStyleSheet("font-size: 12px; color: #ffffff; line-height: 140%;")
        self.chronoPositionLabel = QLabel("")
        self.chronoPositionLabel.setStyleSheet("font-size: 12px; color: #ffffff; line-height: 140%;")
        
        self.chronometerOverlayLayout.addWidget(self.chronoTimeLabel)
        self.chronometerOverlayLayout.addWidget(self.chronoSectionLabel)
        self.chronometerOverlayLayout.addWidget(self.chronoPositionLabel)
        
        self.chronometerOverlay.adjustSize()
        self.chronometerOverlay.move(20, 20)
        self.chronometerOverlay.hide()

        # Premium drag feature
        def overlayMousePressEvent(event):
            if event.button() == Qt.MouseButton.LeftButton:
                # pyrefly: ignore [missing-attribute]
                self.chronometerOverlay._drag_start_pos = event.globalPosition().toPoint() - self.chronometerOverlay.pos()
                event.accept()
                
        def overlayMouseMoveEvent(event):
            if event.buttons() & Qt.MouseButton.LeftButton and hasattr(self.chronometerOverlay, '_drag_start_pos'):
                new_pos = event.globalPosition().toPoint() - self.chronometerOverlay._drag_start_pos
                vx = max(10, min(self.view.width() - self.chronometerOverlay.width() - 10, new_pos.x()))
                vy = max(10, min(self.view.height() - self.chronometerOverlay.height() - 10, new_pos.y()))
                self.chronometerOverlay.move(vx, vy)
                event.accept()

        # pyrefly: ignore [bad-assignment]
        self.chronometerOverlay.mousePressEvent = overlayMousePressEvent
        # pyrefly: ignore [bad-assignment]
        self.chronometerOverlay.mouseMoveEvent = overlayMouseMoveEvent

        # Controls card
        self._init_controls_card()

        self.playerLayout.addWidget(self.controlsCard, stretch=0)
        self.playerLayout.setContentsMargins(0, 0, 0, 0)

        # Register with FluentWindow
        self.playerInterface.setObjectName("playerInterface")
        self.stackedWidget.addWidget(self.playerInterface)
        self.stackedWidget.setCurrentWidget(self.playerInterface)
        self.navigationInterface.hide()
        self.navigationInterface.setFixedWidth(0)
        self.stackedWidget.setContentsMargins(0, 0, 0, 0)
        self.hBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.hBoxLayout.setSpacing(0)
        self.playerLayout.setContentsMargins(0, 0, 0, 0)
        self.playerLayout.setSpacing(0)

        # Startup audio device
        device_id = self.config.get('audio_device', '')
        if device_id:
            for device in QMediaDevices.audioOutputs():
                d_id = (device.id().data().decode()
                        if hasattr(device.id(), 'data') else str(device.id()))
                if d_id == device_id:
                    self.audioOutput.setDevice(device)
                    break

        self.refresh_custom_styles()
        self.update_ui_texts()
        self.is_full_screen = False
        self.sidebar_states_before_fs = {}
        self.setup_shortcuts()

    def update_gpu_state(self):
        if hasattr(self, 'view') and self.pixmapItem is not None:
            enabled = self.config.get('gpu_acceleration', False)
            
            # Switch viewport dynamically
            if enabled:
                if not isinstance(self.view.viewport(), QOpenGLWidget):
                    gl_v = QOpenGLWidget()
                    gl_v.setAutoFillBackground(True)
                    # Force full viewport update to prevent "ghosting" / leaving previous frames
                    self.view.setViewport(gl_v)
                    self.scene.setBackgroundBrush(Qt.GlobalColor.black)
                    self.view.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
            else:
                if isinstance(self.view.viewport(), QOpenGLWidget):
                    from PyQt6.QtWidgets import QWidget
                    self.view.setViewport(QWidget())
                    self.view.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.MinimalViewportUpdate)
            
            self.pixmapItem.gpu_enabled = enabled
            self.pixmapItem.update()

    def update_sidebar_margins(self):
        if not hasattr(self, 'globalSettingsLayout') or not hasattr(self, 'settingsLayout') \
           or not hasattr(self, 'drawingSidebarLayout') or not hasattr(self, 'playlistLayout'):
            return

        bottom_margin = 10
            
        if hasattr(self, 'globalSettingsLayout'):
            self.globalSettingsLayout.setContentsMargins(10, 10, 4, bottom_margin)
        if hasattr(self, 'settingsLayout'):
            self.settingsLayout.setContentsMargins(10, 10, 4, bottom_margin)
        if hasattr(self, 'drawingSidebarLayout'):
            self.drawingSidebarLayout.setContentsMargins(10, 10, 4, bottom_margin)
        if hasattr(self, 'playlistLayout'):
            self.playlistLayout.setContentsMargins(10, 10, 4, bottom_margin)

    def update_sidebar_fullscreen_state(self):
        if not hasattr(self, 'globalSettingsContainer') or not hasattr(self, 'settingsContainer') \
           or not hasattr(self, 'playlistContainer') or not hasattr(self, 'drawingContainer') \
           or not hasattr(self, 'mainSplitter'):
            return

        is_fs = getattr(self, 'is_full_screen', False)
        
        sidebars = [
            ('global_settings', self.globalSettingsContainer, 'left', 0),
            ('settings', self.settingsContainer, 'left', 1),
            ('playlist', self.playlistContainer, 'right', 3),
            ('drawing', self.drawingContainer, 'right', 4)
        ]
        
        if is_fs:
            h = self.controlsCard.height() if (hasattr(self, 'controlsCard') and self.controlsCard.isVisible()) else 0
            sidebar_height = self.height() - h if h > 0 else self.height()
            
            for name, container, side, original_idx in sidebars:
                was_visible = container.isVisible()
                if container.parent() != self:
                    container.setParent(self)
                # Keep original visibility state
                container.setVisible(was_visible)
                
                if was_visible:
                    container.raise_()
                    width = 250
                    x = 0 if side == 'left' else (self.width() - width)
                    container.setGeometry(x, 0, width, sidebar_height)
            
            # Always raise the bottom controls card above the sidebars in fullscreen so its buttons are fully clickable
            if hasattr(self, 'controlsCard') and self.controlsCard.isVisible():
                self.controlsCard.raise_()
        else:
            # Restore to mainSplitter in original index order
            for name, container, side, original_idx in sidebars:
                was_visible = container.isVisible()
                if container.parent() != self.mainSplitter:
                    self.mainSplitter.insertWidget(original_idx, container)
                container.setVisible(was_visible)
            
            # Enforce mutual exclusivity on the same side in windowed mode
            if self.globalSettingsContainer.isVisible() and self.settingsContainer.isVisible():
                self.globalSettingsContainer.hide()
            if self.playlistContainer.isVisible() and self.drawingContainer.isVisible():
                self.drawingContainer.hide()
            
            # Restore windowed sizes dynamically based on actual visibility of the sidebars
            sizes = [
                250 if self.globalSettingsContainer.isVisible() else 0,
                250 if self.settingsContainer.isVisible() else 0,
                10000,
                250 if self.playlistContainer.isVisible() else 0,
                250 if self.drawingContainer.isVisible() else 0
            ]
            self.mainSplitter.setSizes(sizes)
