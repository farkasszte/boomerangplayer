import ctypes
from PyQt6.QtCore import Qt

class FullscreenUIMixin:
    def toggle_full_screen(self):
        self.is_full_screen = not self.is_full_screen
        
        if self.is_full_screen:
            # Entering Full Screen
            # Save exact window state and geometry before entering fullscreen
            self.window_state_before_fs = self.windowState()
            self.geometry_before_fs = self.geometry()
            
            # Save sidebar states
            self.sidebar_states_before_fs = {
                'playlist': self.playlistContainer.isVisible(),
                'drawing': self.drawingContainer.isVisible(),
                'settings': self.settingsContainer.isVisible(),
                'global_settings': self.globalSettingsContainer.isVisible(),
                'subtitle': hasattr(self, 'subtitleContainer') and self.subtitleContainer.isVisible(),
                'audio': hasattr(self, 'audioContainer') and self.audioContainer.isVisible()
            }
            self.sidebars_hidden_by_controls = self.sidebar_states_before_fs.copy()
            
            # Hide everything extra
            self.playlistContainer.hide()
            self.drawingContainer.hide()
            self.settingsContainer.hide()
            self.globalSettingsContainer.hide()
            if hasattr(self, 'subtitleContainer'):
                self.subtitleContainer.hide()
            if hasattr(self, 'audioContainer'):
                self.audioContainer.hide()
            
            if hasattr(self, 'titleBar'):
                self.titleBar.hide()
            
            # Remove header margin
            if hasattr(self, 'widgetLayout'):
                self.widgetLayout.setContentsMargins(0, 0, 0, 0)
            
            # Disable rounded corners and ensure black background to prevent leaks
            self.setStyleSheet("PlayerWindow { border-radius: 0px; border: none; background: black; }")
            if hasattr(self, 'stackedWidget'):
                self.stackedWidget.setStyleSheet("border-radius: 0px; margin: 0px; padding: 0px;")
            if hasattr(self, 'playerInterface'):
                self.playerInterface.setStyleSheet("border-radius: 0px; margin: 0px; padding: 0px;")
            
            # Windows 11: Disable rounded corners via DWM
            try:
                DWMWA_WINDOW_CORNER_PREFERENCE = 33
                DWMWCP_DONOTROUND = 1
                
                hwnd = int(self.winId())
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
                    ctypes.byref(ctypes.c_int(DWMWCP_DONOTROUND)), 
                    ctypes.sizeof(ctypes.c_int)
                )
            except:
                pass
            
            # Remove controlsCard from layout to overlay it on top of the fullscreen window
            if hasattr(self, 'playerLayout') and hasattr(self, 'controlsCard'):
                self.playerLayout.removeWidget(self.controlsCard)
                self.controlsCard.setParent(self)
                self.controlsCard.show()
                self.controlsCard.raise_()
                h = max(80, self.controlsCard.sizeHint().height())
                self.controlsCard.setGeometry(0, self.height() - h, self.width(), h)

            self.showFullScreen()
            
            # Full screen mode: hide panel immediately if mouse is not on it, otherwise show and start timer
            if hasattr(self, 'controlsCard') and self.controlsCard.underMouse():
                if hasattr(self, 'show_controls'):
                    self.show_controls()
            else:
                if hasattr(self, 'controlsCard'):
                    self.controlsCard.hide()
                # If we hid the panel immediately, we should also hide the mouse cursor immediately
                if hasattr(self, 'view') and not getattr(self.view, 'drawing_mode', False):
                    self.setCursor(Qt.CursorShape.BlankCursor)
                    self.view.setCursor(Qt.CursorShape.BlankCursor)
        else:
            # Exiting Full Screen
            # Hide the window transition flash using opacity
            self.setWindowOpacity(0.0)
            
            # Windows 11: Restore rounded corners (default behavior)
            try:
                DWMWA_WINDOW_CORNER_PREFERENCE = 33
                DWMWCP_DEFAULT = 0
                
                hwnd = int(self.winId())
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
                    ctypes.byref(ctypes.c_int(DWMWCP_DEFAULT)), 
                    ctypes.sizeof(ctypes.c_int)
                )
            except:
                pass
            
            # Restore styles (default for FluentWindow)
            if hasattr(self, 'stackedWidget'):
                self.stackedWidget.setStyleSheet("")
            if hasattr(self, 'playerInterface'):
                self.playerInterface.setStyleSheet("")
                
            if hasattr(self, 'refresh_custom_styles'):
                self.refresh_custom_styles()
            
            if hasattr(self, 'titleBar'):
                self.titleBar.show()
                
            # Restore header margin
            if hasattr(self, 'widgetLayout'):
                self.widgetLayout.setContentsMargins(0, 32, 0, 0)
                
            # Restore saved window state or default to Maximized
            if hasattr(self, 'window_state_before_fs') and self.window_state_before_fs is not None:
                if self.window_state_before_fs & Qt.WindowState.WindowMaximized:
                    self.showMaximized()
                else:
                    self.showNormal()
                    if hasattr(self, 'geometry_before_fs') and self.geometry_before_fs is not None:
                        self.setGeometry(self.geometry_before_fs)
            else:
                self.showMaximized()
                
            # Restore sidebars based on what was visible in fullscreen before they auto-hid, or what was visible before entering fullscreen
            if getattr(self, 'sidebars_hidden_by_controls', None) is not None:
                restore_states = self.sidebars_hidden_by_controls
            else:
                restore_states = {
                    'playlist': self.playlistContainer.isVisible(),
                    'drawing': self.drawingContainer.isVisible(),
                    'settings': self.settingsContainer.isVisible(),
                    'global_settings': self.globalSettingsContainer.isVisible(),
                    'subtitle': hasattr(self, 'subtitleContainer') and self.subtitleContainer.isVisible(),
                    'audio': hasattr(self, 'audioContainer') and self.audioContainer.isVisible()
                }

            if restore_states.get('playlist'):
                self.playlistContainer.show()
            if restore_states.get('drawing'):
                self.drawingContainer.show()
            if restore_states.get('settings'):
                self.settingsContainer.show()
            if restore_states.get('global_settings'):
                self.globalSettingsContainer.show()
            if restore_states.get('subtitle') and hasattr(self, 'subtitleContainer'):
                self.subtitleContainer.show()
            if restore_states.get('audio') and hasattr(self, 'audioContainer'):
                self.audioContainer.show()

            self.sidebars_hidden_by_controls = None

            # Ensure controls are shown and timer is stopped when exiting fullscreen
            if hasattr(self, 'controls_timer'):
                self.controls_timer.stop()
            
            # Restore parent and add controlsCard back into self.playerLayout
            if hasattr(self, 'playerLayout') and hasattr(self, 'controlsCard'):
                self.controlsCard.setParent(self.playerInterface)
                self.playerLayout.addWidget(self.controlsCard, stretch=0)
                self.controlsCard.show()

            # Restore mouse cursor
            if hasattr(self, 'view') and not getattr(self.view, 'drawing_mode', False):
                self.setCursor(Qt.CursorShape.ArrowCursor)
                self.view.setCursor(Qt.CursorShape.ArrowCursor)
                
            # Restore opacity smoothly after a short delay to completely hide OS window frame recreation flashes
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(150, lambda: self.setWindowOpacity(1.0))
                
        if hasattr(self, 'update_sidebar_fullscreen_state'):
            self.update_sidebar_fullscreen_state()
        if hasattr(self, 'update_sidebar_margins'):
            self.update_sidebar_margins()
