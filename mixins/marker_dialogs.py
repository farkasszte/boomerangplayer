"""
Dialogs used by MarkerMixin: MarkersDialog, SaveFrameOptionsDialog, SaveLoopOptionsDialog.
"""

import os
import subprocess
from PyQt6.QtWidgets import QDialog, QListWidget, QListWidgetItem, QHBoxLayout, QVBoxLayout, QLabel, QWidget, QFileDialog, QGridLayout, QComboBox
from PyQt6.QtGui import QIntValidator, QImage, QPixmap
from PyQt6.QtCore import Qt, QSize
from qfluentwidgets import ToolButton, FluentIcon, PushButton, LineEdit, CaptionLabel
from translations import tr
from utils import get_resource_path, format_time, get_ffmpeg_path
from styles import get_styles, ACTION_BTN_STYLE


class MarkerRowWidget(QWidget):
    def __init__(self, frame, name, parent_dialog, parent_player):
        super().__init__()
        self.frame = frame
        self.parent_dialog = parent_dialog
        self.parent_player = parent_player

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(8)

        # Convert frame to timestamp
        fps = getattr(self.parent_player, 'fps', 30.0)
        if fps <= 0:
            fps = 30.0
        seconds = frame / fps
        time_str = format_time(int(seconds * 1000))

        # Time label
        self.label = QLabel(f"<b>{time_str}</b>")
        self.label.setStyleSheet("color: white; font-size: 12px; background: transparent; border: none;")
        layout.addWidget(self.label)

        # Frame LineEdit
        self.frameEdit = LineEdit()
        self.frameEdit.setFixedWidth(65)
        self.frameEdit.setText(str(frame))
        total_f = int(getattr(self.parent_player, 'total_frames', 999999))
        self.frameEdit.setValidator(QIntValidator(0, total_f))
        self.frameEdit.setStyleSheet("""
            LineEdit {
                color: #aaa; 
                background: rgba(255,255,255,0.06); 
                border: 1px solid rgba(255,255,255,0.1); 
                border-radius: 4px;
                font-size: 12px;
                height: 24px;
                text-align: center;
            }
        """)
        self.frameEdit.returnPressed.connect(self.on_save_clicked)
        layout.addWidget(self.frameEdit)

        # LineEdit for name
        self.nameEdit = LineEdit()
        self.nameEdit.setText(name)
        self.nameEdit.setPlaceholderText(tr('marker_name'))
        self.nameEdit.setStyleSheet("""
            LineEdit {
                color: white; 
                background: rgba(255,255,255,0.06); 
                border: 1px solid rgba(255,255,255,0.1); 
                border-radius: 4px;
                font-size: 12px;
                height: 24px;
            }
        """)
        self.nameEdit.returnPressed.connect(self.on_save_clicked)
        layout.addWidget(self.nameEdit)

        # Save Button
        self.saveBtn = ToolButton(FluentIcon.SAVE)
        self.saveBtn.setFixedSize(28, 28)
        self.saveBtn.clicked.connect(self.on_save_clicked)
        layout.addWidget(self.saveBtn)

        # Jump Button
        self.jumpBtn = ToolButton(FluentIcon.PLAY)
        self.jumpBtn.setFixedSize(28, 28)
        self.jumpBtn.clicked.connect(self.on_jump_clicked)
        layout.addWidget(self.jumpBtn)

        # Delete Button
        self.deleteBtn = ToolButton(FluentIcon.DELETE)
        self.deleteBtn.setFixedSize(28, 28)
        self.deleteBtn.clicked.connect(self.on_delete_clicked)
        layout.addWidget(self.deleteBtn)

    def on_save_clicked(self):
        try:
            new_frame = int(self.frameEdit.text())
        except ValueError:
            return
        new_name = self.nameEdit.text()
        self.parent_dialog.save_marker_changes(self.frame, new_frame, new_name)

    def on_jump_clicked(self):
        self.parent_player.set_position(self.frame)

    def on_delete_clicked(self):
        self.parent_dialog.delete_marker(self.frame)


class MarkersDialog(QDialog):
    def __init__(self, parent_player):
        super().__init__(parent_player)
        self.parent_player = parent_player
        self.setWindowTitle(tr('markers_title'))
        self.setMinimumSize(420, 450)
        self.setStyleSheet("background: #202020; color: white;")

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(15, 15, 15, 15)
        self.layout.setSpacing(10)

        # List Widget
        self.listWidget = QListWidget()
        self.listWidget.setStyleSheet("""
            QListWidget {
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 6px;
                padding: 5px;
            }
            QListWidget::item {
                background: transparent;
                border-bottom: 1px solid rgba(255,255,255,0.04);
                padding: 4px;
            }
            QListWidget::item:selected {
                background: rgba(255,255,255,0.06);
            }
        """)
        self.listWidget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.layout.addWidget(self.listWidget)

        # Bottom Buttons
        self.closeBtn = PushButton(tr('close'))
        self.closeBtn.clicked.connect(self.close)
        self.closeBtn.setFixedWidth(100)
        
        self.addMarkerBtn = PushButton("+ " + tr('add_marker'))
        self.addMarkerBtn.clicked.connect(self.on_add_marker_clicked)
        
        btnLayout = QHBoxLayout()
        btnLayout.addWidget(self.addMarkerBtn)
        btnLayout.addStretch(1)
        btnLayout.addWidget(self.closeBtn)
        self.layout.addLayout(btnLayout)

        self.load_markers()

    def load_markers(self):
        self.listWidget.clear()
        markers = self.parent_player.markers
        playlistData = self.parent_player.playlistData
        curr_path = self.parent_player.currentFilePath
        
        marker_names = {}
        if curr_path in playlistData:
            marker_names = playlistData[curr_path].get('marker_names', {})

        # Sort markers with 0 forced to the very end of the list for better UX
        sorted_markers = sorted(markers, key=lambda x: float('inf') if x == 0 else x)
        for f in sorted_markers:
            name = marker_names.get(str(f), f"{tr('mark')} {f}")
            item = QListWidgetItem(self.listWidget)
            item.setSizeHint(QSize(0, 48))
            self.listWidget.addItem(item)
            
            row = MarkerRowWidget(f, name, self, self.parent_player)
            self.listWidget.setItemWidget(item, row)

    def save_all_rows_in_place(self):
        rows_data = []
        for i in range(self.listWidget.count()):
            item = self.listWidget.item(i)
            if not item:
                continue
            widget = self.listWidget.itemWidget(item)
            if isinstance(widget, MarkerRowWidget):
                try:
                    frame_val = int(widget.frameEdit.text())
                    name_val = widget.nameEdit.text()
                    rows_data.append((widget.frame, frame_val, name_val))
                except ValueError:
                    rows_data.append((widget.frame, widget.frame, widget.nameEdit.text()))

        playlistData = self.parent_player.playlistData
        curr_path = self.parent_player.currentFilePath
        
        if curr_path:
            if curr_path not in playlistData:
                playlistData[curr_path] = {}
            if 'marker_names' not in playlistData[curr_path]:
                playlistData[curr_path]['marker_names'] = {}
            names = playlistData[curr_path]['marker_names']
            
            new_markers = []
            new_names = {}
            for old_frame, new_frame, new_name in rows_data:
                if new_frame not in new_markers:
                    new_markers.append(new_frame)
                new_names[str(new_frame)] = new_name
                
            new_markers.sort()
            self.parent_player.markers = new_markers
            playlistData[curr_path]['marker_names'] = new_names
            
            self.parent_player.needs_range_update = True
            self.parent_player.progressBar.update_markers(self.parent_player.markers)
            self.parent_player.update_loop_frames_label()
            self.parent_player.save_current_markers()
            self.parent_player.update_chronometer()

    def closeEvent(self, event):
        self.save_all_rows_in_place()
        super().closeEvent(event)

    def on_add_marker_clicked(self):
        self.save_all_rows_in_place()
        self.parent_player.add_smart_marker(force_new=True)
        self.load_markers()

    def save_marker_changes(self, old_frame, new_frame, new_name):
        self.save_all_rows_in_place()
        self.load_markers()

    def delete_marker(self, frame):
        self.save_all_rows_in_place()
        if frame in self.parent_player.markers:
            self.parent_player.markers.remove(frame)
            
        playlistData = self.parent_player.playlistData
        curr_path = self.parent_player.currentFilePath
        if curr_path in playlistData and 'marker_names' in playlistData[curr_path]:
            if str(frame) in playlistData[curr_path]['marker_names']:
                del playlistData[curr_path]['marker_names'][str(frame)]
                
        self.parent_player.needs_range_update = True
        self.parent_player.progressBar.update_markers(self.parent_player.markers)
        self.parent_player.update_loop_frames_label()
        self.parent_player.save_current_markers()
        self.parent_player.update_chronometer()
        self.load_markers()


class SaveFrameOptionsDialog(QDialog):
    def __init__(self, parent_player):
        super().__init__(parent_player)
        self.parent_player = parent_player
        self.setWindowTitle(tr('save_frame_options'))
        self.setMinimumSize(420, 320)
        self.setStyleSheet("background: #202020; color: white;")

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(15)

        self.titleLabel = CaptionLabel(tr('save_frame_options'))
        self.titleLabel.setStyleSheet("font-size: 16px; font-weight: bold; color: white;")
        self.layout.addWidget(self.titleLabel)

        # Main settings container
        settings_widget = QWidget()
        from PyQt6.QtWidgets import QGridLayout
        settings_layout = QGridLayout(settings_widget)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.setSpacing(12)

        try:
            from qfluentwidgets import CheckBox
        except ImportError:
            from PyQt6.QtWidgets import QCheckBox as CheckBox

        accent_color = getattr(self.parent_player, 'accent_color', '#00f2ff')
        from styles import get_styles
        styles_dict = get_styles(accent_color=accent_color)
        combo_style = styles_dict.get('COMBO_STYLE', '')

        # Format selector
        format_label = QLabel(tr('format') + ":")
        format_label.setStyleSheet("color: #aaaaaa; font-size: 13px;")
        self.formatCombo = QComboBox()
        self.formatCombo.addItems(["BMP (*.bmp)", "JPEG (*.jpg)", "PNG (*.png)", "WebP (*.webp)"])
        self.formatCombo.setCurrentIndex(2)
        self.formatCombo.setStyleSheet(combo_style)
        settings_layout.addWidget(format_label, 0, 0)
        settings_layout.addWidget(self.formatCombo, 0, 1)

        # Quality slider
        self.quality_label = QLabel(tr('quality') + ":")
        self.quality_label.setStyleSheet("color: #aaaaaa; font-size: 13px;")
        
        quality_slider_layout = QHBoxLayout()
        from PyQt6.QtWidgets import QSlider
        self.qualitySlider = QSlider(Qt.Orientation.Horizontal)
        self.qualitySlider.setRange(1, 100)
        self.qualitySlider.setValue(95)
        
        slider_style = styles_dict.get('FLUENT_SLIDER_STYLE', '')
        self.qualitySlider.setStyleSheet(slider_style)
        
        self.qualityValueLabel = QLabel("95%")
        self.qualityValueLabel.setStyleSheet("color: white; font-size: 13px; min-width: 35px;")
        self.qualitySlider.valueChanged.connect(lambda v: self.qualityValueLabel.setText(f"{v}%"))
        quality_slider_layout.addWidget(self.qualitySlider)
        quality_slider_layout.addWidget(self.qualityValueLabel)
        
        settings_layout.addWidget(self.quality_label, 1, 0)
        settings_layout.addLayout(quality_slider_layout, 1, 1)

        # Resolution scale selector
        scale_label = QLabel(tr('resolution_scale') + ":")
        scale_label.setStyleSheet("color: #aaaaaa; font-size: 13px;")
        self.scaleCombo = QComboBox()
        self.scaleCombo.addItems([
            tr('original') + " (100%)",
            "75%",
            "50%",
            "200% (2x)",
            "150% (1.5x)"
        ])
        self.scaleCombo.setCurrentIndex(0)
        self.scaleCombo.setStyleSheet(combo_style)
        settings_layout.addWidget(scale_label, 2, 0)
        settings_layout.addWidget(self.scaleCombo, 2, 1)

        self.layout.addWidget(settings_widget)

        # Checkboxes
        self.drawingsCheckbox = CheckBox()
        self.drawingsCheckbox.setText(tr('include_drawings'))
        self.drawingsCheckbox.setChecked(True)
        self.layout.addWidget(self.drawingsCheckbox)

        self.adjustmentsCheckbox = CheckBox()
        self.adjustmentsCheckbox.setText(tr('apply_adjustments'))
        self.adjustmentsCheckbox.setChecked(True)
        self.layout.addWidget(self.adjustmentsCheckbox)

        self.layout.addStretch(1)

        # Action Buttons
        btnLayout = QHBoxLayout()
        self.saveBtn = PushButton(tr('save'))
        self.saveBtn.clicked.connect(self.accept)
        
        self.cancelBtn = PushButton(tr('cancel'))
        self.cancelBtn.clicked.connect(self.reject)
        
        btnLayout.addStretch(1)
        btnLayout.addWidget(self.saveBtn)
        btnLayout.addWidget(self.cancelBtn)
        self.layout.addLayout(btnLayout)

        self.saveBtn.setStyleSheet(ACTION_BTN_STYLE)
        self.cancelBtn.setStyleSheet(ACTION_BTN_STYLE)

        self.formatCombo.currentIndexChanged.connect(self.update_quality_visibility)
        self.update_quality_visibility()

    def update_quality_visibility(self):
        fmt = self.formatCombo.currentText()
        is_adjustable = "BMP" not in fmt
        if not is_adjustable:
            self.qualitySlider.setValue(100)
        self.qualitySlider.setEnabled(is_adjustable)
        self.qualityValueLabel.setEnabled(is_adjustable)
        self.quality_label.setEnabled(is_adjustable)


_cached_av1_encoder = None
_has_checked_av1 = False

def get_supported_av1_encoder():
    global _cached_av1_encoder, _has_checked_av1
    if _has_checked_av1:
        return _cached_av1_encoder
    
    _has_checked_av1 = True
    try:
        ffmpeg_path = get_ffmpeg_path()
        for enc in ["av1_nvenc", "av1_amf", "av1_qsv"]:
            cmd = [
                ffmpeg_path, "-y",
                "-f", "lavfi", "-i", "color=c=black:s=256x256",
                "-frames:v", "1",
                "-c:v", enc,
                "-f", "null", "-"
            ]
            cflags = 0
            if os.name == 'nt':
                cflags = subprocess.CREATE_NO_WINDOW
            try:
                res = subprocess.run(cmd, creationflags=cflags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if res.returncode == 0:
                    _cached_av1_encoder = enc
                    return enc
            except Exception:
                pass
    except Exception:
        pass
    return None


class SaveLoopOptionsDialog(QDialog):
    def __init__(self, parent_player):
        super().__init__(parent_player)
        self.parent_player = parent_player
        self.setWindowTitle(tr('save_loop_options'))
        self.setMinimumSize(450, 480)
        self.setStyleSheet("background: #202020; color: white;")

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(15)

        # Main settings container
        settings_widget = QWidget()
        from PyQt6.QtWidgets import QGridLayout
        settings_layout = QGridLayout(settings_widget)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.setSpacing(12)

        try:
            from qfluentwidgets import CheckBox
        except ImportError:
            from PyQt6.QtWidgets import QCheckBox as CheckBox

        accent_color = getattr(self.parent_player, 'accent_color', '#00f2ff')
        from styles import get_styles
        styles_dict = get_styles(accent_color=accent_color)
        combo_style = styles_dict.get('COMBO_STYLE', '')

        # Export mode (Lossless vs Custom)
        mode_label = QLabel(tr('export_mode') + ":")
        mode_label.setStyleSheet("color: #aaaaaa; font-size: 13px;")
        self.modeCombo = QComboBox()
        self.modeCombo.addItems([tr('lossless_copy'), tr('custom_encode')])
        self.modeCombo.setCurrentIndex(0)  # Default to Lossless
        self.modeCombo.setStyleSheet(combo_style)
        settings_layout.addWidget(mode_label, 0, 0)
        settings_layout.addWidget(self.modeCombo, 0, 1)

        # Format selector
        format_label = QLabel(tr('format') + ":")
        format_label.setStyleSheet("color: #aaaaaa; font-size: 13px;")
        self.formatCombo = QComboBox()
        self.formatCombo.addItems(["MP4 (*.mp4)", "MKV (*.mkv)", "GIF (*.gif)"])
        self.formatCombo.setCurrentIndex(0)
        self.formatCombo.setStyleSheet(combo_style)
        settings_layout.addWidget(format_label, 1, 0)
        settings_layout.addWidget(self.formatCombo, 1, 1)

        # Codec selector
        codec_label = QLabel(tr('codec') + ":")
        codec_label.setStyleSheet("color: #aaaaaa; font-size: 13px;")
        self.codecCombo = QComboBox()
        self.av1_encoder = get_supported_av1_encoder()
        codecs = ["H.264 (AVC)", "H.265 (HEVC)"]
        if self.av1_encoder:
            name_map = {
                "av1_nvenc": "AV1 (NVIDIA NVENC)",
                "av1_amf": "AV1 (AMD AMF)",
                "av1_qsv": "AV1 (Intel QSV)"
            }
            codecs.append(name_map.get(self.av1_encoder, "AV1 (Hardware)"))
        self.codecCombo.addItems(codecs)
        self.codecCombo.setCurrentIndex(0)
        self.codecCombo.setStyleSheet(combo_style)
        settings_layout.addWidget(codec_label, 2, 0)
        settings_layout.addWidget(self.codecCombo, 2, 1)

        # Quality slider
        self.quality_label = QLabel(tr('quality') + ":")
        self.quality_label.setStyleSheet("color: #aaaaaa; font-size: 13px;")
        
        quality_slider_layout = QHBoxLayout()
        from PyQt6.QtWidgets import QSlider
        self.qualitySlider = QSlider(Qt.Orientation.Horizontal)
        self.qualitySlider.setRange(1, 100)
        self.qualitySlider.setValue(80)
        
        slider_style = styles_dict.get('FLUENT_SLIDER_STYLE', '')
        self.qualitySlider.setStyleSheet(slider_style)
        
        self.qualityValueLabel = QLabel("80%")
        self.qualityValueLabel.setStyleSheet("color: white; font-size: 13px; min-width: 35px;")
        self.qualitySlider.valueChanged.connect(lambda v: self.qualityValueLabel.setText(f"{v}%"))
        quality_slider_layout.addWidget(self.qualitySlider)
        quality_slider_layout.addWidget(self.qualityValueLabel)
        
        settings_layout.addWidget(self.quality_label, 3, 0)
        settings_layout.addLayout(quality_slider_layout, 3, 1)

        # Resolution scale selector
        scale_label = QLabel(tr('resolution_scale') + ":")
        scale_label.setStyleSheet("color: #aaaaaa; font-size: 13px;")
        self.scaleCombo = QComboBox()
        self.scaleCombo.addItems([
            tr('original') + " (100%)",
            "75%",
            "50%",
            "200% (2x)",
            "150% (1.5x)"
        ])
        self.scaleCombo.setCurrentIndex(0)
        self.scaleCombo.setStyleSheet(combo_style)
        settings_layout.addWidget(scale_label, 4, 0)
        settings_layout.addWidget(self.scaleCombo, 4, 1)

        self.layout.addWidget(settings_widget)

        # Checkboxes
        self.drawingsCheckbox = CheckBox()
        self.drawingsCheckbox.setText(tr('include_drawings'))
        self.drawingsCheckbox.setChecked(True)
        self.layout.addWidget(self.drawingsCheckbox)

        self.adjustmentsCheckbox = CheckBox()
        self.adjustmentsCheckbox.setText(tr('apply_adjustments'))
        self.adjustmentsCheckbox.setChecked(True)
        self.layout.addWidget(self.adjustmentsCheckbox)

        self.speedCheckbox = CheckBox()
        self.speedCheckbox.setText(tr('apply_speed'))
        self.speedCheckbox.setChecked(False)
        self.layout.addWidget(self.speedCheckbox)

        self.muteCheckbox = CheckBox()
        self.muteCheckbox.setText(tr('mute_audio'))
        self.muteCheckbox.setChecked(False)
        self.layout.addWidget(self.muteCheckbox)

        self.layout.addStretch(1)

        # Action Buttons
        btnLayout = QHBoxLayout()
        self.saveBtn = PushButton(tr('save'))
        self.saveBtn.clicked.connect(self.accept)
        
        self.cancelBtn = PushButton(tr('cancel'))
        self.cancelBtn.clicked.connect(self.reject)
        
        btnLayout.addStretch(1)
        btnLayout.addWidget(self.saveBtn)
        btnLayout.addWidget(self.cancelBtn)
        self.layout.addLayout(btnLayout)

        self.saveBtn.setStyleSheet(ACTION_BTN_STYLE)
        self.cancelBtn.setStyleSheet(ACTION_BTN_STYLE)

        self.modeCombo.currentIndexChanged.connect(self.update_options_visibility)
        self.formatCombo.currentIndexChanged.connect(self.update_options_visibility)
        self.update_options_visibility()

    def update_options_visibility(self):
        is_custom = self.modeCombo.currentIndex() == 1
        fmt = self.formatCombo.currentText()
        is_gif = is_custom and "GIF" in fmt

        self.formatCombo.setEnabled(is_custom)
        self.scaleCombo.setEnabled(is_custom)
        
        if is_custom:
            self.codecCombo.setEnabled(not is_gif)
            self.qualitySlider.setEnabled(not is_gif)
            self.qualityValueLabel.setEnabled(not is_gif)
            self.quality_label.setEnabled(not is_gif)
            self.drawingsCheckbox.setEnabled(True)
            self.drawingsCheckbox.setChecked(True)
            self.adjustmentsCheckbox.setEnabled(True)
            self.adjustmentsCheckbox.setChecked(True)
            self.speedCheckbox.setEnabled(True)
            self.muteCheckbox.setEnabled(not is_gif)
            if is_gif:
                self.muteCheckbox.setChecked(True)
        else:
            self.codecCombo.setEnabled(False)
            self.qualitySlider.setValue(100)
            self.qualitySlider.setEnabled(False)
            self.qualityValueLabel.setEnabled(False)
            self.quality_label.setEnabled(False)
            
            self.drawingsCheckbox.setChecked(False)
            self.drawingsCheckbox.setEnabled(False)
            
            self.adjustmentsCheckbox.setChecked(False)
            self.adjustmentsCheckbox.setEnabled(False)
            
            self.speedCheckbox.setChecked(False)
            self.speedCheckbox.setEnabled(False)
            
            self.muteCheckbox.setEnabled(True)
