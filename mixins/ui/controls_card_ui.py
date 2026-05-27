from PyQt6.QtCore import Qt, QSize, QTimer, QEvent
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import CaptionLabel, ToolButton, FluentIcon
from components import MarkerSlider
from styles import FLUENT_SLIDER_STYLE, COMPACT_BTN_STYLE
from translations import tr

class ControlsCardUIMixin:
    def _init_controls_card(self):
        self.controlsCard = QFrame()
        self.controlsCard.setStyleSheet("background-color: #202020; border: none;")
        self.controlsLayout = QVBoxLayout(self.controlsCard)
        self.controlsLayout.setContentsMargins(12, 12, 12, 12)

        # Progress bar row
        progressLayout = QHBoxLayout()
        self.currentTimeLabel = CaptionLabel("00:00")
        self.frameLabel = CaptionLabel(" [F: 0]")
        self.progressBar = MarkerSlider(Qt.Orientation.Horizontal)
        self.progressBar.setStyleSheet(FLUENT_SLIDER_STYLE)
        self.progressBar.setRange(0, 0)
        self.progressBar.sliderMoved.connect(self.set_position)
        self.progressBar.sliderReleased.connect(self.on_slider_released)
        self.progressBar.sliderPressed.connect(self.on_slider_pressed)
        self.totalTimeLabel = CaptionLabel("00:00")

        initial_vol = 50
        if self.volume_ctrl:
            try:
                initial_vol = int(self.volume_ctrl.GetMasterVolumeLevelScalar() * 100)
                self.userMutedIntent = self.volume_ctrl.GetMute()
            except:
                pass
        self.audioOutput.setVolume(initial_vol / 100.0)

        progressLayout.addWidget(self.currentTimeLabel)
        progressLayout.addWidget(self.frameLabel)
        progressLayout.addWidget(self.progressBar)
        progressLayout.addWidget(self.totalTimeLabel)
        self.controlsLayout.addLayout(progressLayout)

        # Buttons row
        buttonsLayout = QHBoxLayout()

        self.toggleSettingsButton = ToolButton(FluentIcon.VIDEO)
        self.toggleSettingsButton.setToolTip(tr('video_settings'))
        self.toggleSettingsButton.clicked.connect(self.toggle_settings)
        buttonsLayout.addWidget(self.toggleSettingsButton)

        self.globalSettingsButton = ToolButton(FluentIcon.SETTING)
        self.globalSettingsButton.setToolTip(tr('tip_settings'))
        self.globalSettingsButton.clicked.connect(self.show_global_settings)
        buttonsLayout.addWidget(self.globalSettingsButton)

        buttonsLayout.addSpacing(20)
        buttonsLayout.addSpacing(10)
        buttonsLayout.addSpacing(10)

        # Playback buttons (center)
        playbackButtonsLayout = QHBoxLayout()
        playbackButtonsLayout.setSpacing(0)

        self.stepBackButton = ToolButton(FluentIcon.LEFT_ARROW)
        self.stepBackButton.setToolTip(tr('tip_prev_frame'))
        self.stepBackButton.clicked.connect(lambda: self.step_frame(-1))
        self.stepBackButton.setFixedSize(32, 32)
        self.stepBackButton.setStyleSheet(
            COMPACT_BTN_STYLE + "ToolButton { border-top-left-radius: 4px; border-bottom-left-radius: 4px; }"
        )

        # Create flipped Play icon for backward button
        play_pixmap = FluentIcon.PLAY.icon().pixmap(QSize(24, 24))
        flipped_play_pixmap = QPixmap.fromImage(play_pixmap.toImage().mirrored(True, False))
        self.flippedPlayIcon = QIcon(flipped_play_pixmap)
        self.normalPlayIcon = FluentIcon.PLAY.icon()
        self.pauseIcon = FluentIcon.PAUSE.icon()

        self.playBackwardButton = ToolButton(self.flippedPlayIcon)
        self.playBackwardButton.setToolTip(tr('tip_play_backward'))
        self.playBackwardButton.setIconSize(QSize(24, 24))
        self.playBackwardButton.setFixedSize(32, 32)
        self.playBackwardButton.setStyleSheet(
            COMPACT_BTN_STYLE + "ToolButton { border-radius: 0px; border-right: none; }"
        )
        self.playBackwardButton.clicked.connect(self.play_pause_backward)

        self.playButton = ToolButton(FluentIcon.PLAY)
        self.playButton.setToolTip(tr('tip_play_pause'))
        self.playButton.setIconSize(QSize(24, 24))
        self.playButton.setFixedSize(32, 32)
        self.playButton.setStyleSheet(
            COMPACT_BTN_STYLE + "ToolButton { border-radius: 0px; border-right: none; }"
        )
        self.playButton.clicked.connect(self.play_pause)

        self.stepForwardButton = ToolButton(FluentIcon.RIGHT_ARROW)
        self.stepForwardButton.setToolTip(tr('tip_next_frame'))
        self.stepForwardButton.clicked.connect(lambda: self.step_frame(1))
        self.stepForwardButton.setFixedSize(32, 32)
        self.stepForwardButton.setStyleSheet(
            COMPACT_BTN_STYLE
            + "ToolButton { border-right: 1px solid rgba(255,255,255,0.08); "
              "border-top-right-radius: 4px; border-bottom-right-radius: 4px; }"
        )

        playbackButtonsLayout.addWidget(self.stepBackButton)
        playbackButtonsLayout.addWidget(self.playBackwardButton)
        playbackButtonsLayout.addWidget(self.playButton)
        playbackButtonsLayout.addWidget(self.stepForwardButton)

        buttonsLayout.addStretch(1)
        buttonsLayout.addLayout(playbackButtonsLayout)
        buttonsLayout.addStretch(1)

        self.fullScreenButton = ToolButton(FluentIcon.FULL_SCREEN)
        self.fullScreenButton.setToolTip(tr('tip_full_screen'))
        self.fullScreenButton.clicked.connect(self.toggle_full_screen)
        buttonsLayout.addWidget(self.fullScreenButton)

        # Volume
        volumeContainer = QWidget()
        volumeContainerLayout = QHBoxLayout(volumeContainer)
        volumeContainerLayout.setContentsMargins(0, 0, 0, 0)
        volumeContainerLayout.setSpacing(5)

        self.volumeButton = ToolButton(FluentIcon.VOLUME)
        if self.userMutedIntent:
            self.volumeButton.setIcon(FluentIcon.MUTE)
        self.volumeButton.clicked.connect(self.toggle_mute)

        self.volumeValueLabel = CaptionLabel(f"{initial_vol}%")
        if self.userMutedIntent:
            self.volumeValueLabel.setText("0%")
        self.volumeValueLabel.setFixedWidth(40)
        self.volumeValueLabel.setStyleSheet(
            "border: none; background: transparent; color: #ccc; font-size: 12px;"
        )
        self.volumeValueLabel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.volumeValueLabel.mousePressEvent = lambda e: self.show_volume_flyout()

        volumeContainerLayout.addWidget(self.volumeButton)
        volumeContainerLayout.addWidget(self.volumeValueLabel)
        buttonsLayout.addWidget(volumeContainer)

        buttonsLayout.addSpacing(20)

        self.togglePlaylistButton = ToolButton(FluentIcon.MENU)
        self.togglePlaylistButton.setToolTip(tr('tip_playlist'))
        self.togglePlaylistButton.clicked.connect(self.toggle_playlist)
        buttonsLayout.addWidget(self.togglePlaylistButton)

        self.toggleDrawingButton = ToolButton(FluentIcon.EDIT)
        self.toggleDrawingButton.setToolTip(tr('tip_drawing'))
        self.toggleDrawingButton.clicked.connect(self.toggle_drawing_panel)
        buttonsLayout.addWidget(self.toggleDrawingButton)

        self.controlsLayout.addLayout(buttonsLayout)

        # Setup auto-hide controls timer for fullscreen
        self.controls_timer = QTimer(self)
        self.controls_timer.setInterval(3000)
        self.controls_timer.setSingleShot(True)
        self.controls_timer.timeout.connect(self.hide_controls)
        
        # Install event filters to detect user interaction recursively
        self.install_controls_event_filter(self.controlsCard)
        self.install_controls_event_filter(self.view)

    def install_controls_event_filter(self, widget):
        widget.installEventFilter(self)
        widget.setMouseTracking(True)
        for child in widget.findChildren(QWidget):
            child.installEventFilter(self)
            child.setMouseTracking(True)

    def show_controls(self):
        if not getattr(self, 'is_full_screen', False):
            self.controlsCard.show()
            if hasattr(self, 'controls_timer'):
                self.controls_timer.stop()
            # Ensure mouse cursor is restored in windowed mode
            if hasattr(self, 'view') and not getattr(self.view, 'drawing_mode', False):
                self.setCursor(Qt.CursorShape.ArrowCursor)
                self.view.setCursor(Qt.CursorShape.ArrowCursor)
            return
            
        if not self.controlsCard.isVisible():
            self.controlsCard.show()
            
        # Restore any sidebars that were hidden by the controls auto-hide in fullscreen
        hidden_sidebars = getattr(self, 'sidebars_hidden_by_controls', None)
        if hidden_sidebars:
            if hidden_sidebars.get('playlist') and hasattr(self, 'playlistContainer'):
                self.playlistContainer.show()
            if hidden_sidebars.get('drawing') and hasattr(self, 'drawingContainer'):
                self.drawingContainer.show()
            if hidden_sidebars.get('settings') and hasattr(self, 'settingsContainer'):
                self.settingsContainer.show()
            if hidden_sidebars.get('global_settings') and hasattr(self, 'globalSettingsContainer'):
                self.globalSettingsContainer.show()
            self.sidebars_hidden_by_controls = None
            
        if hasattr(self, 'controls_timer'):
            self.controls_timer.start()

        # Restore mouse cursor in fullscreen on movement
        if hasattr(self, 'view') and not getattr(self.view, 'drawing_mode', False):
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.view.setCursor(Qt.CursorShape.ArrowCursor)
            
        if hasattr(self, 'update_sidebar_fullscreen_state'):
            self.update_sidebar_fullscreen_state()
        if hasattr(self, 'update_sidebar_margins'):
            self.update_sidebar_margins()

    def hide_controls(self):
        if getattr(self, 'is_full_screen', False):
            # Only hide if mouse is not directly hovering over the controlsCard itself!
            if self.controlsCard.underMouse():
                if hasattr(self, 'controls_timer'):
                    self.controls_timer.start()
                return
                
            # Save currently visible sidebars to restore them when controls show up again
            self.sidebars_hidden_by_controls = {
                'playlist': hasattr(self, 'playlistContainer') and self.playlistContainer.isVisible(),
                'drawing': hasattr(self, 'drawingContainer') and self.drawingContainer.isVisible(),
                'settings': hasattr(self, 'settingsContainer') and self.settingsContainer.isVisible(),
                'global_settings': hasattr(self, 'globalSettingsContainer') and self.globalSettingsContainer.isVisible()
            }
            
            # Hide the controlsCard and all sidebars in fullscreen
            self.controlsCard.hide()
            if hasattr(self, 'playlistContainer'):
                self.playlistContainer.hide()
            if hasattr(self, 'drawingContainer'):
                self.drawingContainer.hide()
            if hasattr(self, 'settingsContainer'):
                self.settingsContainer.hide()
            if hasattr(self, 'globalSettingsContainer'):
                self.globalSettingsContainer.hide()
            
            # Hide mouse cursor in fullscreen after 3s of inactivity
            if hasattr(self, 'view') and not getattr(self.view, 'drawing_mode', False):
                self.setCursor(Qt.CursorShape.BlankCursor)
                self.view.setCursor(Qt.CursorShape.BlankCursor)
                
            if hasattr(self, 'update_sidebar_margins'):
                self.update_sidebar_margins()

    def eventFilter(self, watched, event):
        if event.type() in [QEvent.Type.MouseMove, QEvent.Type.HoverMove, QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease]:
            if getattr(self, 'is_full_screen', False):
                self.show_controls()
        
        try:
            return super().eventFilter(watched, event)
        except AttributeError:
            return False
