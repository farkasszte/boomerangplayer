from styles import get_styles

class StyleUIMixin:
    def refresh_custom_styles(self, accent_color=None, bg_color=None):
        """Updates all custom styled components when accent or background color changes."""
        if not accent_color:
            
            accent_color = self.config.get('accent_color', '#00f2ff')
        if not bg_color:
            
            bg_color = self.config.get('bg_color', '#202020')

        
        inverse_text = self.config.get('inverse_text', False)
        s = get_styles(accent_color, bg_color, inverse_text)
        fg_color = "#1c1c1c" if inverse_text else "#ffffff"
        border_color = "rgba(0, 0, 0, 0.35)" if inverse_text else "rgba(255, 255, 255, 0.1)"
        bg_translucent = "rgba(0, 0, 0, 0.04)" if inverse_text else "rgba(255, 255, 255, 0.05)"
        bg_hover = "rgba(0, 0, 0, 0.08)" if inverse_text else "rgba(255, 255, 255, 0.1)"
        bg_pressed = "rgba(0, 0, 0, 0.02)" if inverse_text else "rgba(255, 255, 255, 0.03)"

        # Update main UI elements
        sliders = ['progressBar', 'penSizeSlider', 'speedSlider', 'zoomSlider', 'cacheSlider', 'qvSlider',
                   'brightnessSlider', 'contrastSlider', 'gammaSlider', 'saturationSlider', 'opacitySlider']
        for slider_name in sliders:
            if hasattr(self, slider_name):
                slider = getattr(self, slider_name)
                slider.setStyleSheet(s['FLUENT_SLIDER_STYLE'])
        
        # Tool buttons
        tool_btns = ['penTool', 'lineTool', 'arrowTool', 'textTool', 'rectTool', 
                     'ellipseTool', 'triangleTool', 'objEraserTool', 'areaEraserTool', 'measureTool']
        for btn_name in tool_btns:
            if hasattr(self, btn_name):
                btn = getattr(self, btn_name)
                btn.setStyleSheet(s['TOOL_BTN_STYLE'])
        
        # Action buttons
        action_btns = ['saveScreenshotBtn', 'sidebarUndoBtn', 'sidebarClearBtn', 'gsSaveBtn', 'gsResetDefaultsBtn', 'thumbSizeBtn',
                       'syncFrameButton', 'saveLoopButton', 'saveFrameButton', 'mirrorButton', 
                       'mirrorVerticalButton', 'rotateLeftButton', 'rotateRightButton', 'resetAdjButton', 'infoButton',
                       'smartMarkButton', 'manageMarkersButton', 'deleteMarkerButton', 'clearMarkersButton',
                       'penColorBtn', 'btn_add', 'btn_sort', 'btn_save', 'btn_clear']
        for btn_name in action_btns:
            if hasattr(self, btn_name):
                btn = getattr(self, btn_name)
                btn.setStyleSheet(s['ACTION_BTN_STYLE'])

        # Menus
        menus = ['addMenu', 'sortMenu', 'removeMenu']
        for menu_name in menus:
            if hasattr(self, menu_name):
                menu = getattr(self, menu_name)
                menu.setStyleSheet(s['MENU_STYLE'])

        # Playback buttons
        pb_btns = ['stepBackButton', 'playBackwardButton', 'playButton', 'stepForwardButton']
        for btn_name in pb_btns:
            if hasattr(self, btn_name):
                btn = getattr(self, btn_name)
                # COMPACT_BTN_STYLE needs specific rounding for ends
                style = s['COMPACT_BTN_STYLE']
                if btn_name == 'stepBackButton':
                    style += "ToolButton { border-top-left-radius: 4px; border-bottom-left-radius: 4px; }"
                elif btn_name == 'stepForwardButton':
                    style += f"ToolButton {{ border-right: 1px solid {border_color}; border-top-right-radius: 4px; border-bottom-right-radius: 4px; }}"
                btn.setStyleSheet(style)

        # Controls card bottom row tool buttons styling
        cc_btns = ['toggleSettingsButton', 'globalSettingsButton', 'fullScreenButton', 
                   'volumeButton', 'togglePlaylistButton', 'toggleDrawingButton']
        for btn_name in cc_btns:
            if hasattr(self, btn_name):
                btn = getattr(self, btn_name)
                btn.setFixedSize(32, 32)
                btn.setStyleSheet(f"""
                    ToolButton {{
                        border: 1px solid {border_color};
                        border-radius: 4px;
                        background: {bg_translucent};
                        color: {fg_color};
                        min-width: 32px;
                        min-height: 32px;
                    }}
                    ToolButton:hover {{
                        background: {bg_hover};
                    }}
                    ToolButton:pressed {{
                        background: {bg_pressed};
                    }}
                """)

        # Regenerate controls card play/pause icons
        if hasattr(self, 'flippedPlayIcon'):
            from qfluentwidgets import FluentIcon
            from PyQt6.QtGui import QPixmap, QIcon
            from PyQt6.QtCore import QSize
            play_pixmap = FluentIcon.PLAY.icon().pixmap(QSize(24, 24))
            flipped_play_pixmap = QPixmap.fromImage(play_pixmap.toImage().mirrored(True, False))
            self.flippedPlayIcon = QIcon(flipped_play_pixmap)
            self.normalPlayIcon = FluentIcon.PLAY.icon()
            self.pauseIcon = FluentIcon.PAUSE.icon()

        if hasattr(self, 'update_play_icons'):
            self.update_play_icons()

        # Regenerate and apply controls card icons
        if hasattr(self, 'toggleSettingsButton'):
            from qfluentwidgets import FluentIcon
            icons_map = {
                'toggleSettingsButton': FluentIcon.VIDEO,
                'globalSettingsButton': FluentIcon.SETTING,
                'stepBackButton': FluentIcon.LEFT_ARROW,
                'stepForwardButton': FluentIcon.RIGHT_ARROW,
                'fullScreenButton': FluentIcon.FULL_SCREEN,
                'togglePlaylistButton': FluentIcon.MENU,
                'toggleDrawingButton': FluentIcon.EDIT,
            }
            for btn_name, icon in icons_map.items():
                if hasattr(self, btn_name):
                    getattr(self, btn_name).setIcon(icon)
            
            if hasattr(self, 'volumeButton'):
                if getattr(self, 'userMutedIntent', False):
                    
                    self.volumeButton.setIcon(FluentIcon.MUTE)
                else:
                    
                    self.volumeButton.setIcon(FluentIcon.VOLUME)

        # Update palette border in drawing mixin if it exists
        if hasattr(self, 'paletteButtons') and hasattr(self, 'update_palette_ui'):
            self.update_palette_ui()

        # Update ComboBox
        if hasattr(self, 'loopCombo'):
            self.loopCombo.setStyleSheet(s['COMBO_STYLE'])

        # Update SpinBoxes
        spinboxes = ['speedValueLabel', 'zoomValueLabel', 'cacheValueLabel', 'qvValueSpinBox',
                     'brightnessSpinBox', 'contrastSpinBox', 'gammaSpinBox', 'saturationSpinBox',
                     'penSizeLabel']
        for spin_name in spinboxes:
            if hasattr(self, spin_name):
                spin = getattr(self, spin_name)
                spin.setStyleSheet(s['SPINBOX_STYLE'])

        # Update SwitchButtons
        switches = ['navToggle', 'gsGPUToggle', 'thumbToggle', 'fileNameToggle', 'laserModeToggle', 'chronometerToggle', 'drawModeToggle', 'lockSyncToggle']
        for sw_name in switches:
            if hasattr(self, sw_name):
                sw = getattr(self, sw_name)
                # Apply SWITCH_STYLE
                sw.setStyleSheet(s['SWITCH_STYLE'])

        # Update Global Settings Trigger buttons
        gs_btns = ['gsLangBtn', 'gsAudioBtn', 'gsAccentBtn', 'gsBgBtn']
        for btn_name in gs_btns:
            if hasattr(self, btn_name):
                btn = getattr(self, btn_name)
                btn.setStyleSheet(s['TRIGGER_STYLE'])

        if hasattr(self, 'chronoTimeLabel') and self.chronoTimeLabel:
            self.chronoTimeLabel.setStyleSheet(f"font-size: 26px; font-weight: bold; font-family: 'Segoe UI Semibold', 'Courier New'; color: {accent_color};")
        if hasattr(self, 'chronoSectionLabel') and self.chronoSectionLabel:
            self.chronoSectionLabel.setStyleSheet(f"font-size: 12px; color: {fg_color}; line-height: 140%;")
        if hasattr(self, 'chronoPositionLabel') and self.chronoPositionLabel:
            self.chronoPositionLabel.setStyleSheet(f"font-size: 12px; color: {fg_color}; line-height: 140%;")

        # Update pen color label
        if hasattr(self, 'penSizeLabel'):
            from PyQt6.QtWidgets import QLabel
            if isinstance(self.penSizeLabel, QLabel):
                self.penSizeLabel.setStyleSheet(
                    f"color: {fg_color}; font-size: 13px; font-weight: 500; "
                    "background: transparent; border: none !important;"
                )

        # Update first three rows text of drawing panel
        for label_name in ['drawModeToggleLabel', 'laserModeToggleLabel', 'chronometerToggleLabel']:
            if hasattr(self, label_name):
                lbl = getattr(self, label_name)
                lbl.setStyleSheet(f"color: {fg_color}; font-size: 13px;")

        # Update Sidebar Titles and Category Labels
        titles = ['settingsTitle', 'globalSettingsTitle', 'drawingSidebarTitle', 'playlistLabel']
        for t_name in titles:
            if hasattr(self, t_name):
                getattr(self, t_name).setStyleSheet(s['TITLE_STYLE'])
        
        captions = ['gsGeneralLabel', 'gsShortcutsLabel']
        for c_name in captions:
            if hasattr(self, c_name):
                getattr(self, c_name).setStyleSheet(s['CAPTION_STYLE'])

        # Convert hex background color to rgb
        def hex_to_rgb(hex_color):
            hex_color = hex_color.lstrip('#')
            return ",".join([str(int(hex_color[i:i+2], 16)) for i in (0, 2, 4)])

        
        opacity = getattr(self, 'pending_panel_opacity', self.config.get('panel_opacity', 100))
         ignore [unsupported-operation]
        opacity_float = opacity / 100.0
        rgb_bg = hex_to_rgb(bg_color)
        transparent_bg_style = f"background-color: rgba({rgb_bg}, {opacity_float}); border: none;"

        # Update Background Colors
        # Main window (PlayerWindow)
        
        self.setStyleSheet(f"PlayerWindow {{ background-color: {bg_color}; }}")
        
        # Title bar
        if hasattr(self, 'titleBar'):
            self.titleBar.setStyleSheet(f"background-color: {bg_color}; border: none;")
            
        # Set playerInterface background to black so transparent sidebars and controlsCard show high-contrast glass effect
        if hasattr(self, 'playerInterface'):
            self.playerInterface.setStyleSheet(f"QWidget#playerInterface {{ background-color: black; }}")
            
        # Set mainSplitter background to transparent
        if hasattr(self, 'mainSplitter'):
            self.mainSplitter.setStyleSheet(
                "QSplitter { background-color: transparent; } QSplitter::handle { background: transparent; }"
            )
            
        # Controls card (Footer)
        if hasattr(self, 'controlsCard'):
            self.controlsCard.setStyleSheet(transparent_bg_style)
            
        # Sidebars
        sidebar_containers = ['settingsContainer', 'globalSettingsContainer', 
                              'drawingContainer', 'playlistContainer']
        for container_name in sidebar_containers:
            if hasattr(self, container_name):
                if container_name == 'drawingContainer':
                    getattr(self, container_name).setStyleSheet(
                        f"background-color: rgba({rgb_bg}, {opacity_float}); border: none; QScrollBar {{ width: 0px; height: 0px; }}"
                    )
                else:
                    getattr(self, container_name).setStyleSheet(transparent_bg_style)
                
        # Drawing scroll area and widget
        if hasattr(self, 'drawingScrollWidget'):
            self.drawingScrollWidget.setStyleSheet("background: transparent;")
        if hasattr(self, 'drawingScrollArea'):
            self.drawingScrollArea.setStyleSheet("background: transparent; border: none;")
            
        # Settings scroll widget
        if hasattr(self, 'settingsScrollWidget'):
            self.settingsScrollWidget.setStyleSheet("background: transparent;")
        if hasattr(self, 'gsScrollWidget'):
            self.gsScrollWidget.setStyleSheet("background: transparent;")

        # Playlist list selection style
        if hasattr(self, '_update_playlist_list_stylesheet'):
            self._update_playlist_list_stylesheet()

        if hasattr(self, 'update_sync_lock_button_style'):
            self.update_sync_lock_button_style()

        if hasattr(self, 'update_lock_icon'):
            self.update_lock_icon()
