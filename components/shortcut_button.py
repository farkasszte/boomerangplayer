from PyQt6.QtCore import Qt, pyqtSignal
from qfluentwidgets import PushButton

class ShortcutButton(PushButton):
    keyChanged = pyqtSignal(int)
    
    def __init__(self, key_code, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.key_code = key_code
        self.is_recording = False
        self.update_text()
        self.clicked.connect(self.start_recording)
        
    def update_text(self):
        if self.is_recording:
            self.setText("...")
        else:
            try:
                from PyQt6.QtGui import QKeySequence
                self.setText(QKeySequence(self.key_code).toString())
            except Exception:
                self.setText("None")
            
    def start_recording(self):
        self.is_recording = True
        self.update_text()
        self.setFocus()
        
    def focusOutEvent(self, event):
        if self.is_recording:
            self.is_recording = False
            self.update_text()
        super().focusOutEvent(event)
        
    def keyPressEvent(self, event):
        if self.is_recording:
            key = event.key()
            if key != Qt.Key.Key_Escape:
                self.key_code = key
                self.keyChanged.emit(key)
            self.is_recording = False
            self.update_text()
            self.clearFocus()
        else:
            super().keyPressEvent(event)
