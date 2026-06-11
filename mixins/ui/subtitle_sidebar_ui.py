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
        colors = [
            ('color_white', 'White'),
            ('color_yellow', 'Yellow'),
            ('color_cyan', 'Cyan'),
            ('color_green', 'Green'),
            ('color_magenta', 'Magenta'),
            ('color_red', 'Red')
        ]
        for key, val in colors:
            self.subTextColorCombo.addItem(tr(key), val)
        
        default_text_color = self.config.get('subtitle_text_color', 'White')
        idx = self.subTextColorCombo.findData(default_text_color)
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
        bg_colors = [
            ('color_black', 'Black'),
            ('color_dark_grey', 'Dark Grey'),
            ('color_navy_blue', 'Navy Blue'),
            ('color_none', 'None')
        ]
        for key, val in bg_colors:
            self.subBgColorCombo.addItem(tr(key), val)
        
        default_bg_color = self.config.get('subtitle_bg_color', 'Black')
        idx = self.subBgColorCombo.findData(default_bg_color)
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

        # --- SUBTITLE OUTLINE SETTINGS ---
        outlineHeader = QHBoxLayout()
        self.outlineEnableLabel = CaptionLabel(tr('sub_outline_enabled'))
        self.subOutlineToggle = SwitchButton()
        self.subOutlineToggle.setChecked(self.config.get('subtitle_outline_enabled', False))
        self.subOutlineToggle.checkedChanged.connect(self.on_sub_outline_changed)
        outlineHeader.addWidget(self.outlineEnableLabel)
        outlineHeader.addStretch(1)
        outlineHeader.addWidget(self.subOutlineToggle)
        self.subtitleInnerLayout.addLayout(outlineHeader)

        # Outline thickness
        outlineWidthLayout = QVBoxLayout()
        outlineWidthLayout.setSpacing(4)
        outlineWidthHeader = QHBoxLayout()
        outlineWidthHeader.addWidget(CaptionLabel(tr('sub_outline_width')))
        self.subOutlineWidthSpin = QSpinBox()
        self.subOutlineWidthSpin.setRange(1, 8)
        default_outline_w = self.config.get('subtitle_outline_width', 2)
        self.subOutlineWidthSpin.setValue(default_outline_w)
        self.subOutlineWidthSpin.setSuffix(" px")
        self.subOutlineWidthSpin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.subOutlineWidthSpin.setFixedWidth(80)
        outlineWidthHeader.addStretch(1)
        outlineWidthHeader.addWidget(self.subOutlineWidthSpin)
        outlineWidthLayout.addLayout(outlineWidthHeader)

        self.subOutlineWidthSlider = QSlider(Qt.Orientation.Horizontal)
        self.subOutlineWidthSlider.setRange(1, 8)
        self.subOutlineWidthSlider.setValue(default_outline_w)
        self.subOutlineWidthSlider.setStyleSheet(FLUENT_SLIDER_STYLE)
        
        self.subOutlineWidthSlider.valueChanged.connect(self.on_sub_outline_width_changed)
        self.subOutlineWidthSpin.valueChanged.connect(self.on_sub_outline_width_changed)
        
        # Link slider and spinbox
        self.subOutlineWidthSlider.valueChanged.connect(self.subOutlineWidthSpin.setValue)
        self.subOutlineWidthSpin.valueChanged.connect(self.subOutlineWidthSlider.setValue)
        
        outlineWidthLayout.addWidget(self.subOutlineWidthSlider)
        self.subtitleInnerLayout.addLayout(outlineWidthLayout)

        # Outline Color
        outlineColorLayout = QVBoxLayout()
        outlineColorLayout.setSpacing(4)
        outlineColorLayout.addWidget(CaptionLabel(tr('sub_outline_color')))
        self.subOutlineColorCombo = QComboBox()
        sub_colors = [
            ('color_black', 'Black'),
            ('color_dark_grey', 'Dark Grey'),
            ('color_white', 'White'),
            ('color_yellow', 'Yellow'),
            ('color_cyan', 'Cyan'),
            ('color_green', 'Green'),
            ('color_magenta', 'Magenta'),
            ('color_red', 'Red')
        ]
        for key, val in sub_colors:
            self.subOutlineColorCombo.addItem(tr(key), val)
        default_outline_color = self.config.get('subtitle_outline_color', 'Black')
        idx = self.subOutlineColorCombo.findData(default_outline_color)
        if idx != -1:
            self.subOutlineColorCombo.setCurrentIndex(idx)
        self.subOutlineColorCombo.currentIndexChanged.connect(self.on_sub_outline_color_changed)
        outlineColorLayout.addWidget(self.subOutlineColorCombo)
        self.subtitleInnerLayout.addLayout(outlineColorLayout)

        # --- SUBTITLE DROP SHADOW SETTINGS ---
        shadowHeader = QHBoxLayout()
        self.shadowEnableLabel = CaptionLabel(tr('sub_shadow_enabled'))
        self.subShadowToggle = SwitchButton()
        self.subShadowToggle.setChecked(self.config.get('subtitle_shadow_enabled', False))
        self.subShadowToggle.checkedChanged.connect(self.on_sub_shadow_changed)
        shadowHeader.addWidget(self.shadowEnableLabel)
        shadowHeader.addStretch(1)
        shadowHeader.addWidget(self.subShadowToggle)
        self.subtitleInnerLayout.addLayout(shadowHeader)

        # Shadow Blur
        shadowBlurLayout = QVBoxLayout()
        shadowBlurLayout.setSpacing(4)
        shadowBlurHeader = QHBoxLayout()
        shadowBlurHeader.addWidget(CaptionLabel(tr('sub_shadow_blur')))
        self.subShadowBlurSpin = QSpinBox()
        self.subShadowBlurSpin.setRange(0, 30)
        default_shadow_blur = self.config.get('subtitle_shadow_blur', 5)
        self.subShadowBlurSpin.setValue(default_shadow_blur)
        self.subShadowBlurSpin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.subShadowBlurSpin.setFixedWidth(80)
        shadowBlurHeader.addStretch(1)
        shadowBlurHeader.addWidget(self.subShadowBlurSpin)
        shadowBlurLayout.addLayout(shadowBlurHeader)

        self.subShadowBlurSlider = QSlider(Qt.Orientation.Horizontal)
        self.subShadowBlurSlider.setRange(0, 30)
        self.subShadowBlurSlider.setValue(default_shadow_blur)
        self.subShadowBlurSlider.setStyleSheet(FLUENT_SLIDER_STYLE)
        
        self.subShadowBlurSlider.valueChanged.connect(self.on_sub_shadow_blur_changed)
        self.subShadowBlurSpin.valueChanged.connect(self.on_sub_shadow_blur_changed)
        
        # Link slider and spinbox
        self.subShadowBlurSlider.valueChanged.connect(self.subShadowBlurSpin.setValue)
        self.subShadowBlurSpin.valueChanged.connect(self.subShadowBlurSlider.setValue)
        
        shadowBlurLayout.addWidget(self.subShadowBlurSlider)
        self.subtitleInnerLayout.addLayout(shadowBlurLayout)

        # Shadow Offset X
        shadowDxLayout = QVBoxLayout()
        shadowDxLayout.setSpacing(4)
        shadowDxHeader = QHBoxLayout()
        shadowDxHeader.addWidget(CaptionLabel(tr('sub_shadow_dx')))
        self.subShadowDxSpin = QSpinBox()
        self.subShadowDxSpin.setRange(-20, 20)
        default_shadow_dx = self.config.get('subtitle_shadow_dx', 2)
        self.subShadowDxSpin.setValue(default_shadow_dx)
        self.subShadowDxSpin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.subShadowDxSpin.setFixedWidth(80)
        shadowDxHeader.addStretch(1)
        shadowDxHeader.addWidget(self.subShadowDxSpin)
        shadowDxLayout.addLayout(shadowDxHeader)

        self.subShadowDxSlider = QSlider(Qt.Orientation.Horizontal)
        self.subShadowDxSlider.setRange(-20, 20)
        self.subShadowDxSlider.setValue(default_shadow_dx)
        self.subShadowDxSlider.setStyleSheet(FLUENT_SLIDER_STYLE)
        
        self.subShadowDxSlider.valueChanged.connect(self.on_sub_shadow_dx_changed)
        self.subShadowDxSpin.valueChanged.connect(self.on_sub_shadow_dx_changed)
        
        # Link slider and spinbox
        self.subShadowDxSlider.valueChanged.connect(self.subShadowDxSpin.setValue)
        self.subShadowDxSpin.valueChanged.connect(self.subShadowDxSlider.setValue)
        
        shadowDxLayout.addWidget(self.subShadowDxSlider)
        self.subtitleInnerLayout.addLayout(shadowDxLayout)

        # Shadow Offset Y
        shadowDyLayout = QVBoxLayout()
        shadowDyLayout.setSpacing(4)
        shadowDyHeader = QHBoxLayout()
        shadowDyHeader.addWidget(CaptionLabel(tr('sub_shadow_dy')))
        self.subShadowDySpin = QSpinBox()
        self.subShadowDySpin.setRange(-20, 20)
        default_shadow_dy = self.config.get('subtitle_shadow_dy', 2)
        self.subShadowDySpin.setValue(default_shadow_dy)
        self.subShadowDySpin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.subShadowDySpin.setFixedWidth(80)
        shadowDyHeader.addStretch(1)
        shadowDyHeader.addWidget(self.subShadowDySpin)
        shadowDyLayout.addLayout(shadowDyHeader)

        self.subShadowDySlider = QSlider(Qt.Orientation.Horizontal)
        self.subShadowDySlider.setRange(-20, 20)
        self.subShadowDySlider.setValue(default_shadow_dy)
        self.subShadowDySlider.setStyleSheet(FLUENT_SLIDER_STYLE)
        
        self.subShadowDySlider.valueChanged.connect(self.on_sub_shadow_dy_changed)
        self.subShadowDySpin.valueChanged.connect(self.on_sub_shadow_dy_changed)
        
        # Link slider and spinbox
        self.subShadowDySlider.valueChanged.connect(self.subShadowDySpin.setValue)
        self.subShadowDySpin.valueChanged.connect(self.subShadowDySlider.setValue)
        
        shadowDyLayout.addWidget(self.subShadowDySlider)
        self.subtitleInnerLayout.addLayout(shadowDyLayout)

        # Shadow Color
        shadowColorLayout = QVBoxLayout()
        shadowColorLayout.setSpacing(4)
        shadowColorLayout.addWidget(CaptionLabel(tr('sub_shadow_color')))
        self.subShadowColorCombo = QComboBox()
        for key, val in sub_colors:
            self.subShadowColorCombo.addItem(tr(key), val)
        default_shadow_color = self.config.get('subtitle_shadow_color', 'Black')
        idx = self.subShadowColorCombo.findData(default_shadow_color)
        if idx != -1:
            self.subShadowColorCombo.setCurrentIndex(idx)
        self.subShadowColorCombo.currentIndexChanged.connect(self.on_sub_shadow_color_changed)
        shadowColorLayout.addWidget(self.subShadowColorCombo)
        self.subtitleInnerLayout.addLayout(shadowColorLayout)

        # --- SUBTITLE POSITION OFFSET SETTINGS ---
        hlinePos = QFrame()
        hlinePos.setFrameShape(QFrame.Shape.HLine)
        hlinePos.setFrameShadow(QFrame.Shadow.Sunken)
        self.subtitleInnerLayout.addWidget(hlinePos)
        
        self.positionTitleLabel = CaptionLabel(tr('subtitle_position'))
        self.positionTitleLabel.setStyleSheet("font-weight: bold; color: #aaaaaa;")
        self.subtitleInnerLayout.addWidget(self.positionTitleLabel)

        # Vertical Offset
        vOffsetLayout = QVBoxLayout()
        vOffsetLayout.setSpacing(4)
        vOffsetHeader = QHBoxLayout()
        vOffsetHeader.addWidget(CaptionLabel(tr('sub_v_offset')))
        self.subVOffsetSpin = QSpinBox()
        self.subVOffsetSpin.setRange(0, 100)
        default_v_offset = self.config.get('subtitle_v_offset', 5)
        self.subVOffsetSpin.setValue(default_v_offset)
        self.subVOffsetSpin.setSuffix(" %")
        self.subVOffsetSpin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.subVOffsetSpin.setFixedWidth(80)
        vOffsetHeader.addStretch(1)
        vOffsetHeader.addWidget(self.subVOffsetSpin)
        vOffsetLayout.addLayout(vOffsetHeader)
 
        self.subVOffsetSlider = QSlider(Qt.Orientation.Horizontal)
        self.subVOffsetSlider.setRange(0, 100)
        self.subVOffsetSlider.setValue(default_v_offset)
        self.subVOffsetSlider.setStyleSheet(FLUENT_SLIDER_STYLE)
        
        self.subVOffsetSlider.valueChanged.connect(self.on_sub_v_offset_changed)
        self.subVOffsetSpin.valueChanged.connect(self.on_sub_v_offset_changed)
        
        # Link slider and spinbox
        self.subVOffsetSlider.valueChanged.connect(self.subVOffsetSpin.setValue)
        self.subVOffsetSpin.valueChanged.connect(self.subVOffsetSlider.setValue)
        
        vOffsetLayout.addWidget(self.subVOffsetSlider)
        self.subtitleInnerLayout.addLayout(vOffsetLayout)
 
        # Horizontal Offset
        hOffsetLayout = QVBoxLayout()
        hOffsetLayout.setSpacing(4)
        hOffsetHeader = QHBoxLayout()
        hOffsetHeader.addWidget(CaptionLabel(tr('sub_h_offset')))
        self.subHOffsetSpin = QSpinBox()
        self.subHOffsetSpin.setRange(-50, 50)
        default_h_offset = self.config.get('subtitle_h_offset', 0)
        self.subHOffsetSpin.setValue(default_h_offset)
        self.subHOffsetSpin.setSuffix(" %")
        self.subHOffsetSpin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.subHOffsetSpin.setFixedWidth(80)
        hOffsetHeader.addStretch(1)
        hOffsetHeader.addWidget(self.subHOffsetSpin)
        hOffsetLayout.addLayout(hOffsetHeader)
 
        self.subHOffsetSlider = QSlider(Qt.Orientation.Horizontal)
        self.subHOffsetSlider.setRange(-50, 50)
        self.subHOffsetSlider.setValue(default_h_offset)
        self.subHOffsetSlider.setStyleSheet(FLUENT_SLIDER_STYLE)
        
        self.subHOffsetSlider.valueChanged.connect(self.on_sub_h_offset_changed)
        self.subHOffsetSpin.valueChanged.connect(self.on_sub_h_offset_changed)
        
        # Link slider and spinbox
        self.subHOffsetSlider.valueChanged.connect(self.subHOffsetSpin.setValue)
        self.subHOffsetSpin.valueChanged.connect(self.subHOffsetSlider.setValue)
        
        hOffsetLayout.addWidget(self.subHOffsetSlider)
        self.subtitleInnerLayout.addLayout(hOffsetLayout)

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
