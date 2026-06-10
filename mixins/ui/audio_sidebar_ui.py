from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QSlider,
                               QWidget, QComboBox)
from qfluentwidgets import (CaptionLabel, SwitchButton, PushButton,
                             SingleDirectionScrollArea, BodyLabel)
from styles import ACTION_BTN_STYLE
from translations import tr

class AudioSidebarUIMixin:
    def init_audio_sidebar(self):
        self.audioContainer = QFrame()
        self.audioContainer.setMinimumWidth(250)
        self.audioContainer.setStyleSheet("background: #202020; border: none;")
        self.audioLayout = QVBoxLayout(self.audioContainer)
        self.audioLayout.setContentsMargins(10, 10, 4, 10)
        self.audioLayout.setSpacing(6)

        self.audioTitle = CaptionLabel(tr('audio_settings'))
        self.audioTitle.setStyleSheet("font-size: 16px; font-weight: bold; color: white;")
        self.audioLayout.addWidget(self.audioTitle)

        self.audioScrollArea = SingleDirectionScrollArea(self.audioContainer, Qt.Orientation.Vertical)
        self.audioScrollArea.setWidgetResizable(True)
        self.audioScrollArea.setStyleSheet("background: transparent; border: none;")
        self.audioScrollArea.setFrameShape(QFrame.Shape.NoFrame)
        self.audioScrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.audioScrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.audioScrollWidget = QWidget()
        self.audioScrollWidget.setStyleSheet("background: transparent;")
        self.audioInnerLayout = QVBoxLayout(self.audioScrollWidget)
        self.audioInnerLayout.setContentsMargins(0, 0, 0, 0)
        self.audioInnerLayout.setSpacing(10)

        self.audioScrollArea.setWidget(self.audioScrollWidget)
        self.audioLayout.addWidget(self.audioScrollArea)

        # 1. Audio Track Selector Section
        trackLayout = QVBoxLayout()
        trackLayout.setSpacing(4)
        trackLayout.addWidget(CaptionLabel(tr('audio_track_label')))
        
        self.audioTrackCombo = QComboBox()
        self.audioTrackCombo.addItem(tr('default'), 0)
        self.audioTrackCombo.currentIndexChanged.connect(self.on_audio_track_changed)
        trackLayout.addWidget(self.audioTrackCombo)
        self.audioInnerLayout.addLayout(trackLayout)

        # Divider
        hline1 = QFrame()
        hline1.setFrameShape(QFrame.Shape.HLine)
        hline1.setFrameShadow(QFrame.Shadow.Sunken)
        self.audioInnerLayout.addWidget(hline1)

        # 2. Equalizer Header
        eqHeaderLayout = QHBoxLayout()
        self.audioEqLabel = CaptionLabel(tr('audio_eq_enable'))
        self.audioEqLabel.setStyleSheet("font-weight: bold; color: #aaaaaa;")
        self.audioEqToggle = SwitchButton()
        self.audioEqToggle.setChecked(self.config.get('audio_eq_enabled', False))
        self.audioEqToggle.setOnText(tr('on'))
        self.audioEqToggle.setOffText(tr('off'))
        self.audioEqToggle.checkedChanged.connect(self.on_audio_eq_toggle_changed)
        
        eqHeaderLayout.addWidget(self.audioEqLabel)
        eqHeaderLayout.addStretch(1)
        eqHeaderLayout.addWidget(self.audioEqToggle)
        self.audioInnerLayout.addLayout(eqHeaderLayout)

        # 3. Preset Selector Section
        presetLayout = QVBoxLayout()
        presetLayout.setSpacing(4)
        presetLayout.addWidget(CaptionLabel(tr('audio_eq_preset')))
        
        self.audioEqPresetCombo = QComboBox()
        presets_list = [
            ('preset_flat', 'Flat'),
            ('preset_bass_boost', 'Bass Boost'),
            ('preset_treble_boost', 'Treble Boost'),
            ('preset_vocal', 'Vocal'),
            ('preset_pop', 'Pop'),
            ('preset_rock', 'Rock'),
            ('preset_jazz', 'Jazz'),
            ('preset_classical', 'Classical')
        ]
        for key, val in presets_list:
            self.audioEqPresetCombo.addItem(tr(key), val)
        
        default_preset = self.config.get('audio_eq_preset', 'Flat')
        preset_idx = self.audioEqPresetCombo.findData(default_preset)
        if preset_idx != -1:
            self.audioEqPresetCombo.setCurrentIndex(preset_idx)
        self.audioEqPresetCombo.currentIndexChanged.connect(self.on_audio_eq_preset_changed)
        presetLayout.addWidget(self.audioEqPresetCombo)
        self.audioInnerLayout.addLayout(presetLayout)

        # 4. Equalizer Graphic Sliders Section
        self.slidersWidget = QWidget()
        slidersLayout = QHBoxLayout(self.slidersWidget)
        slidersLayout.setContentsMargins(0, 5, 0, 5)
        slidersLayout.setSpacing(4)

        # Bands definitions: (Label key, frequency)
        self.eq_bands = [
            ("31", 31), ("62", 62), ("125", 125), ("250", 250), ("500", 500),
            ("1k", 1000), ("2k", 2000), ("4k", 4000), ("8k", 8000), ("16k", 16000)
        ]
        
        accent_color = self.config.get('accent_color', '#00f2ff')
        
        vertical_slider_style = f"""
        QSlider::groove:vertical {{
            border: none;
            width: 4px;
            background: #444;
            border-radius: 2px;
        }}
        QSlider::handle:vertical {{
            background: #ffffff;
            width: 14px;
            height: 10px;
            margin: 0 -5px;
            border-radius: 2px;
        }}
        QSlider::sub-page:vertical {{
            background: {accent_color};
            border-radius: 2px;
        }}
        """

        self.eq_sliders = []
        self.eq_labels = []
        
        gains = self.config.get('audio_eq_gains', [0] * 10)

        for i, (band_lbl, freq) in enumerate(self.eq_bands):
            band_layout = QVBoxLayout()
            band_layout.setContentsMargins(0, 0, 0, 0)
            band_layout.setSpacing(2)
            
            # Frequency Label
            freq_label = BodyLabel(band_lbl)
            freq_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            freq_label.setStyleSheet("font-size: 12px; color: #888888; font-weight: bold;")
            band_layout.addWidget(freq_label)

            # Vertical Slider
            slider = QSlider(Qt.Orientation.Vertical)
            slider.setRange(-12, 12)
            slider.setValue(gains[i])
            slider.setFixedHeight(120)
            slider.setStyleSheet(vertical_slider_style)
            # Custom attribute to keep track of band index
            slider.setProperty("band_idx", i)
            slider.valueChanged.connect(self.on_eq_slider_changed)
            
            band_layout.addWidget(slider, 0, Qt.AlignmentFlag.AlignCenter)
            self.eq_sliders.append(slider)

            # Gain Value Label
            gain_val = gains[i]
            gain_label = BodyLabel(f"{gain_val:+d}" if gain_val != 0 else "0")
            gain_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            gain_label.setStyleSheet("font-size: 12px; color: #cccccc;")
            band_layout.addWidget(gain_label)
            self.eq_labels.append(gain_label)

            slidersLayout.addLayout(band_layout)

        self.audioInnerLayout.addWidget(self.slidersWidget)

        # 5. Reset EQ Button
        self.resetEqBtn = PushButton(tr('reset_eq'))
        self.resetEqBtn.clicked.connect(self.reset_equalizer)
        self.resetEqBtn.setStyleSheet(ACTION_BTN_STYLE)
        self.audioInnerLayout.addWidget(self.resetEqBtn)

        self.audioInnerLayout.addStretch(1)
        self.audioContainer.hide()

    def update_audio_presets_ui(self):
        preset = self.config.get('audio_eq_preset', 'Flat')
        self.audioEqPresetCombo.blockSignals(True)
        idx = self.audioEqPresetCombo.findData(preset)
        if idx != -1:
            self.audioEqPresetCombo.setCurrentIndex(idx)
        self.audioEqPresetCombo.blockSignals(False)
