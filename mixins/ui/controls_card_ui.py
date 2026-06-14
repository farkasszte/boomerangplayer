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
        buttonsLayout.setSpacing(8)

        self.toggleSettingsButton = ToolButton(FluentIcon.VIDEO)
        self.toggleSettingsButton.setToolTip(tr('video_settings'))
        self.toggleSettingsButton.setFixedSize(32, 32)
        self.toggleSettingsButton.clicked.connect(self.toggle_settings)
        buttonsLayout.addWidget(self.toggleSettingsButton)

        self.toggleImageAdjustButton = ToolButton(FluentIcon.PHOTO)
        self.toggleImageAdjustButton.setToolTip(tr('image_adjustments'))
        self.toggleImageAdjustButton.setFixedSize(32, 32)
        self.toggleImageAdjustButton.clicked.connect(self.toggle_image_adj)
        buttonsLayout.addWidget(self.toggleImageAdjustButton)

        self.toggleSubtitlePanelButton = ToolButton(FluentIcon.CHAT)
        self.toggleSubtitlePanelButton.setToolTip(tr('subtitles'))
        self.toggleSubtitlePanelButton.setFixedSize(32, 32)
        self.toggleSubtitlePanelButton.clicked.connect(self.toggle_subtitle_panel)
        buttonsLayout.addWidget(self.toggleSubtitlePanelButton)

        self.globalSettingsButton = ToolButton(FluentIcon.SETTING)
        self.globalSettingsButton.setToolTip(tr('tip_settings'))
        self.globalSettingsButton.setFixedSize(32, 32)
        self.globalSettingsButton.clicked.connect(self.show_global_settings)
        buttonsLayout.addWidget(self.globalSettingsButton)



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

        self.fullScreenButton = ToolButton(FluentIcon.FULL_SCREEN)
        self.fullScreenButton.setToolTip(tr('tip_full_screen'))
        self.fullScreenButton.setIconSize(QSize(24, 24))
        self.fullScreenButton.setFixedSize(32, 32)
        self.fullScreenButton.setStyleSheet(
            COMPACT_BTN_STYLE + "ToolButton { border-radius: 0px; border-right: none; }"
        )
        self.fullScreenButton.clicked.connect(self.toggle_full_screen)

        playbackButtonsLayout.addWidget(self.stepBackButton)
        playbackButtonsLayout.addWidget(self.playBackwardButton)
        playbackButtonsLayout.addWidget(self.fullScreenButton)
        playbackButtonsLayout.addWidget(self.playButton)
        playbackButtonsLayout.addWidget(self.stepForwardButton)

        buttonsLayout.addStretch(1)
        buttonsLayout.addLayout(playbackButtonsLayout)
        buttonsLayout.addStretch(1)

        # Volume
        volumeContainer = QWidget()
        volumeContainerLayout = QHBoxLayout(volumeContainer)
        volumeContainerLayout.setContentsMargins(0, 0, 0, 0)
        volumeContainerLayout.setSpacing(8)

        self.volumeButton = ToolButton(FluentIcon.VOLUME)
        self.volumeButton.setFixedSize(32, 32)
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

        volumeContainerLayout.addWidget(self.volumeValueLabel)
        volumeContainerLayout.addWidget(self.volumeButton)
        buttonsLayout.addWidget(volumeContainer)

        # Audio Button (moved from left side)
        self.toggleAudioButton = ToolButton(FluentIcon.MUSIC)
        self.toggleAudioButton.setToolTip(tr('audio_settings'))
        self.toggleAudioButton.setFixedSize(32, 32)
        self.toggleAudioButton.clicked.connect(self.toggle_audio_panel)
        buttonsLayout.addWidget(self.toggleAudioButton)

        self.toggleDrawingButton = ToolButton(FluentIcon.EDIT)
        self.toggleDrawingButton.setToolTip(tr('tip_drawing'))
        self.toggleDrawingButton.setFixedSize(32, 32)
        self.toggleDrawingButton.clicked.connect(self.toggle_drawing_panel)
        buttonsLayout.addWidget(self.toggleDrawingButton)

        self.togglePlaylistButton = ToolButton(FluentIcon.MENU)
        self.togglePlaylistButton.setToolTip(tr('tip_playlist'))
        self.togglePlaylistButton.setFixedSize(32, 32)
        self.togglePlaylistButton.clicked.connect(self.toggle_playlist)
        buttonsLayout.addWidget(self.togglePlaylistButton)

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
            if hasattr(self, 'position_subtitle_label'):
                self.position_subtitle_label()
            
        # Restore any sidebars that were hidden by the controls auto-hide in fullscreen
        hidden_sidebars = getattr(self, 'sidebars_hidden_by_controls', None)
        if hidden_sidebars:
            if hidden_sidebars.get('playlist') and hasattr(self, 'playlistContainer'):
                self.playlistContainer.show()
            if hidden_sidebars.get('drawing') and hasattr(self, 'drawingContainer'):
                self.drawingContainer.show()
            if hidden_sidebars.get('settings') and hasattr(self, 'settingsContainer'):
                self.settingsContainer.show()
            if hidden_sidebars.get('image_adj') and hasattr(self, 'imageAdjContainer'):
                self.imageAdjContainer.show()
            if hidden_sidebars.get('subtitle') and hasattr(self, 'subtitleContainer'):
                self.subtitleContainer.show()
            if hidden_sidebars.get('audio') and hasattr(self, 'audioContainer'):
                self.audioContainer.show()
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
                'image_adj': hasattr(self, 'imageAdjContainer') and self.imageAdjContainer.isVisible(),
                'global_settings': hasattr(self, 'globalSettingsContainer') and self.globalSettingsContainer.isVisible(),
                'subtitle': hasattr(self, 'subtitleContainer') and self.subtitleContainer.isVisible(),
                'audio': hasattr(self, 'audioContainer') and self.audioContainer.isVisible()
            }
            
            # Hide the controlsCard and all sidebars in fullscreen
            self.controlsCard.hide()
            if hasattr(self, 'position_subtitle_label'):
                self.position_subtitle_label()
                
            if hasattr(self, 'playlistContainer'):
                self.playlistContainer.hide()
            if hasattr(self, 'drawingContainer'):
                self.drawingContainer.hide()
            if hasattr(self, 'settingsContainer'):
                self.settingsContainer.hide()
            if hasattr(self, 'imageAdjContainer'):
                self.imageAdjContainer.hide()
            if hasattr(self, 'subtitleContainer'):
                self.subtitleContainer.hide()
            if hasattr(self, 'audioContainer'):
                self.audioContainer.hide()
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

    def show_about_dialog(self):
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
        from PyQt6.QtCore import Qt
        from utils import VERSION
        
        dialog = QDialog(self)
        if hasattr(self, 'style_dialog'):
            self.style_dialog(dialog)
            
        dialog.setWindowTitle(tr('about_title'))
        dialog.setFixedSize(380, 240)
        
        # Apply Windows 11 title bar styling using DWM API
        import sys
        if sys.platform == 'win32':
            try:
                import ctypes
                hwnd = int(dialog.winId())
                bg_color = self.config.get('bg_color', '#202020')
                from PyQt6.QtGui import QColor
                def qcolor_to_colorref(qcolor):
                    return qcolor.red() | (qcolor.green() << 8) | (qcolor.blue() << 16)
                bg_color_ref = qcolor_to_colorref(QColor(bg_color))
                # DWMWA_CAPTION_COLOR = 35 (Windows 11 Build 22000+)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    35,
                    ctypes.byref(ctypes.c_int(bg_color_ref)),
                    4
                )
            except Exception as e:
                print(f"[DWM] Failed to set about dialog title bar color: {e}")
                
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(12)
        
        # Title
        title_lbl = QLabel(f"Boomerang Player v{VERSION}")
        title_lbl.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 2px;")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_lbl)
        
        # Description
        desc_lbl = QLabel(tr('about_desc'))
        desc_lbl.setWordWrap(True)
        desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc_lbl)
        
        # Github Link
        accent = self.config.get('accent_color', '#00f2ff')
        link_html = f'<a href="https://github.com/farkasszte/boomerangplayer" style="color: {accent}; text-decoration: none; font-weight: bold;">github.com/farkasszte/boomerangplayer</a>'
        link_lbl = QLabel(link_html)
        link_lbl.setOpenExternalLinks(True)
        link_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        link_lbl.setStyleSheet("font-size: 13px;")
        layout.addWidget(link_lbl)
        
        layout.addStretch()
        
        # Close button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton(tr('close'))
        close_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(close_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        dialog.exec()
