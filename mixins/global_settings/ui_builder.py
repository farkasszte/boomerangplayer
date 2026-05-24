from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QWidget, QGridLayout, QSlider
from qfluentwidgets import CaptionLabel, PushButton, SwitchButton, SingleDirectionScrollArea, BodyLabel
from components import ShortcutButton
from translations import tr
from styles import ACTION_BTN_STYLE

class GlobalSettingsUiBuilderMixin:
    def init_global_settings_sidebar(self):
        self.globalSettingsContainer = QFrame()
        self.globalSettingsContainer.setMinimumWidth(250)
        self.globalSettingsContainer.setStyleSheet("background: #202020; border: none;")
        self.globalSettingsLayout = QVBoxLayout(self.globalSettingsContainer)
        self.globalSettingsLayout.setContentsMargins(10, 10, 4, 10)
        self.globalSettingsLayout.setSpacing(6)

        self.pending_accent_color = self.config.get('accent_color', '#00f2ff')
        self.pending_bg_color = self.config.get('bg_color', '#202020')
        self.pending_panel_opacity = self.config.get('panel_opacity', 100)

        self.globalSettingsTitle = CaptionLabel(tr('settings'))
        self.globalSettingsTitle.setStyleSheet("font-size: 16px; font-weight: bold; color: white;")
        self.globalSettingsLayout.addWidget(self.globalSettingsTitle)

        self.gsScrollArea = SingleDirectionScrollArea(
            self.globalSettingsContainer, Qt.Orientation.Vertical
        )
        self.gsScrollArea.setWidgetResizable(True)
        self.gsScrollArea.setStyleSheet("background: transparent; border: none;")
        self.gsScrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.gsScrollWidget = QWidget()
        self.gsInnerLayout = QVBoxLayout(self.gsScrollWidget)
        self.gsInnerLayout.setContentsMargins(0, 0, 10, 0)
        self.gsInnerLayout.setSpacing(10)

        self.gsGeneralLabel = CaptionLabel(tr('general'))
        self.gsGeneralLabel.setStyleSheet("font-weight: bold; margin-top: 10px; color: #aaaaaa;")
        self.gsInnerLayout.addWidget(self.gsGeneralLabel)

        self.gsLangBtn = PushButton()
        self.gsLangBtn.clicked.connect(self.show_language_menu)
        self.gsInnerLayout.addWidget(self.gsLangBtn)

        self.gsAudioBtn = PushButton()
        self.gsAudioBtn.clicked.connect(self.show_audio_menu)
        self.gsInnerLayout.addWidget(self.gsAudioBtn)

        self.gsAccentBtn = PushButton()
        self.gsAccentBtn.clicked.connect(self.choose_accent_color)
        self.gsInnerLayout.addWidget(self.gsAccentBtn)

        self.gsBgBtn = PushButton()
        self.gsBgBtn.clicked.connect(self.choose_bg_color)
        self.gsInnerLayout.addWidget(self.gsBgBtn)

        opacityRow = QHBoxLayout()
        self.opacityTitleLabel = CaptionLabel(tr('panel_opacity'))
        self.opacityValueLabel = CaptionLabel(f"{self.pending_panel_opacity}%")
        self.opacityValueLabel.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        opacityRow.addWidget(self.opacityTitleLabel)
        opacityRow.addStretch(1)
        opacityRow.addWidget(self.opacityValueLabel)
        self.gsInnerLayout.addLayout(opacityRow)

        self.opacitySlider = QSlider(Qt.Orientation.Horizontal)
        self.opacitySlider.setRange(20, 100)
        self.opacitySlider.setValue(self.pending_panel_opacity)
        self.opacitySlider.setToolTip(tr('tip_panel_opacity'))
        self.opacitySlider.valueChanged.connect(self.on_panel_opacity_changed)
        self.gsInnerLayout.addWidget(self.opacitySlider)

        gpuRow = QHBoxLayout()
        self.gsGPULabel = BodyLabel(tr('gpu_acceleration'))
        self.gsGPUToggle = SwitchButton()
        self.gsGPUToggle.setToolTip(tr('gpu_acceleration_tip'))
        self.gsGPUToggle.setChecked(self.config.get('gpu_acceleration', False))
        self.gsGPUToggle.checkedChanged.connect(self.on_gpu_acceleration_changed)
        gpuRow.addWidget(self.gsGPULabel)
        gpuRow.addStretch(1)
        gpuRow.addWidget(self.gsGPUToggle)
        self.gsInnerLayout.addLayout(gpuRow)

        hline1 = QFrame()
        hline1.setFrameShape(QFrame.Shape.HLine)
        hline1.setFrameShadow(QFrame.Shadow.Sunken)
        self.gsInnerLayout.addWidget(hline1)

        self.playlistSettingsTitle = CaptionLabel(tr('playlist'))
        self.playlistSettingsTitle.setStyleSheet("font-weight: bold; margin-top: 10px; color: #aaaaaa;")
        self.gsInnerLayout.addWidget(self.playlistSettingsTitle)

        thumbRow = QHBoxLayout()
        self.thumbLabel = CaptionLabel(tr('show_thumbnails'))
        self.thumbToggle = SwitchButton()
        self.thumbToggle.setChecked(self.config.get('show_thumbnails', True))
        self.thumbToggle.setOnText(tr('on'))
        self.thumbToggle.setOffText(tr('off'))
        self.thumbToggle.checkedChanged.connect(self.on_thumb_toggle_changed)
        thumbRow.addWidget(self.thumbLabel)
        thumbRow.addStretch(1)
        thumbRow.addWidget(self.thumbToggle)
        self.gsInnerLayout.addLayout(thumbRow)

        fileNameRow = QHBoxLayout()
        self.fileNameLabel = CaptionLabel(tr('show_filenames'))
        self.fileNameToggle = SwitchButton()
        self.fileNameToggle.setChecked(self.config.get('show_filenames', True))
        self.fileNameToggle.setOnText(tr('on'))
        self.fileNameToggle.setOffText(tr('off'))
        self.fileNameToggle.checkedChanged.connect(self.on_filename_toggle_changed)
        fileNameRow.addWidget(self.fileNameLabel)
        fileNameRow.addStretch(1)
        fileNameRow.addWidget(self.fileNameToggle)
        self.gsInnerLayout.addLayout(fileNameRow)

        sizeRow = QHBoxLayout()
        self.thumbSizeLabel = CaptionLabel(tr('thumbnail_size'))
        self.thumbSizeBtn = PushButton()
        self.thumbSizeBtn.clicked.connect(self.show_thumb_size_menu)
        sizeRow.addWidget(self.thumbSizeLabel)
        sizeRow.addStretch(1)
        sizeRow.addWidget(self.thumbSizeBtn)
        self.gsInnerLayout.addLayout(sizeRow)

        self.update_thumb_size_btn_text()

        hline2 = QFrame()
        hline2.setFrameShape(QFrame.Shape.HLine)
        hline2.setFrameShadow(QFrame.Shadow.Sunken)
        self.gsInnerLayout.addWidget(hline2)

        self.gsShortcutsLabel = CaptionLabel(tr('playback_shortcuts'))
        self.gsShortcutsLabel.setStyleSheet("font-weight: bold; margin-top: 10px; color: #aaaaaa;")
        self.gsInnerLayout.addWidget(self.gsShortcutsLabel)

        shortGrid = QGridLayout()
        shortGrid.setContentsMargins(0, 0, 0, 0)
        shortGrid.setSpacing(6)
        shortGrid.setColumnStretch(0, 1)
        shortGrid.setColumnStretch(1, 0)
        self.shortcutLabels = []

        actions = [
            ('play_pause',   'act_play_pause'),
            ('smart_mark',   'act_smart_mark'),
            ('toggle_loop',  'act_toggle_loop'),
            ('next_frame',   'act_next_frame'),
            ('prev_frame',   'act_prev_frame'),
            ('toggle_mute',  'act_toggle_mute'),
            ('act_full_screen', 'act_full_screen'),
        ]

        for i, (act, label_key) in enumerate(actions):
            lbl = BodyLabel(tr(label_key))
            lbl.setWordWrap(True)
            lbl._label_key = label_key
            self.shortcutLabels.append(lbl)
            shortGrid.addWidget(lbl, i, 0)
            btn = ShortcutButton(self.config['shortcuts'].get(act, 0))
            btn.setFixedWidth(80)
            btn.keyChanged.connect(lambda k, a=act: self.update_shortcut_sidebar(a, k))
            shortGrid.addWidget(btn, i, 1)

        self.gsInnerLayout.addLayout(shortGrid)
        self.gsInnerLayout.addStretch(1)

        self.gsScrollArea.setWidget(self.gsScrollWidget)
        self.globalSettingsLayout.addWidget(self.gsScrollArea)

        # Save button at the bottom
        self.gsSaveBtn = PushButton(tr('save_settings'))
        self.gsSaveBtn.clicked.connect(self.save_global_settings)
        self.gsSaveBtn.setStyleSheet(ACTION_BTN_STYLE)
        self.globalSettingsLayout.addWidget(self.gsSaveBtn)

        self.globalSettingsContainer.hide()

    def show_global_settings(self):
        is_visible = self.globalSettingsContainer.isVisible()
        if not is_visible:
            self.settingsContainer.hide()
        self.globalSettingsContainer.setVisible(not is_visible)
        if hasattr(self, 'update_sidebar_fullscreen_state'):
            self.update_sidebar_fullscreen_state()

        if not is_visible and not getattr(self, 'is_full_screen', False):
            sizes = self.mainSplitter.sizes()
            if len(sizes) > 0 and sizes[0] < 250:
                sizes[0] = 250
                self.mainSplitter.setSizes(sizes)

            device_id = self.config.get('audio_device', '')
            if device_id:
                from PyQt6.QtMultimedia import QMediaDevices
                for device in QMediaDevices.audioOutputs():
                    d_id = (device.id().data().decode()
                            if hasattr(device.id(), 'data') else str(device.id()))
                    if d_id == device_id:
                        self.audioOutput.setDevice(device)
                        break

            self.update_ui_texts()

    def toggle_settings(self):
        is_visible = self.settingsContainer.isVisible()
        if not is_visible:
            self.globalSettingsContainer.hide()
        self.settingsContainer.setVisible(not is_visible)
        if hasattr(self, 'update_sidebar_fullscreen_state'):
            self.update_sidebar_fullscreen_state()

        if not is_visible and not getattr(self, 'is_full_screen', False):
            sizes = self.mainSplitter.sizes()
            if len(sizes) > 1 and sizes[1] < 250:
                sizes[1] = 250
                self.mainSplitter.setSizes(sizes)
