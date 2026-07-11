from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout,
                              QWidget, QComboBox, QLabel)
from components import SafeSpinBox as QSpinBox, NoWheelSlider
from qfluentwidgets import (CaptionLabel, SwitchButton, PushButton,
                             SingleDirectionScrollArea)
from styles import (FLUENT_SLIDER_STYLE, ACTION_BTN_STYLE, get_color_tokens)
from translations import tr

class SubtitleSidebarUIMixin:
    def init_subtitle_sidebar(self):
        t = get_color_tokens(
            self.config.get('accent_color', '#00f2ff'),
            self.config.get('bg_color', '#202020'),
            self.config.get('inverse_text', False)
        )
        self.subtitleContainer = QFrame()
        self.subtitleContainer.setMinimumWidth(250)
        self.subtitleContainer.setStyleSheet(f"background: {t['bg']}; border: none;")
        self.subtitleLayout = QVBoxLayout(self.subtitleContainer)
        self.subtitleLayout.setContentsMargins(10, 10, 4, 10)
        self.subtitleLayout.setSpacing(6)

        self.subtitleTitle = CaptionLabel(tr('subtitles'))
        self.subtitleTitle.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {t['fg']};")
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
        self.trackLabel = CaptionLabel(tr('track'))
        trackLayout.addWidget(self.trackLabel)
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
        self.styleTitleLabel.setStyleSheet(f"font-weight: bold; color: {t['sec_fg']};")
        self.subtitleInnerLayout.addWidget(self.styleTitleLabel)

        # 3. Font Family
        fontLayout = QVBoxLayout()
        fontLayout.setSpacing(4)
        self.fontFamilyLabel = CaptionLabel(tr('font_family'))
        fontLayout.addWidget(self.fontFamilyLabel)
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
        self.fontSizeLabel = CaptionLabel(tr('font_size'))
        fontSizeHeader.addWidget(self.fontSizeLabel)
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

        self.subFontSizeSlider = NoWheelSlider(Qt.Orientation.Horizontal)
        self.subFontSizeSlider.setRange(12, 72)
        self.subFontSizeSlider.setValue(default_size)
        self.subFontSizeSlider.setStyleSheet(FLUENT_SLIDER_STYLE)
        
        self.subFontSizeSlider.valueChanged.connect(self.on_sub_size_slider_changed)
        self.subFontSizeSpin.valueChanged.connect(self.on_sub_size_spin_changed)
        
        fontSizeLayout.addWidget(self.subFontSizeSlider)
        self.subtitleInnerLayout.addLayout(fontSizeLayout)

        # 5-6. Text & Background Color
        colorsRow = QHBoxLayout()
        colorsRow.setSpacing(12)
        colorsInner = QVBoxLayout()
        colorsInner.setSpacing(4)
        self.textColorLabel = CaptionLabel(tr('text_color'))
        colorsInner.addWidget(self.textColorLabel)
        self.subTextColorBtn = PushButton()
        self.subTextColorBtn.setFixedSize(30, 30)
        self.subTextColorBtn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.subTextColorBtn.clicked.connect(self.choose_sub_text_color)
        colorsInner.addWidget(self.subTextColorBtn)
        colorsRow.addLayout(colorsInner)
        colorsInner2 = QVBoxLayout()
        colorsInner2.setSpacing(4)
        self.bgColorLabel = CaptionLabel(tr('bg_color_sub'))
        colorsInner2.addWidget(self.bgColorLabel)
        self.subBgColorBtn = PushButton()
        self.subBgColorBtn.setFixedSize(30, 30)
        self.subBgColorBtn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.subBgColorBtn.clicked.connect(self.choose_sub_bg_color)
        colorsInner2.addWidget(self.subBgColorBtn)
        colorsRow.addLayout(colorsInner2)
        colorsRow.addStretch(1)
        self.subtitleInnerLayout.addLayout(colorsRow)

        # 7. Background Opacity
        bgOpacityLayout = QVBoxLayout()
        bgOpacityLayout.setSpacing(4)
        bgOpacityHeader = QHBoxLayout()
        self.bgOpacityLabel = CaptionLabel(tr('bg_opacity'))
        bgOpacityHeader.addWidget(self.bgOpacityLabel)
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

        self.subBgOpacitySlider = NoWheelSlider(Qt.Orientation.Horizontal)
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
        self.outlineWidthLabel = CaptionLabel(tr('sub_outline_width'))
        outlineWidthHeader.addWidget(self.outlineWidthLabel)
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

        self.subOutlineWidthSlider = NoWheelSlider(Qt.Orientation.Horizontal)
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
        self.outlineColorLabel = CaptionLabel(tr('sub_outline_color'))
        outlineColorLayout.addWidget(self.outlineColorLabel)
        self.subOutlineColorBtn = PushButton()
        self.subOutlineColorBtn.setFixedSize(30, 30)
        self.subOutlineColorBtn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.subOutlineColorBtn.clicked.connect(self.choose_sub_outline_color)
        outlineColorLayout.addWidget(self.subOutlineColorBtn)
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
        self.shadowBlurLabel = CaptionLabel(tr('sub_shadow_blur'))
        shadowBlurHeader.addWidget(self.shadowBlurLabel)
        self.subShadowBlurSpin = QSpinBox()
        self.subShadowBlurSpin.setRange(0, 30)
        default_shadow_blur = self.config.get('subtitle_shadow_blur', 5)
        self.subShadowBlurSpin.setValue(default_shadow_blur)
        self.subShadowBlurSpin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.subShadowBlurSpin.setFixedWidth(80)
        shadowBlurHeader.addStretch(1)
        shadowBlurHeader.addWidget(self.subShadowBlurSpin)
        shadowBlurLayout.addLayout(shadowBlurHeader)

        self.subShadowBlurSlider = NoWheelSlider(Qt.Orientation.Horizontal)
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
        self.shadowDxLabel = CaptionLabel(tr('sub_shadow_dx'))
        shadowDxHeader.addWidget(self.shadowDxLabel)
        self.subShadowDxSpin = QSpinBox()
        self.subShadowDxSpin.setRange(-20, 20)
        default_shadow_dx = self.config.get('subtitle_shadow_dx', 2)
        self.subShadowDxSpin.setValue(default_shadow_dx)
        self.subShadowDxSpin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.subShadowDxSpin.setFixedWidth(80)
        shadowDxHeader.addStretch(1)
        shadowDxHeader.addWidget(self.subShadowDxSpin)
        shadowDxLayout.addLayout(shadowDxHeader)

        self.subShadowDxSlider = NoWheelSlider(Qt.Orientation.Horizontal)
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
        self.shadowDyLabel = CaptionLabel(tr('sub_shadow_dy'))
        shadowDyHeader.addWidget(self.shadowDyLabel)
        self.subShadowDySpin = QSpinBox()
        self.subShadowDySpin.setRange(-20, 20)
        default_shadow_dy = self.config.get('subtitle_shadow_dy', 2)
        self.subShadowDySpin.setValue(default_shadow_dy)
        self.subShadowDySpin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.subShadowDySpin.setFixedWidth(80)
        shadowDyHeader.addStretch(1)
        shadowDyHeader.addWidget(self.subShadowDySpin)
        shadowDyLayout.addLayout(shadowDyHeader)

        self.subShadowDySlider = NoWheelSlider(Qt.Orientation.Horizontal)
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
        self.shadowColorLabel = CaptionLabel(tr('sub_shadow_color'))
        shadowColorLayout.addWidget(self.shadowColorLabel)
        self.subShadowColorBtn = PushButton()
        self.subShadowColorBtn.setFixedSize(30, 30)
        self.subShadowColorBtn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.subShadowColorBtn.clicked.connect(self.choose_sub_shadow_color)
        shadowColorLayout.addWidget(self.subShadowColorBtn)
        self.subtitleInnerLayout.addLayout(shadowColorLayout)

        # --- SUBTITLE POSITION OFFSET SETTINGS ---
        hlinePos = QFrame()
        hlinePos.setFrameShape(QFrame.Shape.HLine)
        hlinePos.setFrameShadow(QFrame.Shadow.Sunken)
        self.subtitleInnerLayout.addWidget(hlinePos)
        
        self.positionTitleLabel = CaptionLabel(tr('subtitle_position'))
        self.positionTitleLabel.setStyleSheet(f"font-weight: bold; color: {t['sec_fg']};")
        self.subtitleInnerLayout.addWidget(self.positionTitleLabel)

        # Vertical Offset
        vOffsetLayout = QVBoxLayout()
        vOffsetLayout.setSpacing(4)
        vOffsetHeader = QHBoxLayout()
        self.vOffsetLabel = CaptionLabel(tr('sub_v_offset'))
        vOffsetHeader.addWidget(self.vOffsetLabel)
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
 
        self.subVOffsetSlider = NoWheelSlider(Qt.Orientation.Horizontal)
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
        self.hOffsetLabel = CaptionLabel(tr('sub_h_offset'))
        hOffsetHeader.addWidget(self.hOffsetLabel)
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
 
        self.subHOffsetSlider = NoWheelSlider(Qt.Orientation.Horizontal)
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
        self.timingTitleLabel.setStyleSheet(f"font-weight: bold; color: {t['sec_fg']};")
        self.subtitleInnerLayout.addWidget(self.timingTitleLabel)

        # 8. Subtitle Offset (ms)
        offsetLayout = QVBoxLayout()
        offsetLayout.setSpacing(4)
        offsetHeader = QHBoxLayout()
        self.subtitleOffsetLabel = CaptionLabel(tr('subtitle_offset'))
        offsetHeader.addWidget(self.subtitleOffsetLabel)
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

        self.subOffsetSlider = NoWheelSlider(Qt.Orientation.Horizontal)
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
