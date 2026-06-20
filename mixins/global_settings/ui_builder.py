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

        inverseTextRow = QHBoxLayout()
        self.inverseTextLabel = CaptionLabel(tr('inverse_text'))
        self.inverseTextToggle = SwitchButton()
        
        self.inverseTextToggle.setChecked(self.config.get('inverse_text', False))
        self.inverseTextToggle.setOnText(tr('on'))
        self.inverseTextToggle.setOffText(tr('off'))
        
        self.inverseTextToggle.checkedChanged.connect(self.on_inverse_text_changed)
        inverseTextRow.addWidget(self.inverseTextLabel)
        inverseTextRow.addStretch(1)
        inverseTextRow.addWidget(self.inverseTextToggle)
        self.gsInnerLayout.addLayout(inverseTextRow)

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

        # (Reset defaults button moved to bottom next to save button)

        hline2 = QFrame()
        hline2.setFrameShape(QFrame.Shape.HLine)
        hline2.setFrameShadow(QFrame.Shadow.Sunken)
        self.gsInnerLayout.addWidget(hline2)

        self.gsShortcutsBtn = PushButton()
        self.gsShortcutsBtn.clicked.connect(self.show_shortcuts_dialog)
        self.gsInnerLayout.addWidget(self.gsShortcutsBtn)

        self.gsFileInfoBtn = PushButton()
        self.gsFileInfoBtn.clicked.connect(self.show_file_info)
        self.gsInnerLayout.addWidget(self.gsFileInfoBtn)

        self.gsAboutBtn = PushButton()
        self.gsAboutBtn.clicked.connect(self.show_about_dialog)
        self.gsInnerLayout.addWidget(self.gsAboutBtn)
        self.gsInnerLayout.addStretch(1)

        self.gsScrollArea.setWidget(self.gsScrollWidget)
        self.globalSettingsLayout.addWidget(self.gsScrollArea)

        # Bottom buttons row (Default and Save side-by-side)
        bottomButtonsLayout = QHBoxLayout()
        bottomButtonsLayout.setContentsMargins(0, 0, 0, 0)
        bottomButtonsLayout.setSpacing(8)

        self.gsResetDefaultsBtn = PushButton(tr('default'))
        self.gsResetDefaultsBtn.clicked.connect(self.reset_all_defaults)
        self.gsResetDefaultsBtn.setStyleSheet(ACTION_BTN_STYLE)

        self.gsSaveBtn = PushButton(tr('save'))
        
        self.gsSaveBtn.clicked.connect(self.save_global_settings)
        self.gsSaveBtn.setStyleSheet(ACTION_BTN_STYLE)

        bottomButtonsLayout.addWidget(self.gsResetDefaultsBtn)
        bottomButtonsLayout.addWidget(self.gsSaveBtn)
        self.globalSettingsLayout.addLayout(bottomButtonsLayout)

        self.globalSettingsContainer.hide()

    def show_global_settings(self):
        is_visible = self.globalSettingsContainer.isVisible()
        if not is_visible:
            self.settingsContainer.hide()
            if hasattr(self, 'imageAdjContainer'):
                self.imageAdjContainer.hide()
            if hasattr(self, 'subtitleContainer'):
                self.subtitleContainer.hide()
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

    def reset_all_defaults(self):
        """Reset all settings to factory defaults: HW, GPU, accents, palette, shortcuts, playlist."""
        from utils import DEFAULT_CONFIG

        # Factory default values
        factories = {
            'language': DEFAULT_CONFIG['language'],
            'audio_device': DEFAULT_CONFIG['audio_device'],
            'panel_opacity': DEFAULT_CONFIG['panel_opacity'],
            'shortcuts': dict(DEFAULT_CONFIG['shortcuts']),
            'palette': list(DEFAULT_CONFIG['palette']),
            'active_color_index': DEFAULT_CONFIG['active_color_index'],
            'gpu_acceleration': True,
            'accent_color': '#00f2ff',
            'bg_color': '#202020',
            'inverse_text': False,
            'show_thumbnails': True,
            'show_filenames': True,
            'thumbnail_size_index': 1,
            'advance_playlist_after_loop': DEFAULT_CONFIG.get('advance_playlist_after_loop', False),
            'advance_playlist_loop_count': DEFAULT_CONFIG.get('advance_playlist_loop_count', 1),
        }

        for key, val in factories.items():
            self.config[key] = val

        self.pending_accent_color = factories['accent_color']
        self.pending_bg_color = factories['bg_color']
        self.pending_panel_opacity = factories['panel_opacity']

        # ---- Update UI widgets ----
        if hasattr(self, 'advancePlaylistToggle'):
            self.advancePlaylistToggle.blockSignals(True)
            self.advancePlaylistToggle.setChecked(factories['advance_playlist_after_loop'])
            self.advancePlaylistToggle.blockSignals(False)
        if hasattr(self, 'loopCountSpin'):
            self.loopCountSpin.blockSignals(True)
            self.loopCountSpin.setValue(factories['advance_playlist_loop_count'])
            self.loopCountSpin.blockSignals(False)
        if hasattr(self, 'loopCountSlider'):
            self.loopCountSlider.blockSignals(True)
            self.loopCountSlider.setValue(factories['advance_playlist_loop_count'])
            self.loopCountSlider.blockSignals(False)

        if hasattr(self, 'gsLangBtn'):
            self.gsLangBtn.setText(tr('lang_en'))
        if hasattr(self, 'gsAudioBtn'):
            self.gsAudioBtn.setText(tr('default'))
        if hasattr(self, 'gsAccentBtn'):
            self.apply_accent_color(factories['accent_color'])
        if hasattr(self, 'opacitySlider'):
            self.opacitySlider.blockSignals(True)
            self.opacitySlider.setValue(factories['panel_opacity'])
            self.opacitySlider.blockSignals(False)
        if hasattr(self, 'opacityValueLabel'):
            self.opacityValueLabel.setText(f"{factories['panel_opacity']}%")
        if hasattr(self, 'gsGPUToggle'):
            self.gsGPUToggle.blockSignals(True)
            self.gsGPUToggle.setChecked(False)
            self.gsGPUToggle.blockSignals(False)
        if hasattr(self, 'inverseTextToggle'):
            self.inverseTextToggle.blockSignals(True)
            self.inverseTextToggle.setChecked(False)
            self.inverseTextToggle.blockSignals(False)
        # Reset theme to dark when inverse_text is turned off
        from qfluentwidgets import setTheme, Theme
        setTheme(Theme.DARK)

        # Playlist
        if hasattr(self, 'thumbToggle'):
            self.thumbToggle.blockSignals(True)
            self.thumbToggle.setChecked(True)
            self.thumbToggle.blockSignals(False)
        if hasattr(self, 'fileNameToggle'):
            self.fileNameToggle.blockSignals(True)
            self.fileNameToggle.setChecked(True)
            self.fileNameToggle.blockSignals(False)
        
        self.update_thumb_size_btn_text()
        if hasattr(self, 'update_playlist_layout'):
            self.update_playlist_layout(force_reload_thumbs=True)
        if hasattr(self, '_update_playlist_list_stylesheet'):
            self._update_playlist_list_stylesheet()

        # ---- Reset shortcut buttons ----
        from components import ShortcutButton
        dialog_btns = getattr(self, 'dialog_shortcut_buttons', None)
        for act in [
            'play_pause', 'smart_mark', 'toggle_loop', 'next_frame', 'prev_frame',
            'toggle_mute', 'act_full_screen', 'sub_delay_minus', 'sub_delay_plus'
        ]:
            default_key = DEFAULT_CONFIG['shortcuts'].get(act, 0)
            self.config['shortcuts'][act] = default_key
            if dialog_btns and act in dialog_btns:
                btn = dialog_btns[act]
                btn.key_code = default_key
                btn.update_text()
        if hasattr(self, 'setup_shortcuts'):
            self.setup_shortcuts()

        # ---- Refresh styles, palette, UI texts ----
        if hasattr(self, 'refresh_custom_styles'):
            self.refresh_custom_styles(
                accent_color=factories['accent_color'],
                bg_color=factories['bg_color']
            )
        if hasattr(self, 'update_palette_ui'):
            self.update_palette_ui()
        if hasattr(self, 'update_ui_texts'):
            self.update_ui_texts()

        from qfluentwidgets import InfoBar, InfoBarPosition
        InfoBar.success(
            title=tr('settings'),
            content=tr('reset_defaults_done'),
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self
        )

    def toggle_settings(self):
        is_visible = self.settingsContainer.isVisible()
        if not is_visible:
            self.globalSettingsContainer.hide()
            if hasattr(self, 'imageAdjContainer'):
                self.imageAdjContainer.hide()
            if hasattr(self, 'subtitleContainer'):
                self.subtitleContainer.hide()
        
        self.settingsContainer.setVisible(not is_visible)
        if hasattr(self, 'update_sidebar_fullscreen_state'):
            self.update_sidebar_fullscreen_state()

        if not is_visible and not getattr(self, 'is_full_screen', False):
            sizes = self.mainSplitter.sizes()
            if len(sizes) > 1 and sizes[1] < 250:
                sizes[1] = 250
                self.mainSplitter.setSizes(sizes)

    def show_shortcuts_dialog(self):
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QGridLayout, QHBoxLayout
        from qfluentwidgets import BodyLabel, PushButton
        from components import ShortcutButton
        from styles import ACTION_BTN_STYLE
        
        dialog = QDialog(self)
        if hasattr(self, 'style_dialog'):
            self.style_dialog(dialog)
        dialog.setWindowTitle(tr('playback_shortcuts'))
        dialog.setMinimumWidth(320)
        
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
                print(f"[DWM] Failed to set shortcuts dialog title bar color: {e}")
                
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(12)
        
        grid = QGridLayout()
        grid.setSpacing(8)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 0)
        
        actions = [
            ('play_pause',   'act_play_pause'),
            ('smart_mark',   'act_smart_mark'),
            ('toggle_loop',  'act_toggle_loop'),
            ('next_frame',   'act_next_frame'),
            ('prev_frame',   'act_prev_frame'),
            ('toggle_mute',  'act_toggle_mute'),
            ('act_full_screen', 'act_full_screen'),
            ('sub_delay_minus', 'act_sub_delay_minus'),
            ('sub_delay_plus',  'act_sub_delay_plus'),
        ]
        
        self.dialog_shortcut_buttons = {}
        for i, (act, label_key) in enumerate(actions):
            lbl = BodyLabel(tr(label_key))
            lbl.setWordWrap(True)
            grid.addWidget(lbl, i, 0)
            
            btn = ShortcutButton(self.config['shortcuts'].get(act, 0))
            btn.setFixedWidth(100)
            btn.keyChanged.connect(lambda k, a=act: self.update_shortcut_sidebar(a, k))
            self.dialog_shortcut_buttons[act] = btn
            grid.addWidget(btn, i, 1)
            
        layout.addLayout(grid)
        
        # Close button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = PushButton(tr('close'))
        close_btn.setStyleSheet(ACTION_BTN_STYLE)
        close_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
        
        dialog.exec()
        self.dialog_shortcut_buttons = None
