import sys
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
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
