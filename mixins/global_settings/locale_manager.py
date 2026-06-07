from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtWidgets import QMenu
from translations import tr, set_lang
from styles import get_styles

class GlobalSettingsLocaleManagerMixin:
    def show_language_menu(self):
        # pyrefly: ignore [no-matching-overload]
        menu = QMenu(parent=self)
        menu.setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # pyrefly: ignore [missing-attribute]
        accent = self.config.get('accent_color', '#00f2ff')
        # pyrefly: ignore [missing-attribute]
        bg_color = self.config.get('bg_color', '#202020')
        style = get_styles(accent, bg_color)['MENU_POPUP_STYLE']
        menu.setStyleSheet(style)

        # pyrefly: ignore [missing-attribute]
        current_lang = self.config.get('language', 'en')

        en_action = menu.addAction(tr('lang_en'))
        # pyrefly: ignore [missing-attribute]
        en_action.setCheckable(True)
        # pyrefly: ignore [missing-attribute]
        en_action.setChecked(current_lang == 'en')
        # pyrefly: ignore [missing-attribute]
        en_action.triggered.connect(lambda: self.on_language_changed_sidebar(0))

        hu_action = menu.addAction(tr('lang_hu'))
        # pyrefly: ignore [missing-attribute]
        hu_action.setCheckable(True)
        # pyrefly: ignore [missing-attribute]
        hu_action.setChecked(current_lang == 'hu')
        # pyrefly: ignore [missing-attribute]
        hu_action.triggered.connect(lambda: self.on_language_changed_sidebar(1))

        # pyrefly: ignore [missing-attribute]
        pos = self.gsLangBtn.mapToGlobal(QPoint(0, self.gsLangBtn.height()))
        menu.exec(pos)

    def on_language_changed_sidebar(self, idx):
        lang = 'en' if idx == 0 else 'hu'
        # pyrefly: ignore [missing-attribute]
        self.config['language'] = lang
        set_lang(lang)
        self.update_ui_texts()

    def update_ui_texts(self):
        # pyrefly: ignore [missing-attribute]
        self.playlistLabel.setText(tr('playlist'))
        # pyrefly: ignore [missing-attribute]
        self.thumbLabel.setText(tr('show_thumbnails'))
        # pyrefly: ignore [missing-attribute]
        self.fileNameLabel.setText(tr('show_filenames'))
        # pyrefly: ignore [missing-attribute]
        self.btn_add.setText(tr('add'))
        # pyrefly: ignore [missing-attribute]
        self.btn_sort.setText(tr('sort'))
        # pyrefly: ignore [missing-attribute]
        self.btn_save.setText(tr('save'))
        # pyrefly: ignore [missing-attribute]
        self.btn_clear.setText(tr('clear'))
        # pyrefly: ignore [missing-attribute]
        self.drawingSidebarTitle.setText(tr('drawing_settings'))
        # pyrefly: ignore [missing-attribute]
        self.drawModeToggleLabel.setText(tr('drawing_mode'))
        # pyrefly: ignore [missing-attribute]
        self.laserModeToggleLabel.setText(tr('laser_mode'))
        # pyrefly: ignore [missing-attribute]
        if hasattr(self, 'penSizeLabel') and self.penSizeLabel:
            from PyQt6.QtWidgets import QLabel
            if isinstance(self.penSizeLabel, QLabel):
                self.penSizeLabel.setText(f"{self.penSizeSlider.value()} px")
            else:
                self.penSizeLabel.blockSignals(True)
                self.penSizeLabel.setValue(self.penSizeSlider.value())
                self.penSizeLabel.blockSignals(False)
        # pyrefly: ignore [missing-attribute]
        self.penColorBtn.setText(tr('color'))
        # pyrefly: ignore [missing-attribute]
        self.paletteTitle.setText(tr('color_palette'))
        # pyrefly: ignore [missing-attribute]
        self.saveScreenshotBtn.setText(tr('save_screenshot'))
        # pyrefly: ignore [missing-attribute]
        self.sidebarUndoBtn.setText(tr('undo'))
        # pyrefly: ignore [missing-attribute]
        self.sidebarClearBtn.setText(tr('clear'))
        # pyrefly: ignore [missing-attribute]
        self.settingsTitle.setText(tr('video_settings'))
        if hasattr(self, 'playbackLabel'):
            self.playbackLabel.setText(tr('playback'))
        # pyrefly: ignore [missing-attribute]
        self.speedLabel.setText(tr('playback_speed'))
        # pyrefly: ignore [missing-attribute]
        self.zoomLabel.setText(tr('zoom'))
        # pyrefly: ignore [missing-attribute]
        self.cacheLabel.setText(tr('cache_window'))
        # pyrefly: ignore [missing-attribute]
        self.adjLabel.setText(tr('image_adjustments'))
        # pyrefly: ignore [missing-attribute]
        self.resetAdjButton.setText(tr('reset_image'))
        # pyrefly: ignore [missing-attribute]
        self.infoButton.setText(tr('file_info'))
        # pyrefly: ignore [missing-attribute]
        self.loopLabel.setText(tr('loop'))
        # pyrefly: ignore [missing-attribute]
        self.navLabel.setText(tr('zoom_nav_bar'))
        if hasattr(self, 'chronometerToggleLabel'):
            self.chronometerToggleLabel.setText(tr('chronometer_overlay'))
        # pyrefly: ignore [missing-attribute]
        self.smartMarkButton.setText(tr('mark'))
        # pyrefly: ignore [missing-attribute]
        self.deleteMarkerButton.setText(tr('delete'))
        # pyrefly: ignore [missing-attribute]
        self.clearMarkersButton.setText(tr('reset'))
        if hasattr(self, 'manageMarkersButton') and self.manageMarkersButton:
            # pyrefly: ignore [missing-attribute]
            count = len(self.markers)
            self.manageMarkersButton.setText(f"{tr('manage_markers')} ({count})")
        if hasattr(self, 'syncLabel'):
            self.syncLabel.setText(tr('sync_title'))
        if hasattr(self, 'syncLockLabel') and self.syncLockLabel:
            self.syncLockLabel.setText(tr('sync_lock'))
        if hasattr(self, 'syncFrameButton'):
            self.syncFrameButton.setText(tr('sync_frame'))
        # pyrefly: ignore [missing-attribute]
        self.saveLoopButton.setText(tr('save_loop'))
        # pyrefly: ignore [missing-attribute]
        self.saveFrameButton.setText(tr('save_frame'))
        # pyrefly: ignore [missing-attribute]
        self.mirrorButton.setText(tr('mirror_h'))
        # pyrefly: ignore [missing-attribute]
        self.mirrorVerticalButton.setText(tr('mirror_v'))
        if hasattr(self, 'rotateLeftButton'):
            self.rotateLeftButton.setText(tr('rotate_left'))
        if hasattr(self, 'rotateRightButton'):
            self.rotateRightButton.setText(tr('rotate_right'))
        # pyrefly: ignore [missing-attribute]
        self.globalSettingsButton.setToolTip(tr('settings'))
        # pyrefly: ignore [missing-attribute]
        self.toggleSettingsButton.setToolTip(tr('video_settings'))
        # pyrefly: ignore [missing-attribute]
        self.loadingOverlay.setText(tr('caching'))

        # pyrefly: ignore [missing-attribute]
        idx = self.loopCombo.currentIndex()
        # pyrefly: ignore [missing-attribute]
        self.loopCombo.clear()
        # pyrefly: ignore [missing-attribute]
        self.loopCombo.addItems([tr('loop_none'), tr('loop_forward'), tr('loop_backward'), tr('loop_pingpong')])
        # pyrefly: ignore [missing-attribute]
        self.loopCombo.setCurrentIndex(idx)

        # pyrefly: ignore [missing-attribute]
        self.addMenu.clear()
        # pyrefly: ignore [missing-attribute]
        self.addMenu.addAction(tr('add_media'), self.open_file)
        # pyrefly: ignore [missing-attribute]
        self.addMenu.addAction(tr('add_video_folder'), lambda: self.add_folder_contents(type="video"))
        # pyrefly: ignore [missing-attribute]
        self.addMenu.addAction(tr('add_image_folder'), lambda: self.add_folder_contents(type="image"))

        # pyrefly: ignore [missing-attribute]
        self.sortMenu.clear()
        # pyrefly: ignore [missing-attribute]
        self.sortMenu.addAction(tr('sort_name_asc'),    lambda: self.sort_playlist_by("name_asc"))
        # pyrefly: ignore [missing-attribute]
        self.sortMenu.addAction(tr('sort_name_desc'),   lambda: self.sort_playlist_by("name_desc"))
        # pyrefly: ignore [missing-attribute]
        self.sortMenu.addAction(tr('sort_date_newest'), lambda: self.sort_playlist_by("date_newest"))
        # pyrefly: ignore [missing-attribute]
        self.sortMenu.addAction(tr('sort_date_oldest'), lambda: self.sort_playlist_by("date_oldest"))

        # pyrefly: ignore [missing-attribute]
        self.removeMenu.clear()
        # pyrefly: ignore [missing-attribute]
        self.removeMenu.addAction(tr('remove_selected'), self.remove_from_playlist)
        # pyrefly: ignore [missing-attribute]
        self.removeMenu.addAction(tr('clear_all'),       self.clear_playlist)

        # pyrefly: ignore [missing-attribute]
        self.brightnessLabel.setText(tr('brightness'))
        # pyrefly: ignore [missing-attribute]
        self.contrastLabel.setText(tr('contrast'))
        # pyrefly: ignore [missing-attribute]
        self.gammaLabel.setText(tr('gamma'))
        # pyrefly: ignore [missing-attribute]
        self.saturationLabel.setText(tr('saturation'))

        # pyrefly: ignore [missing-attribute]
        self.update_loop_frames_label()

        # pyrefly: ignore [missing-attribute]
        self.btn_add.setToolTip(tr('tip_add'))
        # pyrefly: ignore [missing-attribute]
        self.btn_sort.setToolTip(tr('tip_sort'))
        # pyrefly: ignore [missing-attribute]
        self.btn_save.setToolTip(tr('tip_save'))
        # pyrefly: ignore [missing-attribute]
        self.btn_clear.setToolTip(tr('tip_clear'))
        # pyrefly: ignore [missing-attribute]
        self.penColorBtn.setToolTip(tr('tip_color'))
        # pyrefly: ignore [missing-attribute]
        self.speedSlider.setToolTip(tr('tip_playback_speed'))
        if hasattr(self, 'speedLockBtn') and self.speedLockBtn:
            # pyrefly: ignore [missing-attribute]
            if getattr(self, 'isSpeedLocked', False):
                self.speedLockBtn.setToolTip(tr('tip_speed_locked'))
            else:
                self.speedLockBtn.setToolTip(tr('tip_speed_unlocked'))
        # pyrefly: ignore [missing-attribute]
        self.zoomSlider.setToolTip(tr('tip_zoom'))
        # pyrefly: ignore [missing-attribute]
        self.cacheSlider.setToolTip(tr('tip_cache_window'))
        # pyrefly: ignore [missing-attribute]
        self.brightnessSlider.setToolTip(tr('tip_brightness'))
        # pyrefly: ignore [missing-attribute]
        self.contrastSlider.setToolTip(tr('tip_contrast'))
        # pyrefly: ignore [missing-attribute]
        self.gammaSlider.setToolTip(tr('tip_gamma'))
        # pyrefly: ignore [missing-attribute]
        self.saturationSlider.setToolTip(tr('tip_saturation'))
        # pyrefly: ignore [missing-attribute]
        self.mirrorButton.setToolTip(tr('tip_mirror_h'))
        # pyrefly: ignore [missing-attribute]
        self.mirrorVerticalButton.setToolTip(tr('tip_mirror_v'))
        if hasattr(self, 'rotateLeftButton'):
            self.rotateLeftButton.setToolTip(tr('tip_rotate_left'))
        if hasattr(self, 'rotateRightButton'):
            self.rotateRightButton.setToolTip(tr('tip_rotate_right'))
        # pyrefly: ignore [missing-attribute]
        self.resetAdjButton.setToolTip(tr('tip_reset_image'))
        # pyrefly: ignore [missing-attribute]
        self.infoButton.setToolTip(tr('tip_file_info'))
        # pyrefly: ignore [missing-attribute]
        self.navToggle.setToolTip(tr('tip_zoom_nav_bar'))
        # pyrefly: ignore [missing-attribute]
        self.loopCombo.setToolTip(tr('tip_loop_mode'))
        # pyrefly: ignore [missing-attribute]
        self.saveLoopButton.setToolTip(tr('tip_save_loop'))
        # pyrefly: ignore [missing-attribute]
        self.saveFrameButton.setToolTip(tr('tip_save_frame'))
        # pyrefly: ignore [missing-attribute]
        self.smartMarkButton.setToolTip(tr('tip_mark'))
        # pyrefly: ignore [missing-attribute]
        self.manageMarkersButton.setToolTip(tr('tip_manage_markers'))
        # pyrefly: ignore [missing-attribute]
        self.deleteMarkerButton.setToolTip(tr('tip_delete_marker'))
        # pyrefly: ignore [missing-attribute]
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
        # pyrefly: ignore [missing-attribute]
        self.penTool.setText(tr('pen'))
        # pyrefly: ignore [missing-attribute]
        self.lineTool.setText(tr('line'))
        # pyrefly: ignore [missing-attribute]
        self.arrowTool.setText(tr('arrow'))
        # pyrefly: ignore [missing-attribute]
        self.textTool.setText(tr('text'))
        # pyrefly: ignore [missing-attribute]
        self.rectTool.setText(tr('rect'))
        # pyrefly: ignore [missing-attribute]
        self.ellipseTool.setText(tr('ellipse'))
        # pyrefly: ignore [missing-attribute]
        self.triangleTool.setText(tr('triangle'))
        # pyrefly: ignore [missing-attribute]
        self.objEraserTool.setText(tr('obj_eraser'))
        # pyrefly: ignore [missing-attribute]
        self.areaEraserTool.setText(tr('area_eraser'))
        # pyrefly: ignore [missing-attribute]
        self.measureTool.setText(tr('measure'))

        # pyrefly: ignore [missing-attribute]
        self.penTool.setToolTip(tr('tip_pen'))
        # pyrefly: ignore [missing-attribute]
        self.lineTool.setToolTip(tr('tip_line'))
        # pyrefly: ignore [missing-attribute]
        self.arrowTool.setToolTip(tr('tip_arrow'))
        # pyrefly: ignore [missing-attribute]
        self.textTool.setToolTip(tr('tip_text'))
        # pyrefly: ignore [missing-attribute]
        self.rectTool.setToolTip(tr('tip_rect'))
        # pyrefly: ignore [missing-attribute]
        self.ellipseTool.setToolTip(tr('tip_ellipse'))
        # pyrefly: ignore [missing-attribute]
        self.triangleTool.setToolTip(tr('tip_triangle'))
        # pyrefly: ignore [missing-attribute]
        self.objEraserTool.setToolTip(tr('tip_obj_eraser'))
        # pyrefly: ignore [missing-attribute]
        self.areaEraserTool.setToolTip(tr('tip_area_eraser'))
        # pyrefly: ignore [missing-attribute]
        self.measureTool.setToolTip(tr('tip_measure'))
        # pyrefly: ignore [missing-attribute]
        self.sidebarUndoBtn.setToolTip(tr('tip_undo'))
        # pyrefly: ignore [missing-attribute]
        self.sidebarClearBtn.setToolTip(tr('tip_clear_draw'))
        # pyrefly: ignore [missing-attribute]
        self.saveScreenshotBtn.setToolTip(tr('tip_screenshot'))
        # pyrefly: ignore [missing-attribute]
        self.togglePlaylistButton.setToolTip(tr('tip_playlist'))
        # pyrefly: ignore [missing-attribute]
        self.toggleDrawingButton.setToolTip(tr('tip_drawing'))
        # pyrefly: ignore [missing-attribute]
        self.globalSettingsButton.setToolTip(tr('tip_settings'))
        # pyrefly: ignore [missing-attribute]
        self.toggleSettingsButton.setToolTip(tr('video_settings'))
        # pyrefly: ignore [missing-attribute]
        self.stepBackButton.setToolTip(tr('tip_prev_frame'))
        # pyrefly: ignore [missing-attribute]
        self.playButton.setToolTip(tr('tip_play_pause'))
        # pyrefly: ignore [missing-attribute]
        self.stepForwardButton.setToolTip(tr('tip_next_frame'))
        # pyrefly: ignore [missing-attribute]
        self.volumeButton.setToolTip(tr('tip_mute'))
        # pyrefly: ignore [missing-attribute]
        self.fullScreenButton.setToolTip(tr('tip_full_screen'))
        if hasattr(self, 'lockSyncToggle') and self.lockSyncToggle:
            self.lockSyncToggle.setToolTip(tr('tip_sync_lock'))
        # pyrefly: ignore [missing-attribute]
        self.syncFrameButton.setToolTip(tr('tip_sync_frame'))

        # pyrefly: ignore [missing-attribute]
        self.globalSettingsTitle.setText(tr('settings'))
        # pyrefly: ignore [missing-attribute]
        self.gsGeneralLabel.setText(tr('general'))
        # pyrefly: ignore [missing-attribute]
        self.gsShortcutsLabel.setText(tr('playback_shortcuts'))
        # pyrefly: ignore [missing-attribute]
        self.loopLabel.setText(tr('loop'))
        if hasattr(self, 'markersTitleLabel') and self.markersTitleLabel:
            self.markersTitleLabel.setText(tr('markers_title'))
        # pyrefly: ignore [missing-attribute]
        self.gsLangBtn.setText(tr('language'))
        # pyrefly: ignore [missing-attribute]
        self.gsAudioBtn.setText(tr('audio_device'))
        # pyrefly: ignore [missing-attribute]
        self.gsSaveBtn.setText(tr('save'))
        if hasattr(self, 'gsResetDefaultsBtn') and self.gsResetDefaultsBtn:
            self.gsResetDefaultsBtn.setText(tr('default'))

        # pyrefly: ignore [missing-attribute]
        self.gsAccentBtn.setText(tr('accent_color'))
        # pyrefly: ignore [missing-attribute]
        self.gsBgBtn.setText(tr('bg_color'))
        if hasattr(self, 'opacityTitleLabel') and self.opacityTitleLabel:
            self.opacityTitleLabel.setText(tr('panel_opacity'))
        if hasattr(self, 'opacitySlider') and self.opacitySlider:
            self.opacitySlider.setToolTip(tr('tip_panel_opacity'))
        # pyrefly: ignore [missing-attribute]
        self.navToggle.setOnText(tr('on'))
        # pyrefly: ignore [missing-attribute]
        self.navToggle.setOffText(tr('off'))

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
