from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QWidget)
from PyQt6.QtMultimedia import QMediaDevices

from qfluentwidgets import (PushButton, ComboBox, TabWidget, MessageBox, BodyLabel, TabCloseButtonDisplayMode)
from translations import tr
from utils import save_config, get_resource_path

import traceback

def log_error(msg):
    with open(get_resource_path("error_log.txt"), "a", encoding="utf-8") as f:
        f.write(msg + "\n")

class ShortcutButton(PushButton):
    keyChanged = pyqtSignal(int)
    
    def __init__(self, key_code, parent=None):
        super().__init__(parent)
        self.key_code = key_code
        self.is_recording = False
        self.update_text()
        self.clicked.connect(self.start_recording)
        
    def update_text(self):
        if self.is_recording:
            self.setText(tr('press_key'))
        else:
            try:
                from PyQt6.QtGui import QKeySequence
                self.setText(QKeySequence(self.key_code).toString())
            except Exception as e:
                self.setText("None")
                log_error(f"ShortcutButton error: {e}")
            
    def start_recording(self):
        self.is_recording = True
        self.update_text()
        self.setFocus()
        
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

class SettingsDialog(MessageBox):
    def __init__(self, config, parent=None):
        try:
            super().__init__(tr('settings'), "", parent)
            self.config = config
            self.new_config = config.copy()
            
            # Use the Dialog's layout
            self.setMinimumSize(450, 600)
            if hasattr(self, 'contentLabel'):
                self.contentLabel.hide()
            
            self.tabWidget = TabWidget(self)
            self.tabWidget.tabBar.setAddButtonVisible(False)
            self.tabWidget.tabBar.setCloseButtonDisplayMode(TabCloseButtonDisplayMode.NEVER)
        
            
            # General Tab
            self.generalTab = QWidget()
            self.generalLayout = QVBoxLayout(self.generalTab)
            self.generalLayout.setContentsMargins(20, 20, 20, 20)
            self.generalLayout.setSpacing(15)
            
            # Language
            langLayout = QHBoxLayout()
            langLayout.addWidget(BodyLabel(tr('language')))
            self.langCombo = ComboBox()
            self.langCombo.addItems(["English", "Magyar"])
            self.langCombo.setCurrentIndex(0 if config.get('language') == 'en' else 1)
            langLayout.addWidget(self.langCombo)
            self.generalLayout.addLayout(langLayout)
            
            # Audio Device
            audioLayout = QHBoxLayout()
            audioLayout.addWidget(BodyLabel(tr('audio_device')))
            self.audioCombo = ComboBox()
            try:
                self.devices = QMediaDevices.audioOutputs()
                device_names = [d.description() for d in self.devices]
                self.audioCombo.addItems(device_names)
                
                current_device = config.get('audio_device', '')
                for i, d in enumerate(self.devices):
                    # Convert QByteArray to string for comparison
                    d_id = d.id().data().decode() if hasattr(d.id(), 'data') else str(d.id())
                    if d_id == current_device:
                        self.audioCombo.setCurrentIndex(i)
                        break
            except Exception as e:
                log_error(f"Audio device detection error: {e}")
                self.devices = []
            
            audioLayout.addWidget(self.audioCombo)
            self.generalLayout.addLayout(audioLayout)
            self.generalLayout.addStretch(1)
            
            self.tabWidget.addTab(self.generalTab, tr('general'))
            
            # Shortcuts Tab
            self.shortcutsTab = QWidget()
            self.shortcutsLayout = QVBoxLayout(self.shortcutsTab)
            self.shortcutsLayout.setContentsMargins(10, 10, 10, 10)
            
            self.shortcutTable = QTableWidget(7, 2)
            self.shortcutTable.setHorizontalHeaderLabels([tr('shortcuts'), tr('record')])
            self.shortcutTable.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            self.shortcutTable.verticalHeader().hide()
            self.shortcutTable.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
            self.shortcutTable.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            self.shortcutTable.setStyleSheet("QTableWidget { background: transparent; border: none; color: white; }")
            
            actions = [
                ('play_pause', 'act_play_pause'),
                ('set_loop_start', 'act_loop_start'),
                ('set_loop_end', 'act_loop_end'),
                ('toggle_loop', 'act_toggle_loop'),
                ('next_frame', 'act_next_frame'),
                ('prev_frame', 'act_prev_frame'),
                ('toggle_mute', 'act_toggle_mute')
            ]
            
            for i, (act, label_key) in enumerate(actions):
                self.shortcutTable.setItem(i, 0, QTableWidgetItem(tr(label_key)))
                btn = ShortcutButton(self.config['shortcuts'].get(act, 0))
                btn.keyChanged.connect(lambda k, a=act: self.update_shortcut(a, k))
                self.shortcutTable.setCellWidget(i, 1, btn)
                
            self.shortcutsLayout.addWidget(self.shortcutTable)
            
            self.tabWidget.addTab(self.shortcutsTab, tr('shortcuts'))
            
            self.vBoxLayout.insertWidget(1, self.tabWidget)
            
            self.yesButton.setText(tr('save'))
            self.cancelButton.setText(tr('cancel')) # Will act as Cancel
            
            self.yesButton.clicked.connect(self.save_settings)
        except Exception as e:
            log_error(f"SettingsDialog init error: {e}\n{traceback.format_exc()}")
            raise e
        
    def update_shortcut(self, action, key_code):
        if 'shortcuts' not in self.new_config:
            self.new_config['shortcuts'] = self.config['shortcuts'].copy()
        self.new_config['shortcuts'][action] = key_code
        
    def save_settings(self):
        try:
            self.new_config['language'] = 'en' if self.langCombo.currentIndex() == 0 else 'hu'
            
            idx = self.audioCombo.currentIndex()
            if 0 <= idx < len(self.devices):
                d = self.devices[idx]
                # Store as string
                self.new_config['audio_device'] = d.id().data().decode() if hasattr(d.id(), 'data') else str(d.id())
                
            save_config(self.new_config)
            self.accept()
        except Exception as e:
            log_error(f"Save settings error: {e}")
            self.reject()
