"""
SettingsMixin — video settings sidebar builder (speed, zoom, cache,
                image adjustments, loop controls, action grid).
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QSlider,
                              QGridLayout, QWidget, QComboBox, QSpinBox)
from qfluentwidgets import (CaptionLabel, SwitchButton, PushButton,
                             SingleDirectionScrollArea, ToolButton, FluentIcon,
                             FluentIconBase, Theme)
from styles import (FLUENT_SLIDER_STYLE, TOOL_BTN_STYLE, ACTION_BTN_STYLE)
from translations import tr
import os


class LocalIcon(FluentIconBase):
    def __init__(self, filename):
        self.filename = filename

    def path(self, theme=Theme.AUTO):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_dir, 'resources', self.filename)


LOCK_ICON = LocalIcon('lock.svg')
UNLOCK_ICON = LocalIcon('unlock.svg')



from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QMainWindow, QSlider, QLabel, QComboBox
    from config import Configuration
    SettingsMixinBase = QMainWindow
else:
    SettingsMixinBase = object


class SettingsMixin(SettingsMixinBase):
    if TYPE_CHECKING:
        config: Configuration
        cache_window_half: int
        cacheValueLabel: QSpinBox
        cacheSlider: QSlider
        loopCombo: QComboBox
        speedSlider: QSlider
        speedValueLabel: QSpinBox
        zoomSlider: QSlider
        zoomValueLabel: QSpinBox
        isSpeedLocked: bool
        speedLockBtn: ToolButton
        brightnessSlider: QSlider
        contrastSlider: QSlider
        gammaSlider: QSlider
        saturationSlider: QSlider
        is_motion_photo: bool
        
        update_zoom: callable
        update_pixmap_from_cache: callable

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
        self.speedValueLabel = QSpinBox()
        self.speedValueLabel.setRange(10, 500)
        self.speedValueLabel.setValue(100)
        self.speedValueLabel.setSuffix("%")
        self.speedValueLabel.setFixedWidth(80)
        self.speedValueLabel.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        
        # Speed lock state
        self.isSpeedLocked = self.config.get('speed_locked', False)
        self.speedLockBtn = ToolButton(UNLOCK_ICON, self.settingsContainer)
        self.speedLockBtn.setCheckable(True)
        self.speedLockBtn.setFixedWidth(32)
        self.speedLockBtn.setFixedHeight(32)
        self.speedLockBtn.setStyleSheet("""
            ToolButton {
                background: transparent;
                border: none;
                border-radius: 4px;
            }
            ToolButton:hover {
                background: rgba(255, 255, 255, 0.08);
            }
            ToolButton:pressed {
                background: rgba(255, 255, 255, 0.04);
            }
        """)
        
        def toggle_speed_lock():
            self.isSpeedLocked = not self.isSpeedLocked
            self.config['speed_locked'] = self.isSpeedLocked
            self.config.save()
            self.update_lock_icon()
            
        self.speedLockBtn.clicked.connect(toggle_speed_lock)
        self.update_lock_icon()

        speedHeader.addWidget(self.speedLabel)
        speedHeader.addStretch(1)
        speedHeader.addWidget(self.speedLockBtn)
        speedHeader.addWidget(self.speedValueLabel)

        self.speedSlider = QSlider(Qt.Orientation.Horizontal)
        self.speedSlider.setRange(10, 500)
        self.speedSlider.setValue(100)
        self.speedSlider.setStyleSheet(FLUENT_SLIDER_STYLE)
        self.speedSlider.setToolTip(tr('tip_playback_speed'))
        
        def update_speed(val):
            rounded_val = round(val / 5) * 5
            self.speedValueLabel.blockSignals(True)
            self.speedValueLabel.setValue(rounded_val)
            self.speedValueLabel.blockSignals(False)
            if val != rounded_val:
                self.speedSlider.blockSignals(True)
                self.speedSlider.setValue(rounded_val)
                self.speedSlider.blockSignals(False)
            
            # Apply playback speed change
            rate = rounded_val / 100.0
            if hasattr(self, 'mediaPlayer') and self.mediaPlayer is not None:
                self.mediaPlayer.setPlaybackRate(rate)
            if not getattr(self, '_block_broadcast', False) and hasattr(self, 'broadcast_sync_event'):
                
                self.broadcast_sync_event("speed", rounded_val)

        self.speedSlider.valueChanged.connect(update_speed)
        self.speedValueLabel.valueChanged.connect(update_speed)
        
        self.settingsInnerLayout.addLayout(speedHeader)
        self.settingsInnerLayout.addWidget(self.speedSlider)

    def _build_zoom_section(self):
        zoomGroup = QVBoxLayout()
        zoomGroup.setSpacing(5)
        zoomHeader = QHBoxLayout()
        self.zoomLabel = CaptionLabel(tr('zoom'))
        self.zoomValueLabel = QSpinBox()
        self.zoomValueLabel.setRange(100, 1000)
        self.zoomValueLabel.setValue(100)
        self.zoomValueLabel.setSuffix("%")
        self.zoomValueLabel.setFixedWidth(80)
        self.zoomValueLabel.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        zoomHeader.addWidget(self.zoomLabel)
        zoomHeader.addStretch(1)
        zoomHeader.addWidget(self.zoomValueLabel)
        zoomGroup.addLayout(zoomHeader)

        self.zoomSlider = QSlider(Qt.Orientation.Horizontal)
        self.zoomSlider.setRange(100, 1000)
        self.zoomSlider.setValue(100)
        self.zoomSlider.setStyleSheet(FLUENT_SLIDER_STYLE)
        self.zoomSlider.setToolTip(tr('tip_zoom'))
        
        def update_zoom_val(val):
            rounded_val = round(val / 20) * 20
            if rounded_val < 100:
                rounded_val = 100
            
            self.zoomValueLabel.blockSignals(True)
            self.zoomValueLabel.setValue(rounded_val)
            self.zoomValueLabel.blockSignals(False)
            if val != rounded_val:
                self.zoomSlider.blockSignals(True)
                self.zoomSlider.setValue(rounded_val)
                self.zoomSlider.blockSignals(False)
            
            # Apply zoom transform
            self.zoomLevel = rounded_val / 100.0
            if hasattr(self, 'view') and self.view is not None:
                from PyQt6.QtWidgets import QGraphicsView
                factor = self.zoomLevel / self.view.zoomLevel
                self.view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
                self.view.scale(factor, factor)
                self.view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
                self.view.zoomLevel = self.zoomLevel

        self.zoomSlider.valueChanged.connect(update_zoom_val)
        self.zoomValueLabel.valueChanged.connect(update_zoom_val)
        
        zoomGroup.addWidget(self.zoomSlider)

        self.settingsInnerLayout.addLayout(zoomGroup)

    def _build_cache_section(self):
        cacheGroup = QVBoxLayout()
        cacheGroup.setSpacing(5)
        cacheHeader = QHBoxLayout()
        self.cacheLabel = CaptionLabel(tr('cache_window'))
        self.cacheValueLabel = QSpinBox()
        self.cacheValueLabel.setRange(100, 3000)
        self.cacheValueLabel.setValue(self.cache_window_half)
        self.cacheValueLabel.setFixedWidth(80)
        self.cacheValueLabel.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        cacheHeader.addWidget(self.cacheLabel)
        cacheHeader.addStretch(1)
        cacheHeader.addWidget(self.cacheValueLabel)
        cacheGroup.addLayout(cacheHeader)

        self.cacheSlider = QSlider(Qt.Orientation.Horizontal)
        self.cacheSlider.setRange(100, 3000)
        self.cacheSlider.setSingleStep(10)
        self.cacheSlider.setPageStep(50)
        self.cacheSlider.setValue(self.cache_window_half)
        self.cacheSlider.setStyleSheet(FLUENT_SLIDER_STYLE)
        self.cacheSlider.setToolTip(tr('tip_cache_window'))

        def update_cache_size(val):
            rounded_val = (val // 10) * 10
            self.cache_window_half = rounded_val
            self.cacheValueLabel.blockSignals(True)
            self.cacheValueLabel.setValue(rounded_val)
            self.cacheValueLabel.blockSignals(False)
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
        self.cacheValueLabel.valueChanged.connect(self.cacheSlider.setValue)
        cacheGroup.addWidget(self.cacheSlider)
        
        # --- MJPEG Quality Slider ---
        qvGroup = QVBoxLayout()
        qvGroup.setSpacing(5)
        qvHeader = QHBoxLayout()
        self.qvLabel = CaptionLabel(tr('mjpeg_quality'))
        self.qvValueSpinBox = QSpinBox()
        self.qvValueSpinBox.setRange(1, 31)
        default_qv = self.config.get('qv_value', 2)
        self.qvValueSpinBox.setValue(default_qv)
        self.qvValueSpinBox.setFixedWidth(80)
        self.qvValueSpinBox.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        qvHeader.addWidget(self.qvLabel)
        qvHeader.addStretch(1)
        qvHeader.addWidget(self.qvValueSpinBox)
        qvGroup.addLayout(qvHeader)

        self.qvSlider = QSlider(Qt.Orientation.Horizontal)
        self.qvSlider.setRange(1, 31)
        self.qvSlider.setValue(default_qv)
        self.qvSlider.setStyleSheet(FLUENT_SLIDER_STYLE)
        self.qvSlider.setToolTip(tr('tip_mjpeg_quality'))
        
        def update_qv(val):
            self.config['qv_value'] = val
            self.config.save()
            
            self.qvValueSpinBox.blockSignals(True)
            self.qvValueSpinBox.setValue(val)
            self.qvValueSpinBox.blockSignals(False)
            
            self.qvSlider.blockSignals(True)
            self.qvSlider.setValue(val)
            self.qvSlider.blockSignals(False)
            
            # Debounce extraction
            if hasattr(self, '_qv_debounce_timer'):
                self._qv_debounce_timer.stop()
            from PyQt6.QtCore import QTimer
            self._qv_debounce_timer = QTimer()
            self._qv_debounce_timer.setSingleShot(True)
            self._qv_debounce_timer.timeout.connect(
                
                lambda: self.request_frame_extraction(self.current_cache_index, force=True)
                        if getattr(self, 'currentFilePath', None) else None
            )
            self._qv_debounce_timer.start(300)

        self.qvSlider.valueChanged.connect(update_qv)
        self.qvValueSpinBox.valueChanged.connect(update_qv)
        qvGroup.addWidget(self.qvSlider)
        cacheGroup.addLayout(qvGroup)
        
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
            
            spin = QSpinBox()
            spin.setRange(min_val, max_val)
            spin.setValue(default)
            spin.setFixedWidth(80)
            spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
            
            header.addWidget(lbl)
            header.addStretch(1)
            header.addWidget(spin)
            
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(min_val, max_val)
            slider.setValue(default)
            slider.setStyleSheet(FLUENT_SLIDER_STYLE)
            slider.setToolTip(tr(tip_key))
            
            slider.valueChanged.connect(
                lambda v: (
                    spin.blockSignals(True),
                    spin.setValue(v),
                    spin.blockSignals(False),
                    self.update_pixmap_from_cache()
                )
            )
            spin.valueChanged.connect(
                lambda v: (
                    slider.blockSignals(True),
                    slider.setValue(v),
                    slider.blockSignals(False),
                    self.update_pixmap_from_cache()
                )
            )
            layout.addLayout(header)
            layout.addWidget(slider)
            return slider, lbl, layout, spin

        self.brightnessSlider, self.brightnessLabel, l1, self.brightnessSpinBox = create_adj_slider(tr('brightness'), -100, 100, 0, 'tip_brightness')
        self.contrastSlider,   self.contrastLabel,   l2, self.contrastSpinBox   = create_adj_slider(tr('contrast'),     0, 200, 100, 'tip_contrast')
        self.gammaSlider,      self.gammaLabel,      l3, self.gammaSpinBox      = create_adj_slider(tr('gamma'),        10, 300, 100, 'tip_gamma')
        self.saturationSlider, self.saturationLabel, l4, self.saturationSpinBox = create_adj_slider(tr('saturation'),    0, 200, 100, 'tip_saturation')

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

        # Zoom to loop toggle
        zoomToLoopGroup = QHBoxLayout()
        self.zoomToLoopLabel = CaptionLabel(tr('zoom_to_loop'))
        self.zoomToLoopToggle = SwitchButton()
        self.zoomToLoopToggle.setChecked(False)
        self.zoomToLoopToggle.setOnText(tr('on'))
        self.zoomToLoopToggle.setOffText(tr('off'))
        self.zoomToLoopToggle.setToolTip(tr('tip_zoom_to_loop'))

        def toggle_zoom_to_loop(checked):
            self.is_zoomed_loop = checked
            if checked:
                self.zoomToWindowToggle.blockSignals(True)
                self.zoomToWindowToggle.setChecked(False)
                self.zoomToWindowToggle.blockSignals(False)
                self.is_zoomed_window = False
            self.sync_progress_bar()

        self.zoomToLoopToggle.checkedChanged.connect(toggle_zoom_to_loop)
        zoomToLoopGroup.addWidget(self.zoomToLoopLabel)
        zoomToLoopGroup.addStretch(1)
        zoomToLoopGroup.addWidget(self.zoomToLoopToggle)
        markersGroup.addLayout(zoomToLoopGroup)

        # Zoom to window toggle + reset button
        zoomToWindowGroup = QHBoxLayout()
        self.zoomToWindowLabel = CaptionLabel(tr('zoom_to_window'))
        
        self.zoomWindowResetBtn = ToolButton(FluentIcon.SYNC, self.settingsContainer)
        self.zoomWindowResetBtn.setFixedSize(24, 24)
        self.zoomWindowResetBtn.setToolTip(tr('tip_reset_zoom_window'))
        self.zoomWindowResetBtn.setStyleSheet("""
            ToolButton {
                background: transparent;
                border: none;
                border-radius: 4px;
            }
            ToolButton:hover {
                background: rgba(255, 255, 255, 0.08);
            }
            ToolButton:pressed {
                background: rgba(255, 255, 255, 0.04);
            }
        """)
        
        self.zoomToWindowToggle = SwitchButton()
        self.zoomToWindowToggle.setChecked(False)
        self.zoomToWindowToggle.setOnText(tr('on'))
        self.zoomToWindowToggle.setOffText(tr('off'))
        self.zoomToWindowToggle.setToolTip(tr('tip_zoom_to_window'))

        def toggle_zoom_to_window(checked):
            self.is_zoomed_window = checked
            if checked:
                self.zoomToLoopToggle.blockSignals(True)
                self.zoomToLoopToggle.setChecked(False)
                self.zoomToLoopToggle.blockSignals(False)
                self.is_zoomed_loop = False
                self.zoom_window_anchor = self.current_cache_index
            self.sync_progress_bar()

        def reset_zoom_window():
            self.zoom_window_anchor = self.current_cache_index
            self.sync_progress_bar()

        self.zoomToWindowToggle.checkedChanged.connect(toggle_zoom_to_window)
        self.zoomWindowResetBtn.clicked.connect(reset_zoom_window)
        
        zoomToWindowGroup.addWidget(self.zoomToWindowLabel)
        zoomToWindowGroup.addStretch(1)
        zoomToWindowGroup.addWidget(self.zoomWindowResetBtn)
        zoomToWindowGroup.addWidget(self.zoomToWindowToggle)
        markersGroup.addLayout(zoomToWindowGroup)

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

    def update_lock_icon(self):
        if not hasattr(self, 'speedLockBtn') or not self.speedLockBtn:
            return
        self.speedLockBtn.setChecked(self.isSpeedLocked)
        if self.isSpeedLocked:
            from qfluentwidgets import themeColor
            # Render the SVG using the active theme accent color
            self.speedLockBtn.setIcon(LOCK_ICON.icon(color=themeColor()))
            self.speedLockBtn.setToolTip(tr('tip_speed_locked'))
        else:
            from PyQt6.QtGui import QColor
            # Render the SVG using white/dark color depending on setting
            unlocked_color = '#1c1c1c' if self.config.get('inverse_text', False) else '#ffffff'
            self.speedLockBtn.setIcon(UNLOCK_ICON.icon(color=QColor(unlocked_color)))
            self.speedLockBtn.setToolTip(tr('tip_speed_unlocked'))


