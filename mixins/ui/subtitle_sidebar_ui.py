from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QSlider,
                              QWidget, QComboBox, QSpinBox)
from qfluentwidgets import (CaptionLabel, SwitchButton, PushButton,
                             SingleDirectionScrollArea)
from styles import (FLUENT_SLIDER_STYLE, ACTION_BTN_STYLE)
from translations import tr

class SubtitleSidebarUIMixin:
    def init_subtitle_sidebar(self):
        self.subtitleContainer = QFrame()
        self.subtitleContainer.setMinimumWidth(250)
        self.subtitleContainer.setStyleSheet("background: #202020; border: none;")
        self.subtitleLayout = QVBoxLayout(self.subtitleContainer)
        self.subtitleLayout.setContentsMargins(10, 10, 4, 10)
        self.subtitleLayout.setSpacing(6)

        self.subtitleTitle = CaptionLabel(tr('subtitles'))
        self.subtitleTitle.setStyleSheet("font-size: 16px; font-weight: bold; color: white;")
        self.subtitleLayout.addWidget(self.subtitleTitle)

        self.subtitleScrollArea = SingleDirectionScrollArea(self.subtitleContainer, Qt.Orientation.Vertical)
        self.subtitleScrollArea.setWidgetResizable(True)
        self.subtitleScrollArea.setStyleSheet("background: transparent; border: none;")
        self.subtitleScrollArea.setFrameShape(QFrame.Shape.NoFrame)
        self.subtitleScrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.subtitleScrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.subtitleScrollWidget = QWidget()
        self.subtitleScrollWidget.setStyleSheet("background: transparent;")
        self.subtitleInnerLayout = QVBoxLayout(self.subtitleScrollWidget)
        self.subtitleInnerLayout.setContentsMargins(0, 0, 0, 0)
        self.subtitleInnerLayout.setSpacing(10)

        self.subtitleScrollArea.setWidget(self.subtitleScrollWidget)
        self.subtitleLayout.addWidget(self.subtitleScrollArea)

        # 1. Enable / Disable subtitles
        enableLayout = QHBoxLayout()
        self.subEnableLabel = CaptionLabel(tr('enable_subtitles'))
        self.subEnableToggle = SwitchButton()
        self.subEnableToggle.setChecked(self.config.get('enable_subtitles', True))
        self.subEnableToggle.setOnText(tr('on'))
        self.subEnableToggle.setOffText(tr('off'))
        self.subEnableToggle.setToolTip(tr('tip_enable_subtitles'))
        self.subEnableToggle.checkedChanged.connect(self.on_enable_subtitles_changed)
        enableLayout.addWidget(self.subEnableLabel)
        enableLayout.addStretch(1)
        enableLayout.addWidget(self.subEnableToggle)
        self.subtitleInnerLayout.addLayout(enableLayout)

        # 2. Load subtitle file
        self.loadSubBtn = PushButton(tr('load_subtitle_file'))
        self.loadSubBtn.setToolTip(tr('tip_load_subtitle'))
        self.loadSubBtn.clicked.connect(self.browse_subtitle_file)
        self.loadSubBtn.setStyleSheet(ACTION_BTN_STYLE)
        self.subtitleInnerLayout.addWidget(self.loadSubBtn)

        # Subtitle Track Selection (embedded tracks)
        trackLayout = QVBoxLayout()
        trackLayout.setSpacing(4)
        trackLayout.addWidget(CaptionLabel(tr('track')))
        self.subTrackCombo = QComboBox()
        self.subTrackCombo.addItem(tr('off'), -1)
        self.subTrackCombo.currentIndexChanged.connect(self.on_sub_track_changed)
        trackLayout.addWidget(self.subTrackCombo)
        self.subtitleInnerLayout.addLayout(trackLayout)

        # Divider
        hline1 = QFrame()
        hline1.setFrameShape(QFrame.Shape.HLine)
        hline1.setFrameShadow(QFrame.Shadow.Sunken)
        self.subtitleInnerLayout.addWidget(hline1)

        # Style Section Header
        self.styleTitleLabel = CaptionLabel(tr('drawing_settings')) # reuse translations or define general style
        self.styleTitleLabel.setStyleSheet("font-weight: bold; color: #aaaaaa;")
        self.subtitleInnerLayout.addWidget(self.styleTitleLabel)

        # 3. Font Family
        fontLayout = QVBoxLayout()
        fontLayout.setSpacing(4)
        fontLayout.addWidget(CaptionLabel(tr('font_family')))
        self.subFontCombo = QComboBox()
        self.subFontCombo.addItems(['Segoe UI', 'Inter', 'Roboto', 'Arial', 'Courier New', 'Times New Roman'])
        default_font = self.config.get('subtitle_font_family', 'Segoe UI')
        idx = self.subFontCombo.findText(default_font)
        if idx != -1:
            self.subFontCombo.setCurrentIndex(idx)
        self.subFontCombo.currentIndexChanged.connect(self.on_sub_font_changed)
        fontLayout.addWidget(self.subFontCombo)
        self.subtitleInnerLayout.addLayout(fontLayout)

        # 4. Font Size (px)
        fontSizeLayout = QVBoxLayout()
        fontSizeLayout.setSpacing(4)
        fontSizeHeader = QHBoxLayout()
        fontSizeHeader.addWidget(CaptionLabel(tr('font_size')))
        self.subFontSizeSpin = QSpinBox()
        self.subFontSizeSpin.setRange(12, 72)
        default_size = self.config.get('subtitle_font_size', 24)
        self.subFontSizeSpin.setValue(default_size)
        self.subFontSizeSpin.setSuffix(" px")
        self.subFontSizeSpin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.subFontSizeSpin.setFixedWidth(80)
        fontSizeHeader.addStretch(1)
        fontSizeHeader.addWidget(self.subFontSizeSpin)
        fontSizeLayout.addLayout(fontSizeHeader)

        self.subFontSizeSlider = QSlider(Qt.Orientation.Horizontal)
        self.subFontSizeSlider.setRange(12, 72)
        self.subFontSizeSlider.setValue(default_size)
        self.subFontSizeSlider.setStyleSheet(FLUENT_SLIDER_STYLE)
        
        self.subFontSizeSlider.valueChanged.connect(self.on_sub_size_slider_changed)
        self.subFontSizeSpin.valueChanged.connect(self.on_sub_size_spin_changed)
        
        fontSizeLayout.addWidget(self.subFontSizeSlider)
        self.subtitleInnerLayout.addLayout(fontSizeLayout)

        # 5. Text Color
        textColorLayout = QVBoxLayout()
        textColorLayout.setSpacing(4)
        textColorLayout.addWidget(CaptionLabel(tr('text_color')))
        self.subTextColorCombo = QComboBox()
        self.subTextColorCombo.addItems(['White', 'Yellow', 'Cyan', 'Green', 'Magenta', 'Red'])
        default_text_color = self.config.get('subtitle_text_color', 'White')
        idx = self.subTextColorCombo.findText(default_text_color)
        if idx != -1:
            self.subTextColorCombo.setCurrentIndex(idx)
        self.subTextColorCombo.currentIndexChanged.connect(self.on_sub_text_color_changed)
        textColorLayout.addWidget(self.subTextColorCombo)
        self.subtitleInnerLayout.addLayout(textColorLayout)

        # 6. Background Color
        bgColorLayout = QVBoxLayout()
        bgColorLayout.setSpacing(4)
        bgColorLayout.addWidget(CaptionLabel(tr('bg_color_sub')))
        self.subBgColorCombo = QComboBox()
        self.subBgColorCombo.addItems(['Black', 'Dark Grey', 'Navy Blue', 'None'])
        default_bg_color = self.config.get('subtitle_bg_color', 'Black')
        idx = self.subBgColorCombo.findText(default_bg_color)
        if idx != -1:
            self.subBgColorCombo.setCurrentIndex(idx)
        self.subBgColorCombo.currentIndexChanged.connect(self.on_sub_bg_color_changed)
        bgColorLayout.addWidget(self.subBgColorCombo)
        self.subtitleInnerLayout.addLayout(bgColorLayout)

        # 7. Background Opacity
        bgOpacityLayout = QVBoxLayout()
        bgOpacityLayout.setSpacing(4)
        bgOpacityHeader = QHBoxLayout()
        bgOpacityHeader.addWidget(CaptionLabel(tr('bg_opacity')))
        self.subBgOpacitySpin = QSpinBox()
        self.subBgOpacitySpin.setRange(0, 100)
        default_opacity = self.config.get('subtitle_bg_opacity', 60)
        self.subBgOpacitySpin.setValue(default_opacity)
        self.subBgOpacitySpin.setSuffix("%")
        self.subBgOpacitySpin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.subBgOpacitySpin.setFixedWidth(80)
        bgOpacityHeader.addStretch(1)
        bgOpacityHeader.addWidget(self.subBgOpacitySpin)
        bgOpacityLayout.addLayout(bgOpacityHeader)

        self.subBgOpacitySlider = QSlider(Qt.Orientation.Horizontal)
        self.subBgOpacitySlider.setRange(0, 100)
        self.subBgOpacitySlider.setValue(default_opacity)
        self.subBgOpacitySlider.setStyleSheet(FLUENT_SLIDER_STYLE)
        
        self.subBgOpacitySlider.valueChanged.connect(self.on_sub_opacity_slider_changed)
        self.subBgOpacitySpin.valueChanged.connect(self.on_sub_opacity_spin_changed)
        
        bgOpacityLayout.addWidget(self.subBgOpacitySlider)
        self.subtitleInnerLayout.addLayout(bgOpacityLayout)

        # Divider
        hline2 = QFrame()
        hline2.setFrameShape(QFrame.Shape.HLine)
        hline2.setFrameShadow(QFrame.Shadow.Sunken)
        self.subtitleInnerLayout.addWidget(hline2)

        # Timing Section Header
        self.timingTitleLabel = CaptionLabel(tr('sync_title'))
        self.timingTitleLabel.setStyleSheet("font-weight: bold; color: #aaaaaa;")
        self.subtitleInnerLayout.addWidget(self.timingTitleLabel)

        # 8. Subtitle Offset (ms)
        offsetLayout = QVBoxLayout()
        offsetLayout.setSpacing(4)
        offsetHeader = QHBoxLayout()
        offsetHeader.addWidget(CaptionLabel(tr('subtitle_offset')))
        self.subOffsetSpin = QSpinBox()
        self.subOffsetSpin.setRange(-10000, 10000)
        self.subOffsetSpin.setSingleStep(50)
        default_offset = self.config.get('subtitle_offset', 0)
        self.subOffsetSpin.setValue(default_offset)
        self.subOffsetSpin.setSuffix(" ms")
        self.subOffsetSpin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.subOffsetSpin.setFixedWidth(100)
        offsetHeader.addStretch(1)
        offsetHeader.addWidget(self.subOffsetSpin)
        offsetLayout.addLayout(offsetHeader)

        self.subOffsetSlider = QSlider(Qt.Orientation.Horizontal)
        self.subOffsetSlider.setRange(-10000, 10000)
        self.subOffsetSlider.setSingleStep(50)
        self.subOffsetSlider.setPageStep(500)
        self.subOffsetSlider.setValue(default_offset)
        self.subOffsetSlider.setStyleSheet(FLUENT_SLIDER_STYLE)
        
        self.subOffsetSlider.valueChanged.connect(self.on_sub_offset_slider_changed)
        self.subOffsetSpin.valueChanged.connect(self.on_sub_offset_spin_changed)
        
        offsetLayout.addWidget(self.subOffsetSlider)
        self.subtitleInnerLayout.addLayout(offsetLayout)

        self.subtitleInnerLayout.addStretch(1)
        self.subtitleContainer.hide()
