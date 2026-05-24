from PyQt6.QtCore import Qt
from qfluentwidgets import InfoBar, InfoBarPosition
from translations import tr

class GlobalSettingsGpuManagerMixin:
    def on_gpu_acceleration_changed(self, checked):
        self.config['gpu_acceleration'] = checked
        
        # Stop playback to prevent painting thread crashes during viewport swap
        if getattr(self, 'is_playing', False):
            self.stop_playback()
            
        # Notify the view if it exists
        if hasattr(self, 'pixmapItem') and hasattr(self, 'update_gpu_state'):
            self.update_gpu_state()
            
        self.update_pixmap_from_cache()
        
        # Show a premium InfoBar alerting the user that a restart is recommended
        InfoBar.info(
            title=tr('gpu_acceleration'),
            content=tr('gpu_restart_msg'),
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=5000,
            parent=self
        )
