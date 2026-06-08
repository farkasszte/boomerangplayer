from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QLineEdit, QTextEdit
import qfluentwidgets

class ShortcutUIMixin:
    # ------------------------------------------------------------------ #
    # Keyboard events & Shortcuts                                          #
    # ------------------------------------------------------------------ #

    def setup_shortcuts(self):
        # Clean up existing shortcuts if any
        if hasattr(self, '_shortcut_objects'):
            for sc in self._shortcut_objects:
                sc.setEnabled(False)
                sc.setParent(None)
        
        self._shortcut_objects = []
        
        handled_actions = {
            
            'play_pause': self.play_pause,
            
            'smart_mark': self.add_smart_marker,
            'toggle_loop': self.toggle_shortcut_loop,
            
            'next_frame': lambda: self.step_frame(1),
            
            'prev_frame': lambda: self.step_frame(-1),
            
            'toggle_mute': self.toggle_mute,
            
            'act_full_screen': self.toggle_full_screen
        }
        
        for act, slot in handled_actions.items():
            
            key_val = self.shortcuts.get(act)
            if key_val is not None:
                try:
                    key_code = int(key_val)
                    shortcut = QShortcut(QKeySequence(key_code), self)
                    shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
                    shortcut.activated.connect(lambda s=slot: self.trigger_shortcut_action(s))
                    self._shortcut_objects.append(shortcut)
                except (ValueError, TypeError) as e:
                    print(f"Error setting up shortcut for {act}: {e}")

    def trigger_shortcut_action(self, slot):
        
        focused = self.focusWidget()
        if isinstance(focused, (QLineEdit, QTextEdit, qfluentwidgets.LineEdit, qfluentwidgets.TextEdit)):
            return
        slot()

    def toggle_shortcut_loop(self):
        
        current = self.loopCombo.currentIndex()
        
        self.loopCombo.setCurrentIndex(0 if current != 0 else 3)

    def keyPressEvent(self, event):
        
        super().keyPressEvent(event)

    def toggle_sync_lock(self, checked=None):
        if checked is not None:
            self.isSyncLocked = checked
        else:
            self.isSyncLocked = not self.isSyncLocked
            
        self.sync_offset = None
        self.update_sync_lock_button_style()
        if self.isSyncLocked:
            
            self.broadcast_sync_event("sync_state", self.current_cache_index)

    def update_sync_lock_button_style(self):
        if hasattr(self, 'lockSyncToggle') and self.lockSyncToggle:
            self.lockSyncToggle.blockSignals(True)
            self.lockSyncToggle.setChecked(self.isSyncLocked)
            self.lockSyncToggle.blockSignals(False)
