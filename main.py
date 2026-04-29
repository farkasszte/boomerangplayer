import sys
import os
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

def main():
    # Enable High DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    
    app = QApplication(sys.argv)
    app.setApplicationName("Boomerang Player")
    
    # Set default font to avoid QFont warnings
    from PyQt6.QtGui import QFont
    app.setFont(QFont("Segoe UI", 10))
    
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
