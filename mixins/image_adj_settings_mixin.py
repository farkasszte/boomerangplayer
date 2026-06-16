"""
ImageAdjSettingsMixin — builds and manages the image adjustments sidebar UI panel.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QSlider, QWidget
from components import SafeSpinBox as QSpinBox
from qfluentwidgets import CaptionLabel, PushButton, SingleDirectionScrollArea
from styles import (FLUENT_SLIDER_STYLE, ACTION_BTN_STYLE)
from translations import tr

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QMainWindow
    from config import Configuration
    ImageAdjSettingsMixinBase = QMainWindow
else:
    ImageAdjSettingsMixinBase = object


class ImageAdjSettingsMixin(ImageAdjSettingsMixinBase):
    if TYPE_CHECKING:
        config: Configuration
        brightnessSlider: QSlider
        contrastSlider: QSlider
        gammaSlider: QSlider
        saturationSlider: QSlider
        hueSlider: QSlider
        tempSlider: QSlider
        exposureSlider: QSlider
        sharpenSlider: QSlider
        blurSlider: QSlider
        invertButton: PushButton
        brightnessSpinBox: any
        contrastSpinBox: any
        gammaSpinBox: any
        saturationSpinBox: any
        hueSpinBox: any
        tempSpinBox: any
        exposureSpinBox: any
        sharpenSpinBox: any
        blurSpinBox: any
        isMirrored: bool
        isMirroredVertical: bool
        rotationAngle: int
        is_loading_video: bool
        
        imageAdjContainer: QFrame
        imageAdjLayout: QVBoxLayout
        imageAdjTitle: CaptionLabel
        adjLabel: CaptionLabel
        imageAdjScrollArea: SingleDirectionScrollArea
        imageAdjScrollWidget: QWidget
        imageAdjInnerLayout: QVBoxLayout
        settingsContainer: QFrame
        globalSettingsContainer: QFrame
        subtitleContainer: QFrame
        mainSplitter: any
        is_full_screen: bool

        update_pixmap_from_cache: callable
        reset_adjustments: callable
        toggle_mirror: callable
        toggle_vertical_mirror: callable
        rotate_video_left: callable
        rotate_video_right: callable
        update_sidebar_fullscreen_state: callable

    def init_image_adj_sidebar(self):
        self.imageAdjContainer = QFrame()
        self.imageAdjContainer.setMinimumWidth(250)
        self.imageAdjContainer.setStyleSheet("background: #202020; border: none;")
        self.imageAdjLayout = QVBoxLayout(self.imageAdjContainer)
        self.imageAdjLayout.setContentsMargins(10, 10, 4, 10)
        self.imageAdjLayout.setSpacing(6)

        self.imageAdjTitle = CaptionLabel(tr('image_adjustments'))
        self.imageAdjTitle.setStyleSheet("font-size: 16px; font-weight: bold; color: white;")
        self.adjLabel = self.imageAdjTitle
        self.imageAdjLayout.addWidget(self.imageAdjTitle)

        self.imageAdjScrollArea = SingleDirectionScrollArea(self.imageAdjContainer, Qt.Orientation.Vertical)
        self.imageAdjScrollArea.setWidgetResizable(True)
        self.imageAdjScrollArea.setStyleSheet("background: transparent; border: none;")
        self.imageAdjScrollArea.setFrameShape(QFrame.Shape.NoFrame)
        self.imageAdjScrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.imageAdjScrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.imageAdjScrollWidget = QWidget()
        self.imageAdjScrollWidget.setStyleSheet("background: transparent;")
        self.imageAdjInnerLayout = QVBoxLayout(self.imageAdjScrollWidget)
        self.imageAdjInnerLayout.setContentsMargins(0, 0, 0, 0)
        self.imageAdjInnerLayout.setSpacing(6)

        self.imageAdjScrollArea.setWidget(self.imageAdjScrollWidget)
        self.imageAdjLayout.addWidget(self.imageAdjScrollArea)

        self._build_image_adj_section()

        self.imageAdjInnerLayout.addStretch(1)
        self.imageAdjContainer.hide()

    def toggle_image_adj(self):
        is_visible = self.imageAdjContainer.isVisible()
        if not is_visible:
            self.globalSettingsContainer.hide()
            self.settingsContainer.hide()
            if hasattr(self, 'subtitleContainer'):
                self.subtitleContainer.hide()
        
        self.imageAdjContainer.setVisible(not is_visible)
        if hasattr(self, 'update_sidebar_fullscreen_state'):
            self.update_sidebar_fullscreen_state()

        if not is_visible and not getattr(self, 'is_full_screen', False):
            sizes = self.mainSplitter.sizes()
            if len(sizes) > 2 and sizes[2] < 250:
                sizes[2] = 250
                self.mainSplitter.setSizes(sizes)

    def _build_image_adj_section(self):
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
        self.hueSlider,        self.hueLabel,        l5, self.hueSpinBox        = create_adj_slider(tr('hue'),       -180, 180, 0, 'tip_hue')
        self.tempSlider,       self.tempLabel,       l6, self.tempSpinBox       = create_adj_slider(tr('temperature'),-100, 100, 0, 'tip_temperature')
        self.exposureSlider,   self.exposureLabel,   l7, self.exposureSpinBox   = create_adj_slider(tr('exposure'),   -100, 100, 0, 'tip_exposure')
        self.sharpenSlider,    self.sharpenLabel,    l8, self.sharpenSpinBox    = create_adj_slider(tr('sharpen'),      0, 100, 0, 'tip_sharpen')
        self.blurSlider,       self.blurLabel,       l9, self.blurSpinBox       = create_adj_slider(tr('blur'),         0, 100, 0, 'tip_blur')

        for l in [l1, l2, l3, l4, l5, l6, l7, l8, l9]:
            self.imageAdjInnerLayout.addLayout(l)

        # Mirror, Rotate, and Invert buttons
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

        self.invertButton = PushButton(tr('invert'))
        self.invertButton.setToolTip(tr('tip_invert'))
        self.invertButton.setCheckable(True)
        self.invertButton.clicked.connect(self.update_pixmap_from_cache)

        for btn in [self.mirrorButton, self.mirrorVerticalButton, self.rotateLeftButton, self.rotateRightButton, self.invertButton]:
            btn.setStyleSheet(ACTION_BTN_STYLE)

        mirrorRow = QHBoxLayout()
        mirrorRow.setSpacing(6)
        mirrorRow.addWidget(self.mirrorButton)
        mirrorRow.addWidget(self.mirrorVerticalButton)
        self.imageAdjInnerLayout.addLayout(mirrorRow)

        rotateRow = QHBoxLayout()
        rotateRow.setSpacing(6)
        rotateRow.addWidget(self.rotateLeftButton)
        rotateRow.addWidget(self.rotateRightButton)
        self.imageAdjInnerLayout.addLayout(rotateRow)

        invertRow = QHBoxLayout()
        invertRow.setSpacing(6)
        invertRow.addWidget(self.invertButton)
        self.imageAdjInnerLayout.addLayout(invertRow)

        # Footer row with Alaphelyzet (Reset Image)
        footerLayout = QHBoxLayout()
        footerLayout.setSpacing(6)
        self.resetAdjButton = PushButton(tr('reset_image'))
        self.resetAdjButton.setToolTip(tr('tip_reset_image'))
        self.resetAdjButton.clicked.connect(self.reset_adjustments)
        self.resetAdjButton.setStyleSheet(ACTION_BTN_STYLE)
        footerLayout.addWidget(self.resetAdjButton)
        self.imageAdjInnerLayout.addLayout(footerLayout)

        hline3 = QFrame()
        hline3.setFrameShape(QFrame.Shape.HLine)
        hline3.setFrameShadow(QFrame.Shadow.Sunken)
        self.imageAdjInnerLayout.addWidget(hline3)
