from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtWidgets import QMenu
from translations import tr
from styles import get_styles

class GlobalSettingsAudioManagerMixin:
    def show_audio_menu(self):
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
        
        self.audioOutput.setDevice(device)
