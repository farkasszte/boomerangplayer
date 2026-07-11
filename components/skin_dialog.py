from PyQt6.QtWidgets import QDialog, QListWidget, QListWidgetItem, QHBoxLayout, QVBoxLayout, QLabel, QWidget, QFrame
from PyQt6.QtCore import Qt, QSize
from qfluentwidgets import ToolButton, FluentIcon, PushButton, SwitchButton
from components.no_wheel_slider import NoWheelSlider
from translations import tr
from styles import get_color_tokens, ACTION_BTN_STYLE, get_styles

class SkinRowWidget(QWidget):
    def __init__(self, name, skin, parent_dialog, parent_player, preset_key=None):
        super().__init__()
        self.name = name
        self.skin = skin
        self.parent_dialog = parent_dialog
        self.parent_player = parent_player
        self.preset_key = preset_key
        self.setFixedHeight(36)

        t = get_color_tokens(
            parent_player.config.get('accent_color', '#00f2ff'),
            parent_player.config.get('bg_color', '#202020'),
            parent_player.config.get('inverse_text', False)
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(10)


        # Name label
        self.label = QLabel(name)
        self.label.setStyleSheet(f"color: {t['fg']}; font-size: 13px; font-weight: bold; background: transparent; border: none;")
        layout.addWidget(self.label)
        layout.addStretch(1)

        # Color previews (bg and accent)
        color_layout = QHBoxLayout()
        color_layout.setSpacing(4)
        
        # Bg color badge
        self.bgBadge = QFrame()
        self.bgBadge.setFixedSize(16, 16)
        self.bgBadge.setStyleSheet(f"background-color: {skin['bg']}; border: 1px solid {t['border']}; border-radius: 8px;")
        color_layout.addWidget(self.bgBadge)

        # Accent color badge
        self.accentBadge = QFrame()
        self.accentBadge.setFixedSize(16, 16)
        self.accentBadge.setStyleSheet(f"background-color: {skin['accent']}; border: 1px solid {t['border']}; border-radius: 8px;")
        color_layout.addWidget(self.accentBadge)

        layout.addLayout(color_layout)

        # Apply Button
        self.applyBtn = ToolButton(FluentIcon.ACCEPT)
        self.applyBtn.setFixedSize(28, 28)
        self.applyBtn.clicked.connect(self.on_apply_clicked)
        layout.addWidget(self.applyBtn)

        # Delete Button
        self.deleteBtn = ToolButton(FluentIcon.DELETE)
        self.deleteBtn.setFixedSize(28, 28)
        self.deleteBtn.clicked.connect(self.on_delete_clicked)
        layout.addWidget(self.deleteBtn)

    def on_apply_clicked(self):
        self.parent_player.apply_skin(self.skin)
        self.parent_dialog.refresh_dialog_styles()

    def on_delete_clicked(self):
        self.parent_dialog.delete_skin(self.name, self.preset_key)



class SkinsDialog(QDialog):
    def __init__(self, parent_player):
        super().__init__(parent_player)
        self.parent_player = parent_player
        
        # Keep reference to active dialog on the player window
        self.parent_player.active_skins_dialog = self

        self.setWindowTitle(tr('skins'))
        self.setMinimumSize(680, 480)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(15)

        # Split pane layout
        self.paneLayout = QHBoxLayout()
        self.paneLayout.setSpacing(20)

        # Left pane: Customization
        self.leftPane = QFrame()
        self.leftLayout = QVBoxLayout(self.leftPane)
        self.leftLayout.setContentsMargins(0, 0, 0, 0)
        self.leftLayout.setSpacing(15)

        # Accent color button
        self.accentBtn = PushButton()
        self.accentBtn.clicked.connect(self.parent_player.choose_accent_color)
        self.leftLayout.addWidget(self.accentBtn)

        # Bg color button
        self.bgBtn = PushButton()
        self.bgBtn.clicked.connect(self.parent_player.choose_bg_color)
        self.leftLayout.addWidget(self.bgBtn)

        # Inverse text row
        inverseTextRow = QHBoxLayout()
        self.inverseTextLabel = QLabel(tr('inverse_text'))
        self.inverseTextToggle = SwitchButton()
        self.inverseTextToggle.setOnText(tr('on'))
        self.inverseTextToggle.setOffText(tr('off'))
        self.inverseTextToggle.checkedChanged.connect(self.parent_player.on_inverse_text_changed)
        inverseTextRow.addWidget(self.inverseTextLabel)
        inverseTextRow.addStretch(1)
        inverseTextRow.addWidget(self.inverseTextToggle)
        self.leftLayout.addLayout(inverseTextRow)

        # Opacity Row
        opacityRow = QHBoxLayout()
        self.opacityTitleLabel = QLabel(tr('panel_opacity'))
        self.opacityValueLabel = QLabel("")
        self.opacityValueLabel.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        opacityRow.addWidget(self.opacityTitleLabel)
        opacityRow.addStretch(1)
        opacityRow.addWidget(self.opacityValueLabel)
        self.leftLayout.addLayout(opacityRow)

        self.opacitySlider = NoWheelSlider(Qt.Orientation.Horizontal)
        self.opacitySlider.setRange(20, 100)
        self.opacitySlider.setSingleStep(5)
        self.opacitySlider.setPageStep(5)
        self.opacitySlider.valueChanged.connect(self.parent_player.on_panel_opacity_changed)
        self.leftLayout.addWidget(self.opacitySlider)
        
        self.leftLayout.addStretch(1)

        # Actions Layout
        self.actionsLayout = QHBoxLayout()
        self.saveBtn = PushButton(tr('save'))
        self.saveBtn.clicked.connect(self.parent_player.prompt_save_skin)
        
        self.importBtn = PushButton(tr('import_skin'))
        self.importBtn.clicked.connect(self.parent_player.prompt_import_skin)

        self.closeBtn = PushButton(tr('cancel'))
        self.closeBtn.clicked.connect(self.accept)

        self.actionsLayout.addWidget(self.saveBtn)
        self.actionsLayout.addWidget(self.importBtn)
        self.leftLayout.addLayout(self.actionsLayout)
        self.leftLayout.addWidget(self.closeBtn)

        # Right pane: Skins & Presets
        self.rightPane = QFrame()
        self.rightLayout = QVBoxLayout(self.rightPane)
        self.rightLayout.setContentsMargins(0, 0, 0, 0)
        self.rightLayout.setSpacing(10)

        # List Widget
        self.listWidget = QListWidget()
        self.listWidget.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.listWidget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.rightLayout.addWidget(self.listWidget)

        # Add to split pane (Skins/Presets on the left, Customization on the right)
        self.paneLayout.addWidget(self.rightPane, 1)
        self.paneLayout.addWidget(self.leftPane, 1)
        self.layout.addLayout(self.paneLayout)

        self.refresh_dialog_styles()

    def get_preset_skins(self):
        if hasattr(self.parent_player, 'get_preset_skins'):
            return self.parent_player.get_preset_skins()
        return {}

    def refresh_dialog_styles(self):
        t = get_color_tokens(
            self.parent_player.config.get('accent_color', '#00f2ff'),
            self.parent_player.config.get('bg_color', '#202020'),
            self.parent_player.config.get('inverse_text', False)
        )
        accent_color = self.parent_player.config.get('accent_color', '#00f2ff')
        styles_dict = get_styles(accent_color=accent_color, bg_color=t['bg'], inverse_text=self.parent_player.config.get('inverse_text', False))

        self.setStyleSheet(f"background: {t['bg']}; color: {t['fg']};")
        self._apply_dwm(t['bg'], t['fg'])

        # Style labels
        for lbl in [self.inverseTextLabel, self.opacityTitleLabel, self.opacityValueLabel]:
            lbl.setStyleSheet(f"color: {t['fg']}; background: transparent; border: none;")

        # Set values
        self.accentBtn.setText(tr('accent_color'))
        self.bgBtn.setText(tr('bg_color'))

        
        self.accentBtn.setStyleSheet(styles_dict.get('TRIGGER_STYLE', ''))
        self.bgBtn.setStyleSheet(styles_dict.get('TRIGGER_STYLE', ''))
        self.saveBtn.setStyleSheet(styles_dict.get('ACTION_BTN_STYLE', ''))
        self.importBtn.setStyleSheet(styles_dict.get('ACTION_BTN_STYLE', ''))
        self.closeBtn.setStyleSheet(styles_dict.get('ACTION_BTN_STYLE', ''))

        self.inverseTextToggle.blockSignals(True)
        self.inverseTextToggle.setChecked(self.parent_player.config.get('inverse_text', False))
        self.inverseTextToggle.blockSignals(False)
        self.inverseTextToggle.setStyleSheet(styles_dict.get('SWITCH_STYLE', ''))

        opacity = self.parent_player.config.get('panel_opacity', 100)
        self.opacityValueLabel.setText(f"{opacity}%")
        self.opacitySlider.blockSignals(True)
        self.opacitySlider.setValue(opacity)
        self.opacitySlider.blockSignals(False)
        self.opacitySlider.setStyleSheet(styles_dict.get('FLUENT_SLIDER_STYLE', ''))

        self.listWidget.setStyleSheet(f"""
            QListWidget {{
                background: {t['bg_translucent']};
                border: 1px solid {t['border']};
                border-radius: 6px;
                padding: 5px;
                outline: none;
            }}
            QListWidget::item {{
                background: transparent;
                border: none;
                padding: 4px;
                outline: none;
            }}
            QListWidget::item:selected {{
                background: transparent;
                border: none;
                outline: none;
            }}
            QListWidget::item:focus {{
                background: transparent;
                border: none;
                outline: none;
            }}
        """)

        self.load_skins()

    def load_skins(self):
        self.listWidget.clear()
        
        skins_to_load = []

        # Load preset skins
        preset_skins = self.get_preset_skins()
        deleted_presets = getattr(self.parent_player, 'deleted_presets', [])
        for name_key, skin in preset_skins.items():
            if name_key in deleted_presets:
                continue
            display_name = tr(name_key)
            is_default = (name_key == 'skin_default')
            skins_to_load.append({
                'display_name': display_name,
                'skin': skin,
                'preset_key': name_key,
                'is_default': is_default
            })

        # Load custom skins
        custom_skins = self.parent_player.load_custom_skins()
        for name, skin in custom_skins.items():
            skins_to_load.append({
                'display_name': name,
                'skin': skin,
                'preset_key': None,
                'is_default': False
            })

        # Sort: Default always top, rest in ABC order
        skins_to_load.sort(key=lambda s: (not s['is_default'], s['display_name'].lower()))

        for s in skins_to_load:
            item = QListWidgetItem(self.listWidget)
            widget = SkinRowWidget(
                s['display_name'], 
                s['skin'], 
                self, 
                self.parent_player, 
                preset_key=s['preset_key']
            )
            item.setSizeHint(widget.sizeHint())
            self.listWidget.setItemWidget(item, widget)

    def delete_skin(self, name, preset_key=None):
        # Confirmation box
        from PyQt6.QtWidgets import QMessageBox
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setWindowTitle(tr('delete_skin'))
        msg_box.setText(tr('confirm_delete'))
        msg_box.setInformativeText(name)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)
        if hasattr(self.parent_player, 'style_dialog'):
            self.parent_player.style_dialog(msg_box)

        if msg_box.exec() != QMessageBox.StandardButton.Yes:
            return

        custom_skins = self.parent_player.load_custom_skins()
        if preset_key:
            if not hasattr(self.parent_player, 'deleted_presets'):
                self.parent_player.deleted_presets = []
            if preset_key not in self.parent_player.deleted_presets:
                self.parent_player.deleted_presets.append(preset_key)
            self.parent_player.save_custom_skins(custom_skins)
            self.load_skins()
        elif name in custom_skins:
            del custom_skins[name]
            self.parent_player.save_custom_skins(custom_skins)
            self.load_skins()
            
        from PyQt6.QtCore import Qt
        from qfluentwidgets import InfoBar, InfoBarPosition
        InfoBar.success(
            title=tr('skins'),
            content=tr('skin_delete_success'),
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )


    def closeEvent(self, event):
        self.parent_player.active_skins_dialog = None
        super().closeEvent(event)

    def _apply_dwm(self, bg, fg):
        import sys
        if sys.platform != 'win32':
            return
        try:
            import ctypes
            hwnd = int(self.winId())

            def _ref(c):
                from PyQt6.QtGui import QColor
                color = QColor(c)
                return color.red() | (color.green() << 8) | (color.blue() << 16)

            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 35, ctypes.byref(ctypes.c_int(_ref(bg))), 4)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 36, ctypes.byref(ctypes.c_int(_ref(fg))), 4)
        except Exception:
            pass
