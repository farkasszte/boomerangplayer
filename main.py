import sys
import os
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

def main():
    # Garbage collect Nvidia DXCache (.nvph) files and stale mem_cache directories asynchronously in the background
    from utils import cleanup_nvidia_dxcache, cleanup_old_mem_cache
    cleanup_nvidia_dxcache()
    cleanup_old_mem_cache()

    # Enable High DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    
    app = QApplication(sys.argv)
    app.setApplicationName("Boomerang Player")
    
    # Set default font to avoid QFont warnings
    from PyQt6.QtGui import QFont
    app.setFont(QFont("Segoe UI", 10))
    
    # Monkeypatch qfluentwidgets MaskDialogBase to fix PyQt6 animation garbage collection bug
    try:
        from qfluentwidgets.components.dialog_box.mask_dialog_base import MaskDialogBase
        from PyQt6.QtCore import QPropertyAnimation, QEasingCurve
        from PyQt6.QtWidgets import QGraphicsOpacityEffect

        def patched_done(self, code):
            self.widget.setGraphicsEffect(None)
            opacityEffect = QGraphicsOpacityEffect(self)
            self.setGraphicsEffect(opacityEffect)
            self.opacityAni = QPropertyAnimation(opacityEffect, b'opacity', self)
            self.opacityAni.setStartValue(1)
            self.opacityAni.setEndValue(0)
            self.opacityAni.setDuration(100)
            self.opacityAni.finished.connect(lambda: self._onDone(code))
            self.opacityAni.start()

        def patched_showEvent(self, e):
            opacityEffect = QGraphicsOpacityEffect(self)
            self.setGraphicsEffect(opacityEffect)
            self.showOpacityAni = QPropertyAnimation(opacityEffect, b'opacity', self)
            self.showOpacityAni.setStartValue(0)
            self.showOpacityAni.setEndValue(1)
            self.showOpacityAni.setDuration(200)
            self.showOpacityAni.setEasingCurve(QEasingCurve.Type.InSine)
            self.showOpacityAni.finished.connect(lambda: self.setGraphicsEffect(None))
            self.showOpacityAni.start()
            super(MaskDialogBase, self).showEvent(e)

        MaskDialogBase.done = patched_done
        MaskDialogBase.showEvent = patched_showEvent
    except Exception as e:
        print(f"Failed to patch MaskDialogBase: {e}")

    from player_window import PlayerWindow
    window = PlayerWindow()
    window.show()
    
    # Force a small window resize to fix Windows 11 styling and layout glitch on startup
    def force_resize_fix():
        window.resize(window.width() + 1, window.height())
        window.resize(window.width() - 1, window.height())
        window.update()
        
    from PyQt6.QtCore import QTimer
    QTimer.singleShot(300, force_resize_fix)
    
    # Load file from command line if provided
    if len(sys.argv) > 1:
        file_path = sys.argv[-1]
        if os.path.exists(file_path):
            from PyQt6.QtCore import QTimer
            # Use a short delay to ensure UI is ready
            def startup_load():
                window.add_files_to_playlist([file_path])
                window.load_video(file_path)
            QTimer.singleShot(100, startup_load)
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
