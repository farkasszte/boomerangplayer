import ctypes
from PyQt6.QtCore import Qt

class FullscreenUIMixin:
    def toggle_full_screen(self):
        self.is_full_screen = not self.is_full_screen
        
        if self.is_full_screen:
            # Entering Full Screen
            # Save exact window state and geometry before entering fullscreen
            # pyrefly: ignore [missing-attribute]
            self.window_state_before_fs = self.windowState()
            # pyrefly: ignore [missing-attribute]
            self.geometry_before_fs = self.geometry()
            
            # Save sidebar states
            self.sidebar_states_before_fs = {
                # pyrefly: ignore [missing-attribute]
                'playlist': self.playlistContainer.isVisible(),
                # pyrefly: ignore [missing-attribute]
                'drawing': self.drawingContainer.isVisible(),
                # pyrefly: ignore [missing-attribute]
                'settings': self.settingsContainer.isVisible(),
                # pyrefly: ignore [missing-attribute]
                'global_settings': self.globalSettingsContainer.isVisible()
            }
            self.sidebars_hidden_by_controls = self.sidebar_states_before_fs.copy()
            
            # Hide everything extra
            # pyrefly: ignore [missing-attribute]
            self.playlistContainer.hide()
            # pyrefly: ignore [missing-attribute]
            self.drawingContainer.hide()
            # pyrefly: ignore [missing-attribute]
            self.settingsContainer.hide()
            # pyrefly: ignore [missing-attribute]
            self.globalSettingsContainer.hide()
            
            if hasattr(self, 'titleBar'):
                self.titleBar.hide()
            
            # Remove header margin
            if hasattr(self, 'widgetLayout'):
                self.widgetLayout.setContentsMargins(0, 0, 0, 0)
            
            # Disable rounded corners and ensure black background to prevent leaks
            # pyrefly: ignore [missing-attribute]
            self.setStyleSheet("PlayerWindow { border-radius: 0px; border: none; background: black; }")
            if hasattr(self, 'stackedWidget'):
                self.stackedWidget.setStyleSheet("border-radius: 0px; margin: 0px; padding: 0px;")
            if hasattr(self, 'playerInterface'):
                self.playerInterface.setStyleSheet("border-radius: 0px; margin: 0px; padding: 0px;")
            
            # Windows 11: Disable rounded corners via DWM
            try:
                DWMWA_WINDOW_CORNER_PREFERENCE = 33
                DWMWCP_DONOTROUND = 1
                # pyrefly: ignore [missing-attribute]
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
                # pyrefly: ignore [missing-attribute]
                self.controlsCard.setGeometry(0, self.height() - h, self.width(), h)

            # pyrefly: ignore [missing-attribute]
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
                    # pyrefly: ignore [missing-attribute]
                    self.setCursor(Qt.CursorShape.BlankCursor)
                    self.view.setCursor(Qt.CursorShape.BlankCursor)
        else:
            # Exiting Full Screen
            # Restore saved window state or default to Maximized
            if hasattr(self, 'window_state_before_fs') and self.window_state_before_fs is not None:
                if self.window_state_before_fs & Qt.WindowState.WindowMaximized:
                    # pyrefly: ignore [missing-attribute]
                    self.showMaximized()
                else:
                    # pyrefly: ignore [missing-attribute]
                    self.showNormal()
                    if hasattr(self, 'geometry_before_fs') and self.geometry_before_fs is not None:
                        # pyrefly: ignore [missing-attribute]
                        self.setGeometry(self.geometry_before_fs)
            else:
                # pyrefly: ignore [missing-attribute]
                self.showMaximized()
            
            # Windows 11: Restore rounded corners (default behavior)
            try:
                DWMWA_WINDOW_CORNER_PREFERENCE = 33
                DWMWCP_DEFAULT = 0
                # pyrefly: ignore [missing-attribute]
                hwnd = int(self.winId())
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
                    ctypes.byref(ctypes.c_int(DWMWCP_DEFAULT)), 
                    ctypes.sizeof(ctypes.c_int)
                )
            except:
                pass
            
            # Restore styles (default for FluentWindow)
            # pyrefly: ignore [missing-attribute]
            self.setStyleSheet("")
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
                
            # Restore sidebars based on what was visible in fullscreen before they auto-hid, or what was visible before entering fullscreen
            if getattr(self, 'sidebars_hidden_by_controls', None) is not None:
                restore_states = self.sidebars_hidden_by_controls
            else:
                restore_states = {
                    # pyrefly: ignore [missing-attribute]
                    'playlist': self.playlistContainer.isVisible(),
                    # pyrefly: ignore [missing-attribute]
                    'drawing': self.drawingContainer.isVisible(),
                    # pyrefly: ignore [missing-attribute]
                    'settings': self.settingsContainer.isVisible(),
                    # pyrefly: ignore [missing-attribute]
                    'global_settings': self.globalSettingsContainer.isVisible()
                }

            if restore_states.get('playlist'):
                # pyrefly: ignore [missing-attribute]
                self.playlistContainer.show()
            if restore_states.get('drawing'):
                # pyrefly: ignore [missing-attribute]
                self.drawingContainer.show()
            if restore_states.get('settings'):
                # pyrefly: ignore [missing-attribute]
                self.settingsContainer.show()
            if restore_states.get('global_settings'):
                # pyrefly: ignore [missing-attribute]
                self.globalSettingsContainer.show()

            # pyrefly: ignore [bad-assignment]
            self.sidebars_hidden_by_controls = None

            # Ensure controls are shown and timer is stopped when exiting fullscreen
            if hasattr(self, 'controls_timer'):
                self.controls_timer.stop()
            
            # Restore parent and add controlsCard back into self.playerLayout
            if hasattr(self, 'playerLayout') and hasattr(self, 'controlsCard'):
                # pyrefly: ignore [missing-attribute]
                self.controlsCard.setParent(self.playerInterface)
                self.playerLayout.addWidget(self.controlsCard, stretch=0)
                self.controlsCard.show()

            # Restore mouse cursor
            if hasattr(self, 'view') and not getattr(self.view, 'drawing_mode', False):
                # pyrefly: ignore [missing-attribute]
                self.setCursor(Qt.CursorShape.ArrowCursor)
                self.view.setCursor(Qt.CursorShape.ArrowCursor)
                
        if hasattr(self, 'update_sidebar_fullscreen_state'):
            self.update_sidebar_fullscreen_state()
        if hasattr(self, 'update_sidebar_margins'):
            self.update_sidebar_margins()
