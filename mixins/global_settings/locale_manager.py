from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtWidgets import QMenu
from translations import tr, set_lang
from styles import get_styles

class GlobalSettingsLocaleManagerMixin:
    def show_language_menu(self):
        menu = QMenu(parent=self)
        menu.setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        
        accent = self.config.get('accent_color', '#00f2ff')
        
        bg_color = self.config.get('bg_color', '#202020')
        style = get_styles(accent, bg_color)['MENU_POPUP_STYLE']
        menu.setStyleSheet(style)

        
        current_lang = self.config.get('language', 'en')

        en_action = menu.addAction(tr('lang_en'))
        
        en_action.setCheckable(True)
        
        en_action.setChecked(current_lang == 'en')
        
        en_action.triggered.connect(lambda: self.on_language_changed_sidebar(0))

        hu_action = menu.addAction(tr('lang_hu'))
        
        hu_action.setCheckable(True)
        
        hu_action.setChecked(current_lang == 'hu')
        
        hu_action.triggered.connect(lambda: self.on_language_changed_sidebar(1))

        
        pos = self.gsLangBtn.mapToGlobal(QPoint(0, self.gsLangBtn.height()))
        menu.exec(pos)

    def on_language_changed_sidebar(self, idx):
        lang = 'en' if idx == 0 else 'hu'
        
        self.config['language'] = lang
        set_lang(lang)
        self.update_ui_texts()

    def update_ui_texts(self):
        
        self.playlistLabel.setText(tr('playlist'))
        
        self.thumbLabel.setText(tr('show_thumbnails'))
        
        self.fileNameLabel.setText(tr('show_filenames'))
        
        self.btn_add.setText(tr('add'))
        
        self.btn_sort.setText(tr('sort'))
        
        self.btn_save.setText(tr('save'))
        
        self.btn_clear.setText(tr('clear'))
        
        self.drawingSidebarTitle.setText(tr('drawing_settings'))
        
        self.drawModeToggleLabel.setText(tr('drawing_mode'))
        
        self.laserModeToggleLabel.setText(tr('laser_mode'))
        
        if hasattr(self, 'penSizeLabel') and self.penSizeLabel:
            from PyQt6.QtWidgets import QLabel
            if isinstance(self.penSizeLabel, QLabel):
                self.penSizeLabel.setText(f"{self.penSizeSlider.value()} px")
            else:
                self.penSizeLabel.blockSignals(True)
                self.penSizeLabel.setValue(self.penSizeSlider.value())
                self.penSizeLabel.blockSignals(False)
        
        self.penColorBtn.setText(tr('color'))
        
        self.paletteTitle.setText(tr('color_palette'))
        
        self.saveScreenshotBtn.setText(tr('save_screenshot'))
        
        self.sidebarUndoBtn.setText(tr('undo'))
        
        self.sidebarClearBtn.setText(tr('clear'))
        
        self.settingsTitle.setText(tr('video_settings'))
        if hasattr(self, 'playbackLabel'):
            self.playbackLabel.setText(tr('playback'))
        
        self.speedLabel.setText(tr('playback_speed'))
        
        self.zoomLabel.setText(tr('zoom'))
        
        self.cacheLabel.setText(tr('cache_window'))
        
        self.adjLabel.setText(tr('image_adjustments'))
        
        self.resetAdjButton.setText(tr('reset_image'))
        
        self.infoButton.setText(tr('file_info'))
        
        self.loopLabel.setText(tr('loop'))
        
        if hasattr(self, 'zoomToLoopLabel') and self.zoomToLoopLabel:
            self.zoomToLoopLabel.setText(tr('zoom_to_loop'))
        if hasattr(self, 'zoomToWindowLabel') and self.zoomToWindowLabel:
            self.zoomToWindowLabel.setText(tr('zoom_to_window'))
        if hasattr(self, 'chronometerToggleLabel'):
            self.chronometerToggleLabel.setText(tr('chronometer_overlay'))
        
        self.smartMarkButton.setText(tr('mark'))
        
        self.deleteMarkerButton.setText(tr('delete'))
        
        self.clearMarkersButton.setText(tr('reset'))
        if hasattr(self, 'manageMarkersButton') and self.manageMarkersButton:
            
            count = len(self.markers)
            self.manageMarkersButton.setText(f"{tr('manage_markers')} ({count})")
        if hasattr(self, 'syncLabel'):
            self.syncLabel.setText(tr('sync_title'))
        if hasattr(self, 'syncLockLabel') and self.syncLockLabel:
            self.syncLockLabel.setText(tr('sync_lock'))
        if hasattr(self, 'syncFrameButton'):
            self.syncFrameButton.setText(tr('sync_frame'))
        
        self.saveLoopButton.setText(tr('save_loop'))
        
        self.saveFrameButton.setText(tr('save_frame'))
        
        self.mirrorButton.setText(tr('mirror_h'))
        
        self.mirrorVerticalButton.setText(tr('mirror_v'))
        if hasattr(self, 'rotateLeftButton'):
            self.rotateLeftButton.setText(tr('rotate_left'))
        if hasattr(self, 'rotateRightButton'):
            self.rotateRightButton.setText(tr('rotate_right'))
        
        self.globalSettingsButton.setToolTip(tr('settings'))
        if hasattr(self, 'aboutButton'):
            self.aboutButton.setToolTip(tr('about'))
        
        self.toggleSettingsButton.setToolTip(tr('video_settings'))
        
        self.loadingOverlay.setText(tr('caching'))

        
        idx = self.loopCombo.currentIndex()
        
        self.loopCombo.clear()
        
        self.loopCombo.addItems([tr('loop_none'), tr('loop_forward'), tr('loop_backward'), tr('loop_pingpong')])
        
        self.loopCombo.setCurrentIndex(idx)


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

        
        self.btn_add.setToolTip(tr('tip_add'))
        
        self.btn_sort.setToolTip(tr('tip_sort'))
        
        self.btn_save.setToolTip(tr('tip_save'))
        
        self.btn_clear.setToolTip(tr('tip_clear'))
        
        self.penColorBtn.setToolTip(tr('tip_color'))
        
        self.speedSlider.setToolTip(tr('tip_playback_speed'))
        if hasattr(self, 'speedLockBtn') and self.speedLockBtn:
            
            if getattr(self, 'isSpeedLocked', False):
                self.speedLockBtn.setToolTip(tr('tip_speed_locked'))
            else:
                self.speedLockBtn.setToolTip(tr('tip_speed_unlocked'))
        
        self.zoomSlider.setToolTip(tr('tip_zoom'))
        
        self.cacheSlider.setToolTip(tr('tip_cache_window'))
        
        self.brightnessSlider.setToolTip(tr('tip_brightness'))
        
        self.contrastSlider.setToolTip(tr('tip_contrast'))
        
        self.gammaSlider.setToolTip(tr('tip_gamma'))
        
        self.saturationSlider.setToolTip(tr('tip_saturation'))
        
        self.mirrorButton.setToolTip(tr('tip_mirror_h'))
        
        self.mirrorVerticalButton.setToolTip(tr('tip_mirror_v'))
        if hasattr(self, 'rotateLeftButton'):
            self.rotateLeftButton.setToolTip(tr('tip_rotate_left'))
        if hasattr(self, 'rotateRightButton'):
            self.rotateRightButton.setToolTip(tr('tip_rotate_right'))
        
        self.resetAdjButton.setToolTip(tr('tip_reset_image'))
        
        self.infoButton.setToolTip(tr('tip_file_info'))
        
        if hasattr(self, 'zoomToLoopToggle') and self.zoomToLoopToggle:
            self.zoomToLoopToggle.setToolTip(tr('tip_zoom_to_loop'))
        if hasattr(self, 'zoomToWindowToggle') and self.zoomToWindowToggle:
            self.zoomToWindowToggle.setToolTip(tr('tip_zoom_to_window'))
        if hasattr(self, 'zoomWindowResetBtn') and self.zoomWindowResetBtn:
            self.zoomWindowResetBtn.setToolTip(tr('tip_reset_zoom_window'))
        
        self.loopCombo.setToolTip(tr('tip_loop_mode'))
        
        self.saveLoopButton.setToolTip(tr('tip_save_loop'))
        
        self.saveFrameButton.setToolTip(tr('tip_save_frame'))
        
        self.smartMarkButton.setToolTip(tr('tip_mark'))
        
        self.manageMarkersButton.setToolTip(tr('tip_manage_markers'))
        
        self.deleteMarkerButton.setToolTip(tr('tip_delete_marker'))
        
        self.clearMarkersButton.setToolTip(tr('tip_reset_markers'))
        
        if hasattr(self, 'thumbLabel'):
            self.thumbLabel.setText(tr('show_thumbnails'))
        if hasattr(self, 'fileNameLabel'):
            self.fileNameLabel.setText(tr('show_filenames'))
        if hasattr(self, 'thumbToggle'):
            self.thumbToggle.setOnText(tr('on'))
            self.thumbToggle.setOffText(tr('off'))
            self.thumbToggle.setToolTip(tr('tip_thumbnails'))
        if hasattr(self, 'fileNameToggle'):
            self.fileNameToggle.setOnText(tr('on'))
            self.fileNameToggle.setOffText(tr('off'))
            self.fileNameToggle.setToolTip(tr('tip_filenames'))
        if hasattr(self, 'playlistSettingsTitle'):
            self.playlistSettingsTitle.setText(tr('playlist'))
        if hasattr(self, 'thumbSizeLabel'):
            self.thumbSizeLabel.setText(tr('thumbnail_size'))
        if hasattr(self, 'update_thumb_size_btn_text'):
            self.update_thumb_size_btn_text()
        
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
        if hasattr(self, 'aboutButton'):
            self.aboutButton.setToolTip(tr('about'))
        
        self.toggleSettingsButton.setToolTip(tr('video_settings'))
        
        self.stepBackButton.setToolTip(tr('tip_prev_frame'))
        
        self.playButton.setToolTip(tr('tip_play_pause'))
        
        self.stepForwardButton.setToolTip(tr('tip_next_frame'))
        
        self.volumeButton.setToolTip(tr('tip_mute'))
        
        self.fullScreenButton.setToolTip(tr('tip_full_screen'))
        if hasattr(self, 'lockSyncToggle') and self.lockSyncToggle:
            self.lockSyncToggle.setToolTip(tr('tip_sync_lock'))
        
        self.syncFrameButton.setToolTip(tr('tip_sync_frame'))

        
        self.globalSettingsTitle.setText(tr('settings'))
        
        self.gsGeneralLabel.setText(tr('general'))
        
        if hasattr(self, 'gsShortcutsBtn'):
            self.gsShortcutsBtn.setText(tr('playback_shortcuts'))
        if hasattr(self, 'gsAboutBtn'):
            self.gsAboutBtn.setText(tr('about'))
        
        self.loopLabel.setText(tr('loop'))
        if hasattr(self, 'markersTitleLabel') and self.markersTitleLabel:
            self.markersTitleLabel.setText(tr('markers_title'))
        
        self.gsLangBtn.setText(tr('language'))
        
        self.gsAudioBtn.setText(tr('audio_device'))
        
        self.gsSaveBtn.setText(tr('save'))
        if hasattr(self, 'gsResetDefaultsBtn') and self.gsResetDefaultsBtn:
            self.gsResetDefaultsBtn.setText(tr('default'))

        
        self.gsAccentBtn.setText(tr('accent_color'))
        
        self.gsBgBtn.setText(tr('bg_color'))
        if hasattr(self, 'opacityTitleLabel') and self.opacityTitleLabel:
            self.opacityTitleLabel.setText(tr('panel_opacity'))
        if hasattr(self, 'opacitySlider') and self.opacitySlider:
            self.opacitySlider.setToolTip(tr('tip_panel_opacity'))
        
        if hasattr(self, 'zoomToLoopToggle') and self.zoomToLoopToggle:
            self.zoomToLoopToggle.setOnText(tr('on'))
            self.zoomToLoopToggle.setOffText(tr('off'))
        if hasattr(self, 'zoomToWindowToggle') and self.zoomToWindowToggle:
            self.zoomToWindowToggle.setOnText(tr('on'))
            self.zoomToWindowToggle.setOffText(tr('off'))

        # Update all SwitchButtons on/off Hungarian translations
        if hasattr(self, 'drawModeToggle') and self.drawModeToggle:
            self.drawModeToggle.setOnText(tr('on'))
            self.drawModeToggle.setOffText(tr('off'))
        if hasattr(self, 'laserModeToggle') and self.laserModeToggle:
            self.laserModeToggle.setOnText(tr('on'))
            self.laserModeToggle.setOffText(tr('off'))
        if hasattr(self, 'chronometerToggle') and self.chronometerToggle:
            self.chronometerToggle.setOnText(tr('on'))
            self.chronometerToggle.setOffText(tr('off'))
        if hasattr(self, 'lockSyncToggle') and self.lockSyncToggle:
            self.lockSyncToggle.setOnText(tr('on'))
            self.lockSyncToggle.setOffText(tr('off'))

        for lbl in getattr(self, 'shortcutLabels', []):
            lbl.setText(tr(lbl._label_key))

        # Update Subtitle Panel UI Texts
        if hasattr(self, 'subtitleTitle'):
            self.subtitleTitle.setText(tr('subtitles'))
        if hasattr(self, 'subEnableLabel'):
            self.subEnableLabel.setText(tr('enable_subtitles'))
        if hasattr(self, 'subEnableToggle'):
            self.subEnableToggle.setOnText(tr('on'))
            self.subEnableToggle.setOffText(tr('off'))
            self.subEnableToggle.setToolTip(tr('tip_enable_subtitles'))
        if hasattr(self, 'loadSubBtn'):
            self.loadSubBtn.setText(tr('load_subtitle_file'))
            self.loadSubBtn.setToolTip(tr('tip_load_subtitle'))
        if hasattr(self, 'subTrackCombo'):
            self.subTrackCombo.setItemText(0, tr('off'))
            for i in range(self.subTrackCombo.count()):
                if self.subTrackCombo.itemData(i) == -2:
                    self.subTrackCombo.setItemText(i, tr('load_subtitle_file'))
                    break
        if hasattr(self, 'styleTitleLabel'):
            self.styleTitleLabel.setText(tr('drawing_settings'))
        if hasattr(self, 'timingTitleLabel'):
            self.timingTitleLabel.setText(tr('sync_title'))
        if hasattr(self, 'subTextColorCombo'):
            color_keys = ['color_white', 'color_yellow', 'color_cyan', 'color_green', 'color_magenta', 'color_red']
            for i, key in enumerate(color_keys):
                if i < self.subTextColorCombo.count():
                    self.subTextColorCombo.setItemText(i, tr(key))
        if hasattr(self, 'subBgColorCombo'):
            bg_keys = ['color_black', 'color_dark_grey', 'color_navy_blue', 'color_none']
            for i, key in enumerate(bg_keys):
                if i < self.subBgColorCombo.count():
                    self.subBgColorCombo.setItemText(i, tr(key))

        # Update Audio Panel UI Texts
        if hasattr(self, 'audioTitle'):
            self.audioTitle.setText(tr('audio_settings'))
        if hasattr(self, 'audioEqLabel'):
            self.audioEqLabel.setText(tr('audio_eq_enable'))
        if hasattr(self, 'audioEqToggle'):
            self.audioEqToggle.setOnText(tr('on'))
            self.audioEqToggle.setOffText(tr('off'))
        if hasattr(self, 'audioEqPresetCombo'):
            preset_keys = [
                'preset_flat', 'preset_bass_boost', 'preset_treble_boost',
                'preset_vocal', 'preset_pop', 'preset_rock', 'preset_jazz', 'preset_classical'
            ]
            for i, key in enumerate(preset_keys):
                if i < self.audioEqPresetCombo.count():
                    self.audioEqPresetCombo.setItemText(i, tr(key))
        if hasattr(self, 'resetEqBtn'):
            self.resetEqBtn.setText(tr('reset_eq'))
        if hasattr(self, 'audioTrackCombo') and self.audioTrackCombo.count() > 0:
            if self.audioTrackCombo.itemData(0) == 0:
                self.audioTrackCombo.setItemText(0, tr('default'))
            elif self.audioTrackCombo.itemData(0) == -1:
                self.audioTrackCombo.setItemText(0, tr('off'))
