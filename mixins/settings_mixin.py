"""
SettingsMixin — video settings sidebar builder (speed, zoom, cache,
                image adjustments, loop controls, action grid).
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QSlider,
                              QGridLayout, QWidget, QComboBox)
from qfluentwidgets import (CaptionLabel, SwitchButton, PushButton,
                             SingleDirectionScrollArea, ToolButton, FluentIcon)
from styles import (FLUENT_SLIDER_STYLE, TOOL_BTN_STYLE, ACTION_BTN_STYLE)
from translations import tr


class SettingsMixin:
    """Builds self.settingsContainer and all inner video-settings widgets."""

    def init_video_settings_sidebar(self):
        self.settingsContainer = QFrame()
        self.settingsContainer.setMinimumWidth(250)
        self.settingsContainer.setStyleSheet("background: #202020; border: none;")
        self.settingsLayout = QVBoxLayout(self.settingsContainer)
        self.settingsLayout.setContentsMargins(10, 10, 4, 10)
        self.settingsLayout.setSpacing(6)

        self.settingsTitle = CaptionLabel(tr('video_settings'))
        self.settingsTitle.setStyleSheet("font-size: 16px; font-weight: bold; color: white;")
        self.settingsLayout.addWidget(self.settingsTitle)

        self.scrollArea = SingleDirectionScrollArea(self.settingsContainer, Qt.Orientation.Vertical)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setStyleSheet("background: transparent; border: none;")
        self.scrollArea.setFrameShape(QFrame.Shape.NoFrame)
        self.scrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.settingsScrollWidget = QWidget()
        self.settingsScrollWidget.setStyleSheet("background: transparent;")
        self.settingsInnerLayout = QVBoxLayout(self.settingsScrollWidget)
        self.settingsInnerLayout.setContentsMargins(0, 0, 0, 0)
        self.settingsInnerLayout.setSpacing(6)

        self.scrollArea.setWidget(self.settingsScrollWidget)
        self.settingsLayout.addWidget(self.scrollArea)

        # Playback Section Header
        self.playbackLabel = CaptionLabel(tr('playback'))
        self.playbackLabel.setStyleSheet("font-weight: bold; margin-top: 10px; color: #aaaaaa;")
        self.settingsInnerLayout.addWidget(self.playbackLabel)

        self._build_speed_section()
        self._build_zoom_section()
        self._build_cache_section()
        self._build_image_adj_section()
        self._build_loop_section()
        self._build_markers_section()
        self._build_sync_section()

        self.settingsInnerLayout.addStretch(1)
        self.settingsContainer.hide()

    # ------------------------------------------------------------------ #
    # Sub-builders                                                         #
    # ------------------------------------------------------------------ #

    def _build_speed_section(self):
        speedHeader = QHBoxLayout()
        self.speedLabel = CaptionLabel(tr('playback_speed'))
        self.speedValueLabel = CaptionLabel("1.0x")
        self.speedValueLabel.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        speedHeader.addWidget(self.speedLabel)
        speedHeader.addStretch(1)
        speedHeader.addWidget(self.speedValueLabel)

        self.speedSlider = QSlider(Qt.Orientation.Horizontal)
        self.speedSlider.setRange(10, 500)
        self.speedSlider.setValue(100)
        self.speedSlider.setStyleSheet(FLUENT_SLIDER_STYLE)
        self.speedSlider.setToolTip(tr('tip_playback_speed'))
        self.speedSlider.valueChanged.connect(self.on_speed_slider_changed)
        self.settingsInnerLayout.addLayout(speedHeader)
        self.settingsInnerLayout.addWidget(self.speedSlider)

    def _build_zoom_section(self):
        zoomGroup = QVBoxLayout()
        zoomGroup.setSpacing(5)
        zoomHeader = QHBoxLayout()
        self.zoomLabel = CaptionLabel(tr('zoom'))
        self.zoomValueLabel = CaptionLabel("100%")
        self.zoomValueLabel.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        zoomHeader.addWidget(self.zoomLabel)
        zoomHeader.addStretch(1)
        zoomHeader.addWidget(self.zoomValueLabel)
        zoomGroup.addLayout(zoomHeader)

        self.zoomSlider = QSlider(Qt.Orientation.Horizontal)
        self.zoomSlider.setRange(100, 1000)
        self.zoomSlider.setValue(100)
        self.zoomSlider.setStyleSheet(FLUENT_SLIDER_STYLE)
        self.zoomSlider.setToolTip(tr('tip_zoom'))
        self.zoomSlider.valueChanged.connect(self.update_zoom)
        zoomGroup.addWidget(self.zoomSlider)

        self.settingsInnerLayout.addLayout(zoomGroup)

    def _build_cache_section(self):
        cacheGroup = QVBoxLayout()
        cacheGroup.setSpacing(5)
        cacheHeader = QHBoxLayout()
        self.cacheLabel = CaptionLabel(tr('cache_window'))
        self.cacheValueLabel = CaptionLabel(str(self.cache_window_half))
        self.cacheValueLabel.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        cacheHeader.addWidget(self.cacheLabel)
        cacheHeader.addStretch(1)
        cacheHeader.addWidget(self.cacheValueLabel)
        cacheGroup.addLayout(cacheHeader)

        self.cacheSlider = QSlider(Qt.Orientation.Horizontal)
        self.cacheSlider.setRange(100, 1500)
        self.cacheSlider.setSingleStep(10)
        self.cacheSlider.setPageStep(50)
        self.cacheSlider.setValue(self.cache_window_half)
        self.cacheSlider.setStyleSheet(FLUENT_SLIDER_STYLE)
        self.cacheSlider.setToolTip(tr('tip_cache_window'))

        def update_cache_size(val):
            rounded_val = (val // 10) * 10
            self.cache_window_half = rounded_val
            self.cacheValueLabel.setText(str(rounded_val))
            if val != rounded_val:
                self.cacheSlider.blockSignals(True)
                self.cacheSlider.setValue(rounded_val)
                self.cacheSlider.blockSignals(False)
            
            # Save to config
            self.config['cache_window'] = rounded_val
            self.config.save()
            
            # Debounce: only trigger extraction 300ms after the last slider movement
            if hasattr(self, '_cache_debounce_timer'):
                self._cache_debounce_timer.stop()
            from PyQt6.QtCore import QTimer
            self._cache_debounce_timer = QTimer()
            self._cache_debounce_timer.setSingleShot(True)
            self._cache_debounce_timer.timeout.connect(
                lambda: self.request_frame_extraction(self.current_cache_index, force=True)
                        if getattr(self, 'currentFilePath', None) else None
            )
            self._cache_debounce_timer.start(300)

        self.cacheSlider.valueChanged.connect(update_cache_size)
        cacheGroup.addWidget(self.cacheSlider)
        self.settingsInnerLayout.addLayout(cacheGroup)
        hline2 = QFrame()
        hline2.setFrameShape(QFrame.Shape.HLine)
        hline2.setFrameShadow(QFrame.Shadow.Sunken)
        self.settingsInnerLayout.addWidget(hline2)

    def _build_image_adj_section(self):
        self.adjLabel = CaptionLabel(tr('image_adjustments'))
        self.adjLabel.setStyleSheet("font-weight: bold; margin-top: 10px; color: #aaaaaa;")
        self.settingsInnerLayout.addWidget(self.adjLabel)

        def create_adj_slider(label_text, min_val, max_val, default, tip_key):
            layout = QVBoxLayout()
            header = QHBoxLayout()
            lbl = CaptionLabel(label_text)
            val_lbl = CaptionLabel(str(default))
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            header.addWidget(lbl)
            header.addStretch(1)
            header.addWidget(val_lbl)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(min_val, max_val)
            slider.setValue(default)
            slider.setStyleSheet(FLUENT_SLIDER_STYLE)
            slider.setToolTip(tr(tip_key))
            slider.valueChanged.connect(
                lambda v: (val_lbl.setText(str(v)), self.update_pixmap_from_cache())
            )
            layout.addLayout(header)
            layout.addWidget(slider)
            return slider, lbl, layout

        self.brightnessSlider, self.brightnessLabel, l1 = create_adj_slider(tr('brightness'), -100, 100, 0, 'tip_brightness')
        self.contrastSlider,   self.contrastLabel,   l2 = create_adj_slider(tr('contrast'),     0, 200, 100, 'tip_contrast')
        self.gammaSlider,      self.gammaLabel,      l3 = create_adj_slider(tr('gamma'),        10, 300, 100, 'tip_gamma')
        self.saturationSlider, self.saturationLabel, l4 = create_adj_slider(tr('saturation'),    0, 200, 100, 'tip_saturation')

        for l in [l1, l2, l3, l4]:
            self.settingsInnerLayout.addLayout(l)

        # Mirror and Rotate buttons (placed BEFORE the Alaphelyzet button)
        self.mirrorButton = PushButton(tr('mirror_h'))
        self.mirrorButton.setToolTip(tr('tip_mirror_h'))
        self.mirrorButton.clicked.connect(self.toggle_mirror)
        self.mirrorVerticalButton = PushButton(tr('mirror_v'))
        self.mirrorVerticalButton.setToolTip(tr('tip_mirror_v'))
        self.mirrorVerticalButton.clicked.connect(self.toggle_vertical_mirror)
        
        self.rotateLeftButton = PushButton(tr('rotate_left'))
        self.rotateLeftButton.setToolTip(tr('tip_rotate_left'))
        self.rotateLeftButton.clicked.connect(self.rotate_video_left)
        self.rotateRightButton = PushButton(tr('rotate_right'))
        self.rotateRightButton.setToolTip(tr('tip_rotate_right'))
        self.rotateRightButton.clicked.connect(self.rotate_video_right)

        for btn in [self.mirrorButton, self.mirrorVerticalButton, self.rotateLeftButton, self.rotateRightButton]:
            btn.setStyleSheet(ACTION_BTN_STYLE)

        mirrorRow = QHBoxLayout()
        mirrorRow.setSpacing(6)
        mirrorRow.addWidget(self.mirrorButton)
        mirrorRow.addWidget(self.mirrorVerticalButton)
        self.settingsInnerLayout.addLayout(mirrorRow)

        rotateRow = QHBoxLayout()
        rotateRow.setSpacing(6)
        rotateRow.addWidget(self.rotateLeftButton)
        rotateRow.addWidget(self.rotateRightButton)
        self.settingsInnerLayout.addLayout(rotateRow)

        # Footer row with Alaphelyzet (Reset Image) and Fájl infó (File Info)
        footerLayout = QHBoxLayout()
        footerLayout.setSpacing(6)
        self.resetAdjButton = PushButton(tr('reset_image'))
        self.resetAdjButton.setToolTip(tr('tip_reset_image'))
        self.resetAdjButton.clicked.connect(self.reset_adjustments)
        self.infoButton = PushButton(tr('file_info'))
        self.infoButton.setToolTip(tr('tip_file_info'))
        self.infoButton.clicked.connect(self.show_file_info)
        for btn in [self.resetAdjButton, self.infoButton]:
            btn.setStyleSheet(ACTION_BTN_STYLE)
        footerLayout.addWidget(self.resetAdjButton)
        footerLayout.addWidget(self.infoButton)
        self.settingsInnerLayout.addLayout(footerLayout)

        hline3 = QFrame()
        hline3.setFrameShape(QFrame.Shape.HLine)
        hline3.setFrameShadow(QFrame.Shadow.Sunken)
        self.settingsInnerLayout.addWidget(hline3)

    def _build_loop_section(self):
        loopGroup = QVBoxLayout()
        loopGroup.setSpacing(10)

        # Loop mode header label
        self.loopLabel = CaptionLabel(tr('loop'))
        self.loopLabel.setStyleSheet("font-weight: bold; margin-top: 10px; color: #aaaaaa;")
        loopGroup.addWidget(self.loopLabel)

        # Zoom navigation bar toggle
        navGroup = QHBoxLayout()
        self.navLabel = CaptionLabel(tr('zoom_nav_bar'))
        self.navToggle = SwitchButton()
        self.navToggle.setChecked(False)
        self.navToggle.setOnText(tr('on'))
        self.navToggle.setOffText(tr('off'))
        self.navToggle.setToolTip(tr('tip_zoom_nav_bar'))

        def toggle_nav_mode(checked):
            self.is_zoomed_nav = checked
            self.sync_progress_bar()

        self.navToggle.checkedChanged.connect(toggle_nav_mode)
        navGroup.addWidget(self.navLabel)
        navGroup.addStretch(1)
        navGroup.addWidget(self.navToggle)
        loopGroup.addLayout(navGroup)

        # The loop mode dropdown combo box
        self.loopCombo = QComboBox()
        self.loopCombo.addItems([tr('loop_none'), tr('loop_forward'), tr('loop_backward'), tr('loop_pingpong')])
        self.loopCombo.setCurrentIndex(3)
        self.loopCombo.setToolTip(tr('tip_loop_mode'))
        self.loopCombo.currentIndexChanged.connect(self.on_loop_mode_changed)
        loopGroup.addWidget(self.loopCombo)

        # Save loop and Save frame buttons inside the Hurok section
        self.saveLoopButton = PushButton(tr('save_loop'))
        self.saveLoopButton.setToolTip(tr('tip_save_loop'))
        self.saveLoopButton.clicked.connect(self.save_loop_segment)
        self.saveFrameButton = PushButton(tr('save_frame'))
        self.saveFrameButton.setToolTip(tr('tip_save_frame'))
        self.saveFrameButton.clicked.connect(self.save_current_frame)

        for btn in [self.saveLoopButton, self.saveFrameButton]:
            btn.setStyleSheet(ACTION_BTN_STYLE)

        loopSaveLayout = QHBoxLayout()
        loopSaveLayout.setSpacing(6)
        loopSaveLayout.addWidget(self.saveLoopButton)
        loopSaveLayout.addWidget(self.saveFrameButton)
        loopGroup.addLayout(loopSaveLayout)

        self.settingsInnerLayout.addLayout(loopGroup)

        hline4 = QFrame()
        hline4.setFrameShape(QFrame.Shape.HLine)
        hline4.setFrameShadow(QFrame.Shadow.Sunken)
        self.settingsInnerLayout.addWidget(hline4)

    def _build_markers_section(self):
        markersGroup = QVBoxLayout()
        markersGroup.setSpacing(10)

        # Markers section header
        self.markersTitleLabel = CaptionLabel(tr('markers_title'))
        self.markersTitleLabel.setStyleSheet("font-weight: bold; margin-top: 10px; color: #aaaaaa;")
        markersGroup.addWidget(self.markersTitleLabel)

        # Set up buttons with ACTION_BTN_STYLE
        self.smartMarkButton = PushButton(tr('mark'))
        self.smartMarkButton.setToolTip(tr('tip_mark'))
        self.manageMarkersButton = PushButton(tr('manage_markers'))
        self.manageMarkersButton.setToolTip(tr('tip_manage_markers'))
        self.deleteMarkerButton = PushButton(tr('delete'))
        self.deleteMarkerButton.setToolTip(tr('tip_delete_marker'))
        self.clearMarkersButton = PushButton(tr('reset'))
        self.clearMarkersButton.setToolTip(tr('tip_reset_markers'))

        for btn in [self.smartMarkButton, self.manageMarkersButton, self.deleteMarkerButton, self.clearMarkersButton]:
            btn.setStyleSheet(ACTION_BTN_STYLE)
            btn.clicked.connect(self.add_smart_marker if btn == self.smartMarkButton else
                                self.show_markers_dialog if btn == self.manageMarkersButton else
                                self.delete_nearest_marker if btn == self.deleteMarkerButton else
                                self.clear_loop_markers)

        # Mark and Manage Markers in row 1
        row1 = QHBoxLayout()
        row1.setSpacing(6)
        row1.addWidget(self.smartMarkButton)
        row1.addWidget(self.manageMarkersButton)
        markersGroup.addLayout(row1)

        # Delete and Reset in row 2 below row 1
        row2 = QHBoxLayout()
        row2.setSpacing(6)
        row2.addWidget(self.deleteMarkerButton)
        row2.addWidget(self.clearMarkersButton)
        markersGroup.addLayout(row2)

        self.settingsInnerLayout.addLayout(markersGroup)

        hline_m = QFrame()
        hline_m.setFrameShape(QFrame.Shape.HLine)
        hline_m.setFrameShadow(QFrame.Shadow.Sunken)
        self.settingsInnerLayout.addWidget(hline_m)

    def _build_sync_section(self):
        syncGroup = QVBoxLayout()
        syncGroup.setSpacing(10)

        syncHeader = QHBoxLayout()
        self.syncLabel = CaptionLabel(tr('sync_title'))
        self.syncLabel.setStyleSheet("font-weight: bold; margin-top: 10px; color: #aaaaaa;")
        syncHeader.addWidget(self.syncLabel)
        syncGroup.addLayout(syncHeader)

        # Sync lock toggle row
        syncLockRow = QHBoxLayout()
        self.syncLockLabel = CaptionLabel(tr('sync_lock'))
        self.lockSyncToggle = SwitchButton()
        self.lockSyncToggle.setChecked(self.isSyncLocked)
        self.lockSyncToggle.setOnText(tr('on'))
        self.lockSyncToggle.setOffText(tr('off'))
        self.lockSyncToggle.setToolTip(tr('tip_sync_lock'))
        self.lockSyncToggle.checkedChanged.connect(self.toggle_sync_lock)
        syncLockRow.addWidget(self.syncLockLabel)
        syncLockRow.addStretch(1)
        syncLockRow.addWidget(self.lockSyncToggle)
        syncGroup.addLayout(syncLockRow)

        # Force sync frame button
        self.syncFrameButton = PushButton(tr('sync_frame'))
        self.syncFrameButton.setToolTip(tr('tip_sync_frame'))
        self.syncFrameButton.clicked.connect(self.force_frame_sync_broadcast)
        self.syncFrameButton.setEnabled(True)
        self.syncFrameButton.setStyleSheet(ACTION_BTN_STYLE)
        syncGroup.addWidget(self.syncFrameButton)

        self.settingsInnerLayout.addLayout(syncGroup)

        hline_sync = QFrame()
        hline_sync.setFrameShape(QFrame.Shape.HLine)
        hline_sync.setFrameShadow(QFrame.Shadow.Sunken)
        self.settingsInnerLayout.addWidget(hline_sync)


