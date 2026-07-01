import sys
import os
import logging
import faulthandler
import traceback
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMessageBox

# Determine base directory
if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

# Check if debug mode is enabled via --debug flag
is_debug = "--debug" in sys.argv

# Enable faulthandler for native C/C++ crashes (only in debug mode)
if is_debug:
    crash_log_path = os.path.join(base_dir, "crash_traceback.log")
    try:
        crash_log_file = open(crash_log_path, "w", encoding="utf-8")
        faulthandler.enable(file=crash_log_file)
    except Exception as e:
        sys.stderr.write(f"Failed to enable faulthandler: {e}\n")

# Configure logging
if is_debug:
    log_path = os.path.join(base_dir, "boomerang.log")
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout)
        ]
    )
else:
    # Disable logs or redirect them to NullHandler
    logging.basicConfig(
        level=logging.WARNING,
        handlers=[logging.NullHandler()]
    )
logger = logging.getLogger("BoomerangPlayer")

# Global exception hook
def exception_hook(exctype, value, tb):
    tb_lines = traceback.format_exception(exctype, value, tb)
    tb_text = "".join(tb_lines)
    logger.error(f"Unhandled exception:\n{tb_text}")
    try:
        if QApplication.instance():
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setText("Egy váratlan hiba történt a program futása során.")
            msg.setInformativeText(str(value))
            msg.setDetailedText(tb_text)
            msg.setWindowTitle("Váratlan hiba")
            msg.exec()
    except Exception as dialog_err:
        sys.stderr.write(f"Failed to show crash dialog: {dialog_err}\n")
    sys.__excepthook__(exctype, value, tb)

sys.excepthook = exception_hook

def main():
    logger.info("Boomerang Player main execution started.")
    # Garbage collect Nvidia DXCache (.nvph) files and stale mem_cache directories asynchronously in the background
    from utils import cleanup_nvidia_dxcache, cleanup_old_mem_cache
    cleanup_nvidia_dxcache()
    cleanup_old_mem_cache()

    # Enable High DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    
    app = QApplication(sys.argv)
    app.setApplicationName("Boomerang Player")
    
    if "--test-crash" in sys.argv:
        logger.info("Testing Python unhandled exception crash...")
        raise ValueError("Ez egy teszt Python kivétel.")
        
    if "--test-native-crash" in sys.argv:
        logger.info("Testing native C/C++ crash via ctypes...")
        import ctypes
        ctypes.memset(0, 0, 1)
    
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
            self.showOpacityAni.finished.connect(lambda: opacityEffect.setOpacity(1.0))
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
    file_path = None
    for arg in reversed(sys.argv[1:]):
        if not arg.startswith("--"):
            file_path = arg
            break
    if file_path and os.path.exists(file_path):
        from PyQt6.QtCore import QTimer
        # Use a short delay to ensure UI is ready
        def startup_load():
            window.add_files_to_playlist([file_path])
            window.load_video(file_path)
        QTimer.singleShot(100, startup_load)
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
