from PyQt6.QtWidgets import QSpinBox

class SafeSpinBox(QSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lineEdit().cursorPositionChanged.connect(self._fix_cursor_position)

    def _fix_cursor_position(self, old_pos, new_pos):
        prefix = self.prefix()
        suffix = self.suffix()
        text = self.lineEdit().text()
        
        min_pos = len(prefix) if prefix else 0
        max_pos = len(text) - len(suffix) if suffix and text.endswith(suffix) else len(text)
        
        if new_pos < min_pos or new_pos > max_pos:
            target_pos = max(min_pos, min(new_pos, max_pos))
            # Block signals temporarily to prevent recursion
            self.lineEdit().blockSignals(True)
            self.lineEdit().setCursorPosition(target_pos)
            self.lineEdit().blockSignals(False)
