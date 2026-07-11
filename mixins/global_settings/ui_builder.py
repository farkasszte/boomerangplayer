import sys
from typing import Any, Dict

from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QWidget, QGridLayout, QDialog
from qfluentwidgets import CaptionLabel, PushButton, SwitchButton, SingleDirectionScrollArea, BodyLabel, InfoBar, InfoBarPosition, setTheme, Theme

from components import NoWheelSlider, ShortcutButton
from translations import tr
from styles import ACTION_BTN_STYLE, get_color_tokens


class GlobalSettingsUiBuilderMixin:
    """Mixin class to build the global settings UI elements and handle setting resets."""

    def init_global_settings_sidebar(self) -> None:
        t = get_color_tokens(
            self.config.get('accent_color', '#00f2ff'),
            self.config.get('bg_color', '#202020'),
            self.config.get('inverse_text', False)
        )
        self.globalSettingsContainer = QFrame()
        self.globalSettingsContainer.setMinimumWidth(250)
        self.globalSettingsContainer.setStyleSheet(f"background: {t['bg']}; border: none;")
        self.globalSettingsLayout = QVBoxLayout(self.globalSettingsContainer)
        self.globalSettingsLayout.setContentsMargins(10, 10, 4, 10)
        self.globalSettingsLayout.setSpacing(6)

        self.pending_accent_color = self.config.get('accent_color', '#00f2ff')
        self.pending_bg_color = self.config.get('bg_color', '#202020')
        self.pending_panel_opacity = self.config.get('panel_opacity', 100)

        self.globalSettingsTitle = CaptionLabel(tr('settings'))
        self.globalSettingsTitle.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {t['fg']};")
        self.globalSettingsLayout.addWidget(self.globalSettingsTitle)

        self.gsScrollArea = SingleDirectionScrollArea(
            self.globalSettingsContainer, Qt.Orientation.Vertical
        )
        self.gsScrollArea.setWidgetResizable(True)
        self.gsScrollArea.setStyleSheet("background: transparent; border: none;")
        self.gsScrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.gsScrollWidget = QWidget()
        self.gsInnerLayout = QVBoxLayout(self.gsScrollWidget)
        self.gsInnerLayout.setContentsMargins(0, 0, 0, 0)
        self.gsInnerLayout.setSpacing(10)

        # Build individual UI sections
        self._init_general_section(self.gsInnerLayout, t)
        
        # Horizontal divider
        hline1 = QFrame()
        hline1.setFrameShape(QFrame.Shape.HLine)
        hline1.setFrameShadow(QFrame.Shadow.Sunken)
        self.gsInnerLayout.addWidget(hline1)

        self._init_playlist_section(self.gsInnerLayout, t)
        
        # Horizontal divider
        hline2 = QFrame()
        hline2.setFrameShape(QFrame.Shape.HLine)
        hline2.setFrameShadow(QFrame.Shadow.Sunken)
        self.gsInnerLayout.addWidget(hline2)

        self._init_other_buttons(self.gsInnerLayout)

        self.gsScrollArea.setWidget(self.gsScrollWidget)
        self.globalSettingsLayout.addWidget(self.gsScrollArea)

        # Bottom actions (Save and Reset Defaults)
        self._init_bottom_buttons(self.globalSettingsLayout)

        self.globalSettingsContainer.hide()

    def _init_general_section(self, layout: QVBoxLayout, t: dict) -> None:
        self.gsGeneralLabel = CaptionLabel(tr('general'))
        self.gsGeneralLabel.setStyleSheet(f"font-weight: bold; margin-top: 10px; color: {t['sec_fg']};")
        layout.addWidget(self.gsGeneralLabel)

        self.gsLangBtn = PushButton()
        self.gsLangBtn.clicked.connect(self.show_language_menu)
        layout.addWidget(self.gsLangBtn)

        self.gsAudioBtn = PushButton()
        self.gsAudioBtn.clicked.connect(self.show_audio_menu)
        layout.addWidget(self.gsAudioBtn)

        self.gsAccentBtn = PushButton()
        self.gsAccentBtn.clicked.connect(self.choose_accent_color)
        layout.addWidget(self.gsAccentBtn)

        self.gsBgBtn = PushButton()
        self.gsBgBtn.clicked.connect(self.choose_bg_color)
        layout.addWidget(self.gsBgBtn)

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
        layout.addLayout(inverseTextRow)

        opacityRow = QHBoxLayout()
        self.opacityTitleLabel = CaptionLabel(tr('panel_opacity'))
        self.opacityValueLabel = CaptionLabel(f"{self.pending_panel_opacity}%")
        self.opacityValueLabel.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        opacityRow.addWidget(self.opacityTitleLabel)
        opacityRow.addStretch(1)
        opacityRow.addWidget(self.opacityValueLabel)
        layout.addLayout(opacityRow)

        self.opacitySlider = NoWheelSlider(Qt.Orientation.Horizontal)
        self.opacitySlider.setRange(20, 100)
        self.opacitySlider.setSingleStep(5)
        self.opacitySlider.setPageStep(5)
        self.opacitySlider.setValue(self.pending_panel_opacity)
        self.opacitySlider.setToolTip(tr('tip_panel_opacity'))
        self.opacitySlider.valueChanged.connect(self.on_panel_opacity_changed)
        layout.addWidget(self.opacitySlider)

    def _init_playlist_section(self, layout: QVBoxLayout, t: dict) -> None:
        self.playlistSettingsTitle = CaptionLabel(tr('playlist'))
        self.playlistSettingsTitle.setStyleSheet(f"font-weight: bold; margin-top: 10px; color: {t['sec_fg']};")
        layout.addWidget(self.playlistSettingsTitle)

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
        layout.addLayout(thumbRow)

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
        layout.addLayout(fileNameRow)

        sizeRow = QHBoxLayout()
        self.thumbSizeLabel = CaptionLabel(tr('thumbnail_size'))
        self.thumbSizeBtn = PushButton()
        self.thumbSizeBtn.clicked.connect(self.show_thumb_size_menu)
        sizeRow.addWidget(self.thumbSizeLabel)
        sizeRow.addStretch(1)
        sizeRow.addWidget(self.thumbSizeBtn)
        layout.addLayout(sizeRow)

        self.update_thumb_size_btn_text()

    def _init_other_buttons(self, layout: QVBoxLayout) -> None:
        self.gsShortcutsBtn = PushButton()
        self.gsShortcutsBtn.clicked.connect(self.show_shortcuts_dialog)
        layout.addWidget(self.gsShortcutsBtn)

        self.gsFileInfoBtn = PushButton()
        self.gsFileInfoBtn.clicked.connect(self.show_file_info)
        layout.addWidget(self.gsFileInfoBtn)

        self.gsAboutBtn = PushButton()
        self.gsAboutBtn.clicked.connect(self.show_about_dialog)
        layout.addWidget(self.gsAboutBtn)
        layout.addStretch(1)

    def _init_bottom_buttons(self, layout: QVBoxLayout) -> None:
        bottomButtonsLayout = QHBoxLayout()
        bottomButtonsLayout.setSpacing(8)

        self.gsResetDefaultsBtn = PushButton(tr('default'))
        self.gsResetDefaultsBtn.clicked.connect(self.reset_all_defaults)
        self.gsResetDefaultsBtn.setStyleSheet(ACTION_BTN_STYLE)

        self.gsSaveBtn = PushButton(tr('save'))
        self.gsSaveBtn.clicked.connect(self.save_global_settings)
        self.gsSaveBtn.setStyleSheet(ACTION_BTN_STYLE)

        bottomButtonsLayout.addWidget(self.gsResetDefaultsBtn)
        bottomButtonsLayout.addWidget(self.gsSaveBtn)
        layout.addLayout(bottomButtonsLayout)

    def show_global_settings(self) -> None:
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

    def reset_all_defaults(self) -> None:
        """Reset all settings to factory defaults: HW, GPU, accents, palette, shortcuts, playlist."""
        from utils import DEFAULT_CONFIG

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
            # Audio EQ
            'audio_eq_enabled': DEFAULT_CONFIG.get('audio_eq_enabled', False),
            'audio_eq_preset': DEFAULT_CONFIG.get('audio_eq_preset', 'Flat'),
            'audio_eq_gains': list(DEFAULT_CONFIG.get('audio_eq_gains', [0] * 10)),
            # Subtitle settings
            'enable_subtitles': DEFAULT_CONFIG.get('enable_subtitles', True),
            'subtitle_font_family': DEFAULT_CONFIG.get('subtitle_font_family', 'Segoe UI'),
            'subtitle_font_size': DEFAULT_CONFIG.get('subtitle_font_size', 24),
            'subtitle_text_color': DEFAULT_CONFIG.get('subtitle_text_color', '#ffffff'),
            'subtitle_bg_color': DEFAULT_CONFIG.get('subtitle_bg_color', '#000000'),
            'subtitle_bg_opacity': DEFAULT_CONFIG.get('subtitle_bg_opacity', 60),
            'subtitle_outline_enabled': DEFAULT_CONFIG.get('subtitle_outline_enabled', False),
            'subtitle_outline_width': DEFAULT_CONFIG.get('subtitle_outline_width', 2),
            'subtitle_outline_color': DEFAULT_CONFIG.get('subtitle_outline_color', '#000000'),
            'subtitle_shadow_enabled': DEFAULT_CONFIG.get('subtitle_shadow_enabled', False),
            'subtitle_shadow_blur': DEFAULT_CONFIG.get('subtitle_shadow_blur', 5),
            'subtitle_shadow_dx': DEFAULT_CONFIG.get('subtitle_shadow_dx', 2),
            'subtitle_shadow_dy': DEFAULT_CONFIG.get('subtitle_shadow_dy', 2),
            'subtitle_shadow_color': DEFAULT_CONFIG.get('subtitle_shadow_color', '#000000'),
            'subtitle_v_offset': DEFAULT_CONFIG.get('subtitle_v_offset', 5),
            'subtitle_h_offset': DEFAULT_CONFIG.get('subtitle_h_offset', 0),
            'subtitle_offset': DEFAULT_CONFIG.get('subtitle_offset', 0),
        }

        # Apply settings and state
        self._reset_config_defaults(factories)
        
        # Reset UI Widgets grouped by feature
        self._reset_playlist_defaults_ui(factories)
        self._reset_audio_eq_defaults_ui(factories)
        self._reset_subtitle_defaults_ui(factories)
        self._reset_shortcut_defaults_ui(factories)
        self._reset_theme_defaults_ui(factories)

        # Refresh styles, palette, UI texts
        if hasattr(self, 'refresh_custom_styles'):
            self.refresh_custom_styles(
                accent_color=factories['accent_color'],
                bg_color=factories['bg_color']
            )
        if hasattr(self, 'update_palette_ui'):
            self.update_palette_ui()
        if hasattr(self, 'update_ui_texts'):
            self.update_ui_texts()

        InfoBar.success(
            title=tr('settings'),
            content=tr('reset_defaults_done'),
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self
        )

    def _reset_config_defaults(self, factories: dict) -> None:
        for key, val in factories.items():
            self.config[key] = val

        self.pending_accent_color = factories['accent_color']
        self.pending_bg_color = factories['bg_color']
        self.pending_panel_opacity = factories['panel_opacity']
        self.accent_color = factories['accent_color']

    def _reset_playlist_defaults_ui(self, factories: dict) -> None:
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

    def _reset_audio_eq_defaults_ui(self, factories: dict) -> None:
        if hasattr(self, 'audioEqToggle'):
            self.audioEqToggle.blockSignals(True)
            self.audioEqToggle.setChecked(factories['audio_eq_enabled'])
            self.audioEqToggle.blockSignals(False)
        if hasattr(self, 'audioEqPresetCombo'):
            self.audioEqPresetCombo.blockSignals(True)
            idx = self.audioEqPresetCombo.findData(factories['audio_eq_preset'])
            if idx != -1:
                self.audioEqPresetCombo.setCurrentIndex(idx)
            self.audioEqPresetCombo.blockSignals(False)
        if hasattr(self, 'eq_sliders') and hasattr(self, 'eq_labels'):
            for i, slider in enumerate(self.eq_sliders):
                slider.blockSignals(True)
                slider.setValue(factories['audio_eq_gains'][i])
                slider.blockSignals(False)
            for i, label in enumerate(self.eq_labels):
                g = factories['audio_eq_gains'][i]
                label.setText(f"{g:+d}" if g != 0 else "0")
        if hasattr(self, 'update_audio_presets_ui'):
            self.update_audio_presets_ui()

    def _reset_subtitle_defaults_ui(self, factories: dict) -> None:
        if hasattr(self, 'subEnableToggle'):
            self.subEnableToggle.blockSignals(True)
            self.subEnableToggle.setChecked(factories['enable_subtitles'])
            self.subEnableToggle.blockSignals(False)
        if hasattr(self, 'subFontCombo'):
            self.subFontCombo.blockSignals(True)
            idx = self.subFontCombo.findText(factories['subtitle_font_family'])
            if idx != -1:
                self.subFontCombo.setCurrentIndex(idx)
            self.subFontCombo.blockSignals(False)
        if hasattr(self, 'subFontSizeSpin'):
            self.subFontSizeSpin.blockSignals(True)
            self.subFontSizeSpin.setValue(factories['subtitle_font_size'])
            self.subFontSizeSpin.blockSignals(False)
        if hasattr(self, 'subFontSizeSlider'):
            self.subFontSizeSlider.blockSignals(True)
            self.subFontSizeSlider.setValue(factories['subtitle_font_size'])
            self.subFontSizeSlider.blockSignals(False)
        if hasattr(self, 'subTextColorBtn'):
            self.config['subtitle_text_color'] = factories['subtitle_text_color']
        if hasattr(self, 'subBgColorBtn'):
            self.config['subtitle_bg_color'] = factories['subtitle_bg_color']
        if hasattr(self, '_update_sub_color_btns'):
            self._update_sub_color_btns()
        if hasattr(self, 'subBgOpacitySpin'):
            self.subBgOpacitySpin.blockSignals(True)
            self.subBgOpacitySpin.setValue(factories['subtitle_bg_opacity'])
            self.subBgOpacitySpin.blockSignals(False)
        if hasattr(self, 'subBgOpacitySlider'):
            self.subBgOpacitySlider.blockSignals(True)
            self.subBgOpacitySlider.setValue(factories['subtitle_bg_opacity'])
            self.subBgOpacitySlider.blockSignals(False)
        if hasattr(self, 'subOutlineToggle'):
            self.subOutlineToggle.blockSignals(True)
            self.subOutlineToggle.setChecked(factories['subtitle_outline_enabled'])
            self.subOutlineToggle.blockSignals(False)
        if hasattr(self, 'subOutlineWidthSpin'):
            self.subOutlineWidthSpin.blockSignals(True)
            self.subOutlineWidthSpin.setValue(factories['subtitle_outline_width'])
            self.subOutlineWidthSpin.blockSignals(False)
        if hasattr(self, 'subOutlineWidthSlider'):
            self.subOutlineWidthSlider.blockSignals(True)
            self.subOutlineWidthSlider.setValue(factories['subtitle_outline_width'])
            self.subOutlineWidthSlider.blockSignals(False)
        if hasattr(self, 'subOutlineColorBtn'):
            self.config['subtitle_outline_color'] = factories['subtitle_outline_color']
        if hasattr(self, 'subShadowToggle'):
            self.subShadowToggle.blockSignals(True)
            self.subShadowToggle.setChecked(factories['subtitle_shadow_enabled'])
            self.subShadowToggle.blockSignals(False)
        if hasattr(self, 'subShadowBlurSpin'):
            self.subShadowBlurSpin.blockSignals(True)
            self.subShadowBlurSpin.setValue(factories['subtitle_shadow_blur'])
            self.subShadowBlurSpin.blockSignals(False)
        if hasattr(self, 'subShadowBlurSlider'):
            self.subShadowBlurSlider.blockSignals(True)
            self.subShadowBlurSlider.setValue(factories['subtitle_shadow_blur'])
            self.subShadowBlurSlider.blockSignals(False)
        if hasattr(self, 'subShadowDxSpin'):
            self.subShadowDxSpin.blockSignals(True)
            self.subShadowDxSpin.setValue(factories['subtitle_shadow_dx'])
            self.subShadowDxSpin.blockSignals(False)
        if hasattr(self, 'subShadowDxSlider'):
            self.subShadowDxSlider.blockSignals(True)
            self.subShadowDxSlider.setValue(factories['subtitle_shadow_dx'])
            self.subShadowDxSlider.blockSignals(False)
        if hasattr(self, 'subShadowDySpin'):
            self.subShadowDySpin.blockSignals(True)
            self.subShadowDySpin.setValue(factories['subtitle_shadow_dy'])
            self.subShadowDySpin.blockSignals(False)
        if hasattr(self, 'subShadowDySlider'):
            self.subShadowDySlider.blockSignals(True)
            self.subShadowDySlider.setValue(factories['subtitle_shadow_dy'])
            self.subShadowDySlider.blockSignals(False)
        if hasattr(self, 'subShadowColorBtn'):
            self.config['subtitle_shadow_color'] = factories['subtitle_shadow_color']
        if hasattr(self, 'subVOffsetSpin'):
            self.subVOffsetSpin.blockSignals(True)
            self.subVOffsetSpin.setValue(factories['subtitle_v_offset'])
            self.subVOffsetSpin.blockSignals(False)
        if hasattr(self, 'subVOffsetSlider'):
            self.subVOffsetSlider.blockSignals(True)
            self.subVOffsetSlider.setValue(factories['subtitle_v_offset'])
            self.subVOffsetSlider.blockSignals(False)
        if hasattr(self, 'subHOffsetSpin'):
            self.subHOffsetSpin.blockSignals(True)
            self.subHOffsetSpin.setValue(factories['subtitle_h_offset'])
            self.subHOffsetSpin.blockSignals(False)
        if hasattr(self, 'subHOffsetSlider'):
            self.subHOffsetSlider.blockSignals(True)
            self.subHOffsetSlider.setValue(factories['subtitle_h_offset'])
            self.subHOffsetSlider.blockSignals(False)
        if hasattr(self, 'subOffsetSpin'):
            self.subOffsetSpin.blockSignals(True)
            self.subOffsetSpin.setValue(factories['subtitle_offset'])
            self.subOffsetSpin.blockSignals(False)
        if hasattr(self, 'subOffsetSlider'):
            self.subOffsetSlider.blockSignals(True)
            self.subOffsetSlider.setValue(factories['subtitle_offset'])
            self.subOffsetSlider.blockSignals(False)

    def _reset_shortcut_defaults_ui(self, factories: dict) -> None:
        dialog_btns = getattr(self, 'dialog_shortcut_buttons', None)
        for act in [
            'play_pause', 'smart_mark', 'toggle_loop', 'next_frame', 'prev_frame',
            'toggle_mute', 'act_full_screen', 'sub_delay_minus', 'sub_delay_plus'
        ]:
            default_key = factories['shortcuts'].get(act, 0)
            self.config['shortcuts'][act] = default_key
            if dialog_btns and act in dialog_btns:
                btn = dialog_btns[act]
                btn.key_code = default_key
                btn.update_text()
        if hasattr(self, 'setup_shortcuts'):
            self.setup_shortcuts()

    def _reset_theme_defaults_ui(self, factories: dict) -> None:
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
        setTheme(Theme.DARK)

    def toggle_settings(self) -> None:
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

    def show_shortcuts_dialog(self) -> None:
        dialog = QDialog(self)
        if hasattr(self, 'style_dialog'):
            self.style_dialog(dialog)
        dialog.setWindowTitle(tr('playback_shortcuts'))
        dialog.setMinimumWidth(320)
        
        # Apply Windows 11 title bar styling
        bg_color = self.config.get('bg_color', '#202020')
        self._apply_dialog_win11_style(dialog, bg_color)
                
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

    @staticmethod
    def _apply_dialog_win11_style(dialog: QDialog, bg_color: str) -> None:
        """Applies Windows 11 DWM title bar styling to a QDialog on Windows platforms."""
        if sys.platform == 'win32':
            try:
                import ctypes
                from PyQt6.QtGui import QColor
                hwnd = int(dialog.winId())
                
                # Convert QColor to COLORREF (0x00BBGGRR)
                qcolor = QColor(bg_color)
                bg_color_ref = qcolor.red() | (qcolor.green() << 8) | (qcolor.blue() << 16)
                
                # DWMWA_CAPTION_COLOR = 35 (Windows 11 Build 22000+)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    35,
                    ctypes.byref(ctypes.c_int(bg_color_ref)),
                    4
                )
            except Exception as e:
                print(f"[DWM] Failed to set shortcuts dialog title bar color: {e}")
