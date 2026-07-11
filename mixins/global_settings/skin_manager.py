import os
import json
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtWidgets import QMenu, QInputDialog, QMessageBox
from PyQt6.QtGui import QColor
from qfluentwidgets import Theme, setTheme, setThemeColor
from translations import tr
from styles import get_styles
from utils import get_base_path

class GlobalSettingsSkinManagerMixin:
    def get_preset_skins(self):
        return {
            'skin_default': {'accent': '#00F2FF', 'bg': '#202020', 'inverse_text': False},
            'skin_light': {'accent': '#0078D4', 'bg': '#F3F3F3', 'inverse_text': True},
            'skin_dark': {'accent': '#00F2FF', 'bg': '#121212', 'inverse_text': False},
            'skin_nord': {'accent': '#88C0D0', 'bg': '#2E3440', 'inverse_text': False},
            'skin_neon': {'accent': '#FF007F', 'bg': '#0D0E15', 'inverse_text': False},
            'skin_forest': {'accent': '#A3BE8C', 'bg': '#1B2B24', 'inverse_text': False},
            'skin_sunset': {'accent': '#FF5722', 'bg': '#2A1F2D', 'inverse_text': False},
        }

    def get_skins_json_path(self):
        return os.path.join(get_base_path(), "skins.json")

    def load_custom_skins(self):
        path = self.get_skins_json_path()
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.deleted_presets = data.pop('_deleted_presets', [])
                    return data
            except Exception as e:
                print(f"Error loading custom skins: {e}")
        self.deleted_presets = []
        return {}

    def save_custom_skins(self, skins):
        path = self.get_skins_json_path()
        try:
            data = skins.copy()
            data['_deleted_presets'] = getattr(self, 'deleted_presets', [])
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error saving custom skins: {e}")

    def show_skins_dialog(self):
        from components.skin_dialog import SkinsDialog
        dialog = SkinsDialog(self)
        dialog.exec()



    def apply_skin(self, skin):
        accent = skin['accent']
        bg = skin['bg']
        inverse_text = skin['inverse_text']

        # Update configuration
        self.config['accent_color'] = accent
        self.config['bg_color'] = bg
        self.config['inverse_text'] = inverse_text

        # Update pending state values in settings
        self.pending_accent_color = accent
        self.pending_bg_color = bg
        self.accent_color = accent

        # Theme color setting
        setThemeColor(QColor(accent))
        setTheme(Theme.LIGHT if inverse_text else Theme.DARK)

        # Update UI components
        if hasattr(self, 'inverseTextToggle'):
            self.inverseTextToggle.blockSignals(True)
            self.inverseTextToggle.setChecked(inverse_text)
            self.inverseTextToggle.blockSignals(False)

        if hasattr(self, 'refresh_custom_styles'):
            self.refresh_custom_styles()

        self.update_ui_texts()
        self.config.save()

    def prompt_save_skin(self):
        dialog = QInputDialog(self)
        dialog.setWindowTitle(tr('skins'))
        dialog.setLabelText(tr('enter_skin_name'))
        if hasattr(self, 'style_dialog'):
            self.style_dialog(dialog)
        else:
            accent = self.config.get('accent_color', '#00f2ff')
            bg = self.config.get('bg_color', '#202020')
            inverse = self.config.get('inverse_text', False)
            fg = "#1c1c1c" if inverse else "#ffffff"
            border = "rgba(0, 0, 0, 0.35)" if inverse else "rgba(255, 255, 255, 0.1)"
            dialog.setStyleSheet(f"QInputDialog, QDialog {{ background-color: {bg}; border: 1px solid {border}; }} QLabel {{ color: {fg}; }}")

        ok = dialog.exec()
        name = dialog.textValue()

        if ok and name.strip():
            name = name.strip()
            custom_skins = self.load_custom_skins()
            preset_keys = self.get_preset_skins().keys()
            preset_names = [tr(k).lower() for k in preset_keys]
            
            if name.lower() in preset_names or name in custom_skins:
                msg_box = QMessageBox(self)
                msg_box.setIcon(QMessageBox.Icon.Warning)
                msg_box.setWindowTitle(tr('skins'))
                msg_box.setText(tr('skin_exists'))
                if hasattr(self, 'style_dialog'):
                    self.style_dialog(msg_box)
                msg_box.exec()
                return

            custom_skins[name] = {
                'accent': self.config.get('accent_color', '#00f2ff'),
                'bg': self.config.get('bg_color', '#202020'),
                'inverse_text': self.config.get('inverse_text', False)
            }
            self.save_custom_skins(custom_skins)
            
            parent_widget = self.active_skins_dialog if (hasattr(self, 'active_skins_dialog') and self.active_skins_dialog) else self
            from qfluentwidgets import InfoBar, InfoBarPosition
            InfoBar.success(
                title=tr('skins'),
                content=tr('skin_save_success'),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=parent_widget
            )
            if hasattr(self, 'active_skins_dialog') and self.active_skins_dialog:
                self.active_skins_dialog.refresh_dialog_styles()

    def prompt_delete_skin(self):
        from components.skin_dialog import SkinsDialog
        dialog = SkinsDialog(self)
        dialog.exec()


    def prompt_import_skin(self):
        from mixins.file_dialog import MediaFileDialog
        from PyQt6.QtWidgets import QDialog
        dialog = MediaFileDialog(self, self.config)
        dialog.setWindowTitle(tr('import_skin'))
        if hasattr(dialog, '_filter_combo'):
            dialog._filter_combo.setCurrentIndex(4) # Select playlist/JSON index
        
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
            
        paths = dialog.selected_paths()
        if not paths:
            return
        file_path = paths[0]


        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"Error loading imported skin file: {e}")
            parent_widget = self.active_skins_dialog if (hasattr(self, 'active_skins_dialog') and self.active_skins_dialog) else self
            msg_box = QMessageBox(parent_widget)
            msg_box.setIcon(QMessageBox.Icon.Critical)
            msg_box.setWindowTitle(tr('skins'))
            msg_box.setText(tr('invalid_skin_file'))
            if hasattr(self, 'style_dialog'):
                self.style_dialog(msg_box)
            msg_box.exec()
            return

        # Check if single skin or multiple skins
        is_single = isinstance(data, dict) and 'accent' in data and 'bg' in data and 'inverse_text' in data
        is_multiple = isinstance(data, dict) and not is_single and all(
            isinstance(v, dict) and 'accent' in v and 'bg' in v and 'inverse_text' in v
            for v in data.values()
        )

        if not is_single and not is_multiple:
            parent_widget = self.active_skins_dialog if (hasattr(self, 'active_skins_dialog') and self.active_skins_dialog) else self
            msg_box = QMessageBox(parent_widget)
            msg_box.setIcon(QMessageBox.Icon.Critical)
            msg_box.setWindowTitle(tr('skins'))
            msg_box.setText(tr('invalid_skin_file'))
            if hasattr(self, 'style_dialog'):
                self.style_dialog(msg_box)
            msg_box.exec()
            return

        custom_skins = self.load_custom_skins()
        preset_skins = self.get_preset_skins()
        
        # Hardcoded set of preset names in both English and Hungarian to filter them out
        preset_names = {
            'default', 'alapértelmezett', 'light', 'világos', 'dark', 'sötét', 
            'nord', 'neon', 'forest', 'erdei', 'sunset', 'naplemente',
            'skin_default', 'skin_light', 'skin_dark', 'skin_nord', 'skin_neon', 'skin_forest', 'skin_sunset'
        }

        def is_duplicate_or_preset(name, skin):
            # Check name collision with factory presets
            if name.lower() in preset_names:
                return True
            # Check color value collision with factory presets
            for p_val in preset_skins.values():
                if (p_val['accent'].upper() == skin.get('accent', '').upper() and 
                    p_val['bg'].upper() == skin.get('bg', '').upper() and 
                    p_val['inverse_text'] == skin.get('inverse_text', False)):
                    return True
            # Check color value collision with existing custom skins to avoid duplicates
            for c_val in custom_skins.values():
                if (c_val['accent'].upper() == skin.get('accent', '').upper() and 
                    c_val['bg'].upper() == skin.get('bg', '').upper() and 
                    c_val['inverse_text'] == skin.get('inverse_text', False)):
                    return True
            return False

        imported_count = 0
        skipped_count = 0

        if is_single:
            if is_duplicate_or_preset(os.path.splitext(os.path.basename(file_path))[0], data):
                skipped_count = 1
            else:
                # Get default name from filename
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                parent_widget = self.active_skins_dialog if (hasattr(self, 'active_skins_dialog') and self.active_skins_dialog) else self
                dialog = QInputDialog(parent_widget)
                dialog.setWindowTitle(tr('skins'))
                dialog.setLabelText(tr('enter_skin_name'))
                dialog.setTextValue(base_name)
                if hasattr(self, 'style_dialog'):
                    self.style_dialog(dialog)
                else:
                    accent = self.config.get('accent_color', '#00f2ff')
                    bg = self.config.get('bg_color', '#202020')
                    inverse = self.config.get('inverse_text', False)
                    fg = "#1c1c1c" if inverse else "#ffffff"
                    border = "rgba(0, 0, 0, 0.35)" if inverse else "rgba(255, 255, 255, 0.1)"
                    dialog.setStyleSheet(f"QInputDialog, QDialog {{ background-color: {bg}; border: 1px solid {border}; }} QLabel {{ color: {fg}; }}")

                ok = dialog.exec()
                name = dialog.textValue()
                if ok and name.strip():
                    name = name.strip()
                    if is_duplicate_or_preset(name, data):
                        skipped_count = 1
                    else:
                        final_name = name
                        suffix = 1
                        while final_name in custom_skins:
                            final_name = f"{name} ({suffix})"
                            suffix += 1
                        custom_skins[final_name] = data
                        self.save_custom_skins(custom_skins)
                        self.apply_skin(data)
                        imported_count = 1
        else:
            # Merge all skins, resolving name collisions by appending a suffix
            for name, skin in data.items():
                if is_duplicate_or_preset(name, skin):
                    skipped_count += 1
                    continue
                final_name = name
                suffix = 1
                while final_name in custom_skins:
                    final_name = f"{name} ({suffix})"
                    suffix += 1
                custom_skins[final_name] = skin
                imported_count += 1
            if imported_count > 0:
                self.save_custom_skins(custom_skins)

        # Dynamic translation
        from translations import get_lang
        lang = get_lang()
        if lang == 'hu':
            msg = f"Sikeresen importálva: {imported_count} szkín. Kihagyva (duplikáció): {skipped_count}."
        else:
            msg = f"Imported successfully: {imported_count} skin(s). Skipped (duplicate): {skipped_count}."

        parent_widget = self.active_skins_dialog if (hasattr(self, 'active_skins_dialog') and self.active_skins_dialog) else self
        from qfluentwidgets import InfoBar, InfoBarPosition
        InfoBar.success(
            title=tr('skins'),
            content=msg,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=parent_widget
        )

        if imported_count > 0 and hasattr(self, 'active_skins_dialog') and self.active_skins_dialog:
            self.active_skins_dialog.refresh_dialog_styles()
