"""
SettingsMixin — video settings sidebar builder (speed, zoom, cache,
                image adjustments, loop controls, action grid).
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QSlider,
                              QGridLayout, QWidget, QComboBox)
from qfluentwidgets import (CaptionLabel, SwitchButton, PushButton,
                             SingleDirectionScrollArea)
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

        self._build_speed_section()
        self._build_zoom_section()
        self._build_cache_section()
        self._build_image_adj_section()
        self._build_loop_section()

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
        self.zoomSlider.valueChanged.connect(self.update_zoom)
        zoomGroup.addWidget(self.zoomSlider)

        self.settingsInnerLayout.addLayout(zoomGroup)
        self.settingsInnerLayout.addWidget(
            QFrame(frameShape=QFrame.Shape.HLine, frameShadow=QFrame.Shadow.Sunken)
        )

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

        def update_cache_size(val):
            rounded_val = (val // 10) * 10
            self.cache_window_half = rounded_val
            self.cacheValueLabel.setText(str(rounded_val))
            if val != rounded_val:
                self.cacheSlider.blockSignals(True)
                self.cacheSlider.setValue(rounded_val)
                self.cacheSlider.blockSignals(False)

        self.cacheSlider.valueChanged.connect(update_cache_size)
        cacheGroup.addWidget(self.cacheSlider)
        self.settingsInnerLayout.addLayout(cacheGroup)
        self.settingsInnerLayout.addWidget(
            QFrame(frameShape=QFrame.Shape.HLine, frameShadow=QFrame.Shadow.Sunken)
        )

    def _build_image_adj_section(self):
        self.adjLabel = CaptionLabel(tr('image_adjustments'))
        self.adjLabel.setStyleSheet("font-weight: bold; margin-top: 5px;")
        self.settingsInnerLayout.addWidget(self.adjLabel)

        def create_adj_slider(label_text, min_val, max_val, default):
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
            slider.valueChanged.connect(
                lambda v: (val_lbl.setText(str(v)), self.update_pixmap_from_cache())
            )
            layout.addLayout(header)
            layout.addWidget(slider)
            return slider, lbl, layout

        self.brightnessSlider, self.brightnessLabel, l1 = create_adj_slider(tr('brightness'), -100, 100, 0)
        self.contrastSlider,   self.contrastLabel,   l2 = create_adj_slider(tr('contrast'),     0, 200, 100)
        self.gammaSlider,      self.gammaLabel,      l3 = create_adj_slider(tr('gamma'),        10, 300, 100)
        self.saturationSlider, self.saturationLabel, l4 = create_adj_slider(tr('saturation'),    0, 200, 100)

        for l in [l1, l2, l3, l4]:
            self.settingsInnerLayout.addLayout(l)

        footerLayout = QHBoxLayout()
        footerLayout.setSpacing(6)
        self.resetAdjButton = PushButton(tr('reset_image'))
        self.resetAdjButton.clicked.connect(self.reset_adjustments)
        self.infoButton = PushButton(tr('file_info'))
        self.infoButton.clicked.connect(self.show_file_info)
        for btn in [self.resetAdjButton, self.infoButton]:
            btn.setStyleSheet(ACTION_BTN_STYLE)
        footerLayout.addWidget(self.resetAdjButton)
        footerLayout.addWidget(self.infoButton)
        self.settingsInnerLayout.addLayout(footerLayout)
        self.settingsInnerLayout.addWidget(
            QFrame(frameShape=QFrame.Shape.HLine, frameShadow=QFrame.Shadow.Sunken)
        )

    def _build_loop_section(self):
        loopGroup = QVBoxLayout()
        loopGroup.setSpacing(10)

        self.loopCombo = QComboBox()
        self.loopCombo.addItems([tr('loop_none'), tr('loop_forward'), tr('loop_backward'), tr('loop_pingpong')])
        self.loopCombo.setCurrentIndex(3)
        self.loopCombo.currentIndexChanged.connect(self.on_loop_mode_changed)
        # Style will be set in refresh_custom_styles

        loopHeader = QHBoxLayout()
        self.loopLabel = CaptionLabel(tr('loop'))
        self.loopToggle = SwitchButton()
        self.loopToggle.setChecked(self.loopCombo.currentIndex() != 0)
        self.loopToggle.setOnText(tr('on'))
        self.loopToggle.setOffText(tr('off'))
        self.loopToggle.checkedChanged.connect(self.on_loop_switch_toggled)
        loopHeader.addWidget(self.loopLabel)
        loopHeader.addStretch(1)
        loopHeader.addWidget(self.loopToggle)
        loopGroup.addLayout(loopHeader)

        globalLoopHeader = QHBoxLayout()
        self.globalLoopLabel = CaptionLabel(tr('global_loop_mode'))
        self.globalLoopToggle = SwitchButton()
        self.globalLoopToggle.setChecked(True)
        self.globalLoopToggle.setOnText(tr('on'))
        self.globalLoopToggle.setOffText(tr('off'))
        self.globalLoopToggle.setToolTip("Apply loop mode to all videos")
        globalLoopHeader.addWidget(self.globalLoopLabel)
        globalLoopHeader.addStretch(1)
        globalLoopHeader.addWidget(self.globalLoopToggle)
        loopGroup.addLayout(globalLoopHeader)

        navGroup = QHBoxLayout()
        self.navLabel = CaptionLabel(tr('zoom_nav_bar'))
        self.navToggle = SwitchButton()
        self.navToggle.setChecked(False)
        self.navToggle.setOnText(tr('on'))
        self.navToggle.setOffText(tr('off'))

        def toggle_nav_mode(checked):
            self.is_zoomed_nav = checked
            self.sync_progress_bar()

        self.navToggle.checkedChanged.connect(toggle_nav_mode)
        navGroup.addWidget(self.navLabel)
        navGroup.addStretch(1)
        navGroup.addWidget(self.navToggle)
        loopGroup.addLayout(navGroup)
        loopGroup.addWidget(self.loopCombo)

        markerLayout = QHBoxLayout()
        markerLayout.setSpacing(6)
        self.smartMarkButton = PushButton(tr('mark'))
        self.smartMarkButton.setStyleSheet(TOOL_BTN_STYLE)
        self.smartMarkButton.clicked.connect(self.add_smart_marker)
        self.deleteMarkerButton = PushButton(tr('delete'))
        self.deleteMarkerButton.setStyleSheet(TOOL_BTN_STYLE)
        self.deleteMarkerButton.clicked.connect(self.delete_nearest_marker)
        self.clearMarkersButton = PushButton(tr('reset'))
        self.clearMarkersButton.setStyleSheet(TOOL_BTN_STYLE)
        self.clearMarkersButton.clicked.connect(self.clear_loop_markers)
        markerLayout.addWidget(self.smartMarkButton)
        markerLayout.addWidget(self.deleteMarkerButton)
        markerLayout.addWidget(self.clearMarkersButton)
        loopGroup.addLayout(markerLayout)

        self.loopFramesLabel = CaptionLabel("[F: 0 - End]")
        self.loopFramesLabel.setStyleSheet("color: #aaa; font-size: 11px; margin-top: 2px;")
        loopGroup.addWidget(self.loopFramesLabel)

        self.actionsGrid = QGridLayout()
        self.actionsGrid.setSpacing(6)
        self.saveLoopButton = PushButton(tr('save_loop'))
        self.saveLoopButton.clicked.connect(self.save_loop_segment)
        self.saveFrameButton = PushButton(tr('save_frame'))
        self.saveFrameButton.clicked.connect(self.save_current_frame)
        self.mirrorButton = PushButton(tr('mirror_h'))
        self.mirrorButton.clicked.connect(self.toggle_mirror)
        self.mirrorVerticalButton = PushButton(tr('mirror_v'))
        self.mirrorVerticalButton.clicked.connect(self.toggle_vertical_mirror)
        self.rotateButton = PushButton(tr('rotate'))
        self.rotateButton.clicked.connect(self.rotate_video)

        for btn in [self.saveLoopButton, self.saveFrameButton,
                    self.mirrorButton, self.mirrorVerticalButton, self.rotateButton]:
            btn.setStyleSheet(ACTION_BTN_STYLE)

        self.actionsGrid.addWidget(self.saveLoopButton,       0, 0)
        self.actionsGrid.addWidget(self.saveFrameButton,      0, 1)
        self.actionsGrid.addWidget(self.mirrorButton,         1, 0)
        self.actionsGrid.addWidget(self.mirrorVerticalButton, 1, 1)
        self.actionsGrid.addWidget(self.rotateButton,         2, 0, 1, 2)
        loopGroup.addLayout(self.actionsGrid)

        self.settingsInnerLayout.addLayout(loopGroup)
        self.settingsInnerLayout.addWidget(
            QFrame(frameShape=QFrame.Shape.HLine, frameShadow=QFrame.Shadow.Sunken)
        )
