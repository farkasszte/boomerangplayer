"""
GlobalSettingsMixin — global settings sidebar builder + language/audio/shortcuts handlers.
"""

from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QWidget, QMenu,
                              QGridLayout)
from qfluentwidgets import (CaptionLabel, PushButton, SwitchButton,
                             SingleDirectionScrollArea, BodyLabel)
from components import ShortcutButton
from translations import tr, set_lang
from utils import save_config
from styles import ACTION_BTN_STYLE


class GlobalSettingsMixin:
    """Builds self.globalSettingsContainer and handles all global settings logic."""

    def init_global_settings_sidebar(self):
        self.globalSettingsContainer = QFrame()
        self.globalSettingsContainer.setMinimumWidth(250)
        self.globalSettingsContainer.setStyleSheet("background: #202020; border: none;")
        self.globalSettingsLayout = QVBoxLayout(self.globalSettingsContainer)
        self.globalSettingsLayout.setContentsMargins(10, 10, 10, 10)
        self.globalSettingsLayout.setSpacing(10)

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
        self.gsInnerLayout.setSpacing(15)

        TRIGGER_STYLE = """
            PushButton {
                background: rgba(255,255,255,0.0605);
                border: 1px solid rgba(255,255,255,0.08);
                border-bottom: 1px solid rgba(255,255,255,0.2);
                border-radius: 4px; color: white;
                padding: 8px 12px; text-align: left; font-size: 13px;
            }
            PushButton:hover { background: rgba(255,255,255,0.1); }
        """

        self.gsGeneralLabel = CaptionLabel(tr('general'))
        self.gsGeneralLabel.setStyleSheet("font-weight: bold; margin-top: 10px; color: #aaaaaa;")
        self.gsInnerLayout.addWidget(self.gsGeneralLabel)

        self.gsLangBtn = PushButton()
        self.gsLangBtn.setStyleSheet(TRIGGER_STYLE)
        self.gsLangBtn.clicked.connect(self.show_language_menu)
        self.gsInnerLayout.addWidget(self.gsLangBtn)

        self.gsAudioBtn = PushButton()
        self.gsAudioBtn.setStyleSheet(TRIGGER_STYLE)
        self.gsAudioBtn.clicked.connect(self.show_audio_menu)
        self.gsInnerLayout.addWidget(self.gsAudioBtn)

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

        self.gsInnerLayout.addWidget(
            QFrame(frameShape=QFrame.Shape.HLine, frameShadow=QFrame.Shadow.Sunken)
        )

        self.gsShortcutsLabel = CaptionLabel(tr('playback_shortcuts'))
        self.gsShortcutsLabel.setStyleSheet("font-weight: bold; color: #aaaaaa;")
        self.gsInnerLayout.addWidget(self.gsShortcutsLabel)

        shortGrid = QGridLayout()
        shortGrid.setContentsMargins(0, 0, 0, 0)
        shortGrid.setSpacing(10)
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

    # ------------------------------------------------------------------ #
    # Panel toggle                                                         #
    # ------------------------------------------------------------------ #

    def show_global_settings(self):
        is_visible = self.globalSettingsContainer.isVisible()
        if not is_visible:
            self.settingsContainer.hide()
        self.globalSettingsContainer.setVisible(not is_visible)

        if not is_visible:
            sizes = self.mainSplitter.sizes()
            if sizes[0] < 250:
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

        if not is_visible:
            sizes = self.mainSplitter.sizes()
            if sizes[1] < 250:
                sizes[1] = 250
                self.mainSplitter.setSizes(sizes)

    # ------------------------------------------------------------------ #
    # Language menu                                                        #
    # ------------------------------------------------------------------ #

    _MENU_POPUP_STYLE = """
        QMenu { background-color: #202020; border: none; padding: 4px 0px; }
        QMenu::item { padding: 8px 25px; color: white; background-color: transparent; }
        QMenu::item:selected { background-color: rgba(255,255,255,0.1); }
        QMenu::item:checked { color: #00f2ff; font-weight: bold; }
        QMenu::indicator { width: 0px; }
    """

    def show_language_menu(self):
        menu = QMenu(parent=self)
        menu.setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        menu.setStyleSheet(self._MENU_POPUP_STYLE)

        current_lang = self.config.get('language', 'en')

        en_action = menu.addAction(tr('English'))
        en_action.setCheckable(True)
        en_action.setChecked(current_lang == 'en')
        en_action.triggered.connect(lambda: self.on_language_changed_sidebar(0))

        hu_action = menu.addAction(tr('Magyar'))
        hu_action.setCheckable(True)
        hu_action.setChecked(current_lang == 'hu')
        hu_action.triggered.connect(lambda: self.on_language_changed_sidebar(1))

        pos = self.gsLangBtn.mapToGlobal(QPoint(0, self.gsLangBtn.height()))
        menu.exec(pos)

    # ------------------------------------------------------------------ #
    # Audio device menu                                                    #
    # ------------------------------------------------------------------ #

    def show_audio_menu(self):
        menu = QMenu(parent=self)
        menu.setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        menu.setStyleSheet(self._MENU_POPUP_STYLE)

        current_device_id = self.config.get('audio_device', '')
        try:
            from PyQt6.QtMultimedia import QMediaDevices
            self.temp_devices = QMediaDevices.audioOutputs()
            if not self.temp_devices:
                menu.addAction(tr("no_devices_found")).setEnabled(False)
            else:
                for device in self.temp_devices:
                    name = device.description()
                    d_id = (device.id().data().decode()
                            if hasattr(device.id(), 'data') else str(device.id()))
                    action = menu.addAction(name)
                    action.setCheckable(True)
                    action.setChecked(d_id == current_device_id)
                    action.triggered.connect(
                        lambda checked, d=device: self.select_audio_device_sidebar(d)
                    )
        except Exception as e:
            menu.addAction(f"Error: {e}").setEnabled(False)

        pos = self.gsAudioBtn.mapToGlobal(QPoint(0, self.gsAudioBtn.height()))
        menu.exec(pos)

    def select_audio_device_sidebar(self, device):
        d_id = (device.id().data().decode()
                if hasattr(device.id(), 'data') else str(device.id()))
        self.config['audio_device'] = d_id
        # save_config(self.config) -> Removed for manual save
        self.audioOutput.setDevice(device)

    # ------------------------------------------------------------------ #
    # Language change handler                                              #
    # ------------------------------------------------------------------ #

    def on_language_changed_sidebar(self, idx):
        lang = 'en' if idx == 0 else 'hu'
        self.config['language'] = lang
        # save_config(self.config) -> Removed for manual save
        set_lang(lang)
        self.update_ui_texts()

    def on_gpu_acceleration_changed(self, checked):
        self.config['gpu_acceleration'] = checked
        # save_config(self.config) -> Removed for manual save
        # Notify the view if it exists
        if hasattr(self, 'pixmapItem') and hasattr(self, 'update_gpu_state'):
            self.update_gpu_state()
        self.update_pixmap_from_cache()

    # ------------------------------------------------------------------ #
    # Shortcut update                                                      #
    # ------------------------------------------------------------------ #

    def update_shortcut_sidebar(self, action_name, new_key):
        self.shortcuts[action_name] = new_key
        self.config['shortcuts'] = self.shortcuts
        # save_config(self.config) -> Removed for manual save

    def save_global_settings(self):
        from utils import save_config
        save_config(self.config)
        
        # Visual feedback
        from qfluentwidgets import InfoBar, InfoBarPosition
        InfoBar.success(
            title=tr('settings'),
            content=tr('save_settings') + " " + tr('ok'),
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )

    # ------------------------------------------------------------------ #
    # UI text refresh                                                      #
    # ------------------------------------------------------------------ #

    def update_ui_texts(self):
        self.playlistLabel.setText(tr('playlist'))
        self.thumbLabel.setText(tr('show_thumbnails'))
        self.btn_add.setText(tr('add'))
        self.btn_sort.setText(tr('sort'))
        self.btn_save.setText(tr('save'))
        self.btn_clear.setText(tr('clear'))
        self.drawingSidebarTitle.setText(tr('drawing_settings'))
        self.drawModeToggleLabel.setText(tr('drawing_mode'))
        self.laserModeToggleLabel.setText(tr('laser_mode'))
        self.penSizeLabel.setText(f"{self.penSizeSlider.value()} px")
        self.penColorBtn.setText(tr('color'))
        self.paletteTitle.setText(tr('color_palette'))
        self.saveScreenshotBtn.setText(tr('save_screenshot'))
        self.sidebarUndoBtn.setText(tr('undo'))
        self.sidebarClearBtn.setText(tr('clear'))
        self.settingsTitle.setText(tr('video_settings'))
        self.speedLabel.setText(tr('playback_speed'))
        self.zoomLabel.setText(tr('zoom'))
        self.cacheLabel.setText(tr('cache_window'))
        self.adjLabel.setText(tr('image_adjustments'))
        self.resetAdjButton.setText(tr('reset_image'))
        self.infoButton.setText(tr('file_info'))
        self.loopLabel.setText(tr('loop'))
        self.globalLoopLabel.setText(tr('global_loop_mode'))
        self.navLabel.setText(tr('zoom_nav_bar'))
        self.smartMarkButton.setText(tr('mark'))
        self.deleteMarkerButton.setText(tr('delete'))
        self.clearMarkersButton.setText(tr('reset'))
        self.saveLoopButton.setText(tr('save_loop'))
        self.saveFrameButton.setText(tr('save_frame'))
        self.mirrorButton.setText(tr('mirror_h'))
        self.mirrorVerticalButton.setText(tr('mirror_v'))
        self.rotateButton.setText(tr('rotate'))
        self.globalSettingsButton.setToolTip(tr('settings'))
        self.toggleSettingsButton.setToolTip(tr('video_settings'))
        self.loadingOverlay.setText(tr('caching'))

        idx = self.loopCombo.currentIndex()
        self.loopCombo.clear()
        self.loopCombo.addItems([tr('loop_none'), tr('loop_forward'), tr('loop_backward'), tr('loop_pingpong')])
        self.loopCombo.setCurrentIndex(idx)

        self.addMenu.clear()
        self.addMenu.addAction(tr('add_media'), self.open_file)
        self.addMenu.addAction(tr('add_video_folder'), lambda: self.add_folder_contents(type="video"))
        self.addMenu.addAction(tr('add_image_folder'), lambda: self.add_folder_contents(type="image"))
        self.addMenu.addSeparator()
        self.addMenu.addAction(tr('load_playlist'), self.load_playlist_from_file)

        self.sortMenu.clear()
        self.sortMenu.addAction(tr('sort_name_asc'),    lambda: self.sort_playlist_by("name_asc"))
        self.sortMenu.addAction(tr('sort_name_desc'),   lambda: self.sort_playlist_by("name_desc"))
        self.sortMenu.addAction(tr('sort_date_newest'), lambda: self.sort_playlist_by("date_newest"))
        self.sortMenu.addAction(tr('sort_date_oldest'), lambda: self.sort_playlist_by("date_oldest"))

        self.removeMenu.clear()
        self.removeMenu.addAction(tr('remove_selected'), self.remove_from_playlist)
        self.removeMenu.addAction(tr('clear_all'),       self.clear_playlist)

        self.brightnessLabel.setText(tr('brightness'))
        self.contrastLabel.setText(tr('contrast'))
        self.gammaLabel.setText(tr('gamma'))
        self.saturationLabel.setText(tr('saturation'))

        self.update_loop_frames_label()

        self.btn_save.setToolTip(tr('tip_save'))
        self.btn_clear.setToolTip(tr('tip_clear'))
        self.thumbToggle.setToolTip(tr('tip_thumbnails'))
        self.penTool.setText(tr('pen'))
        self.lineTool.setText(tr('line'))
        self.arrowTool.setText(tr('arrow'))
        self.textTool.setText(tr('text'))
        self.rectTool.setText(tr('rect'))
        self.ellipseTool.setText(tr('ellipse'))
        self.triangleTool.setText(tr('triangle'))
        self.objEraserTool.setText(tr('obj_eraser'))
        self.areaEraserTool.setText(tr('area_eraser'))
        self.measureTool.setText(tr('measure'))

        self.penTool.setToolTip(tr('tip_pen'))
        self.lineTool.setToolTip(tr('tip_line'))
        self.arrowTool.setToolTip(tr('tip_arrow'))
        self.textTool.setToolTip(tr('tip_text'))
        self.rectTool.setToolTip(tr('tip_rect'))
        self.ellipseTool.setToolTip(tr('tip_ellipse'))
        self.triangleTool.setToolTip(tr('tip_triangle'))
        self.objEraserTool.setToolTip(tr('tip_obj_eraser'))
        self.areaEraserTool.setToolTip(tr('tip_area_eraser'))
        self.measureTool.setToolTip(tr('tip_measure'))
        self.sidebarUndoBtn.setToolTip(tr('tip_undo'))
        self.sidebarClearBtn.setToolTip(tr('tip_clear_draw'))
        self.saveScreenshotBtn.setToolTip(tr('tip_screenshot'))
        self.togglePlaylistButton.setToolTip(tr('tip_playlist'))
        self.toggleDrawingButton.setToolTip(tr('tip_drawing'))
        self.globalSettingsButton.setToolTip(tr('tip_settings'))
        self.toggleSettingsButton.setToolTip(tr('video_settings'))
        self.stepBackButton.setToolTip(tr('tip_prev_frame'))
        self.playButton.setToolTip(tr('tip_play_pause'))
        self.stepForwardButton.setToolTip(tr('tip_next_frame'))
        self.volumeButton.setToolTip(tr('tip_mute'))

        self.loopToggle.blockSignals(True)
        self.loopToggle.setChecked(self.loopCombo.currentIndex() != 0)
        self.loopToggle.blockSignals(False)

        self.globalSettingsTitle.setText(tr('settings'))
        self.gsGeneralLabel.setText(tr('general'))
        self.gsShortcutsLabel.setText(tr('playback_shortcuts'))
        self.loopLabel.setText(tr('loop'))
        self.globalLoopLabel.setText(tr('global_loop_mode'))
        self.gsLangBtn.setText(tr('language'))
        self.gsAudioBtn.setText(tr('audio_device'))
        self.gsSaveBtn.setText(tr('save_settings'))
        self.gsGPULabel.setText(tr('gpu_acceleration'))
        self.gsGPUToggle.setToolTip(tr('gpu_acceleration_tip'))
        self.navToggle.setOnText(tr('on'))
        self.navToggle.setOffText(tr('off'))

        for lbl in getattr(self, 'shortcutLabels', []):
            lbl.setText(tr(lbl._label_key))
