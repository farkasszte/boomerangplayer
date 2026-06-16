"""
ExportFrameMixin — save/export current frame as image.
"""

import os
from PyQt6.QtWidgets import QFileDialog, QDialog
from PyQt6.QtGui import QImage
from PyQt6.QtCore import Qt
from translations import tr

from components.marker_dialogs import SaveFrameOptionsDialog

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QMainWindow, QSlider
    from config import Configuration
    ExportFrameMixinBase = QMainWindow
else:
    ExportFrameMixinBase = object


class ExportFrameMixin(ExportFrameMixinBase):
    if TYPE_CHECKING:
        current_cache_index: int
        cached_frame_dict: dict
        brightnessSlider: QSlider
        contrastSlider: QSlider
        gammaSlider: QSlider
        saturationSlider: QSlider
        hueSlider: QSlider
        tempSlider: QSlider
        exposureSlider: QSlider
        sharpenSlider: QSlider
        blurSlider: QSlider
        invertButton: any
        view: any
        pixmapItem: any
        currentFilePath: str | None
        isMirrored: bool
        isMirroredVertical: bool
        rotationAngle: int
        
        update_pixmap_from_cache: callable
        _get_adj_lut: callable

    def save_current_frame(self):
        if self.current_cache_index not in getattr(self, 'cached_frame_dict', {}):
            return

        dialog = SaveFrameOptionsDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        fmt_text = dialog.formatCombo.currentText()
        quality = dialog.qualitySlider.value()
        scale_idx = dialog.scaleCombo.currentIndex()
        include_drawings = dialog.drawingsCheckbox.isChecked()
        apply_adjustments = dialog.adjustmentsCheckbox.isChecked()

        scale_factors = [1.0, 0.75, 0.5, 2.0, 1.5]
        scale_factor = scale_factors[scale_idx]

        ext = ".png"
        file_filter = "PNG Image (*.png)"
        if "JPEG" in fmt_text:
            ext = ".jpg"
            file_filter = "JPEG Image (*.jpg *.jpeg)"
        elif "BMP" in fmt_text:
            ext = ".bmp"
            file_filter = "BMP Image (*.bmp)"
        elif "WebP" in fmt_text:
            ext = ".webp"
            file_filter = "WebP Image (*.webp)"

        default_name = f"frame_{self.current_cache_index + 1}{ext}"

        fileName, _ = QFileDialog.getSaveFileName(self, tr('save_frame'), default_name, file_filter)
        if not fileName:
            return

        data = self.cached_frame_dict[self.current_cache_index]
        img = QImage()
        if isinstance(data, bytes):
            img.loadFromData(data)
        elif isinstance(data, str):
            img.load(data)

        if img.isNull():
            return

        import numpy as np
        from PyQt6.QtGui import QPainter, QPixmap, QTransform
        from PyQt6.QtCore import QRectF

        if apply_adjustments:
            img = img.convertToFormat(QImage.Format.Format_ARGB32)
            b = self.brightnessSlider.value()
            c = self.contrastSlider.value() / 100.0
            g = self.gammaSlider.value() / 100.0
            s = self.saturationSlider.value() / 100.0
            hue_val = self.hueSlider.value() if hasattr(self, 'hueSlider') else 0
            temp_val = self.tempSlider.value() if hasattr(self, 'tempSlider') else 0
            exp_val = self.exposureSlider.value() if hasattr(self, 'exposureSlider') else 0
            exposure_mult = 1.0 + exp_val / 50.0 if exp_val >= 0 else 1.0 + exp_val / 111.0
            invert_val = 1.0 if (hasattr(self, 'invertButton') and self.invertButton.isChecked()) else 0.0
            sharpen_val = self.sharpenSlider.value() if hasattr(self, 'sharpenSlider') else 0
            blur_val = self.blurSlider.value() if hasattr(self, 'blurSlider') else 0

            width, height = img.width(), img.height()
            ptr = img.bits()
            ptr.setsize(img.sizeInBytes())
            arr = np.frombuffer(ptr, np.uint8).reshape((height, width, 4))

            # 1. Blur & Sharpen
            if blur_val > 0 or sharpen_val > 0:
                orig = arr[:, :, :3].astype(np.float32)
                top = np.roll(orig, -1, axis=0)
                bottom = np.roll(orig, 1, axis=0)
                left = np.roll(orig, -1, axis=1)
                right = np.roll(orig, 1, axis=1)
                
                if blur_val > 0:
                    blurred = (orig * 4.0 + top + bottom + left + right) / 8.0
                    orig = orig + (blur_val / 100.0) * (blurred - orig)
                if sharpen_val > 0:
                    sharpened = orig * 5.0 - (top + bottom + left + right)
                    orig = orig + (sharpen_val / 100.0) * (sharpened - orig)
                arr[:, :, :3] = np.clip(orig, 0, 255).astype(np.uint8)

            # 2. Exposure
            if exposure_mult != 1.0:
                arr[:, :, :3] = np.clip(arr[:, :, :3].astype(np.float32) * exposure_mult, 0, 255).astype(np.uint8)

            # 3. Brightness, Contrast & Gamma
            if b != 0 or c != 1.0 or g != 1.0:
                lut = self._get_adj_lut(b, c, g)
                arr[:, :, :3] = lut[arr[:, :, :3]]

            # 4. Saturation
            if s != 1.0:
                b_chan = arr[:, :, 0].astype(np.float32)
                g_chan = arr[:, :, 1].astype(np.float32)
                r_chan = arr[:, :, 2].astype(np.float32)
                gray = (0.299 * r_chan + 0.587 * g_chan + 0.114 * b_chan)
                arr[:, :, 0] = np.clip(gray + s * (b_chan - gray), 0, 255).astype(np.uint8)
                arr[:, :, 1] = np.clip(gray + s * (g_chan - gray), 0, 255).astype(np.uint8)
                arr[:, :, 2] = np.clip(gray + s * (r_chan - gray), 0, 255).astype(np.uint8)

            # 5. Hue Rotation
            if hue_val != 0:
                rad = hue_val * np.pi / 180.0
                cos_a = np.cos(rad)
                sin_a = np.sin(rad)
                r_ch = arr[:, :, 2].astype(np.float32)
                g_ch = arr[:, :, 1].astype(np.float32)
                b_ch = arr[:, :, 0].astype(np.float32)
                y = 0.299 * r_ch + 0.587 * g_ch + 0.114 * b_ch
                u = -0.147 * r_ch - 0.289 * g_ch + 0.436 * b_ch
                v = 0.615 * r_ch - 0.515 * g_ch - 0.100 * b_ch
                u_prime = u * cos_a - v * sin_a
                v_prime = u * sin_a + v * cos_a
                arr[:, :, 2] = np.clip(y + 1.140 * v_prime, 0, 255).astype(np.uint8)
                arr[:, :, 1] = np.clip(y - 0.395 * u_prime - 0.581 * v_prime, 0, 255).astype(np.uint8)
                arr[:, :, 0] = np.clip(y + 2.032 * u_prime, 0, 255).astype(np.uint8)

            # 6. Temperature
            if temp_val != 0:
                shift = temp_val * 0.15 * 2.55
                arr[:, :, 2] = np.clip(arr[:, :, 2].astype(np.float32) + shift, 0, 255).astype(np.uint8)
                arr[:, :, 0] = np.clip(arr[:, :, 0].astype(np.float32) - shift, 0, 255).astype(np.uint8)
                arr[:, :, 1] = np.clip(arr[:, :, 1].astype(np.float32) + shift * 0.33, 0, 255).astype(np.uint8)

            # 7. Invert
            if invert_val > 0.5:
                arr[:, :, :3] = 255 - arr[:, :, :3]

        if include_drawings:
            original_pixmap = self.pixmapItem.pixmap()
            self.pixmapItem.setPixmap(QPixmap.fromImage(img))

            rect = self.pixmapItem.pixmap().rect()
            out_pixmap = QPixmap(rect.size())
            out_pixmap.fill(Qt.GlobalColor.black)

            painter = QPainter(out_pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            self.view.scene().render(painter, QRectF(rect), QRectF(rect))
            painter.end()

            self.pixmapItem.setPixmap(original_pixmap)
            final_img = out_pixmap.toImage()
        else:
            if apply_adjustments:
                transform = QTransform()
                if self.isMirrored:
                    transform.scale(-1, 1)
                if self.isMirroredVertical:
                    transform.scale(1, -1)
                if self.rotationAngle != 0:
                    transform.rotate(self.rotationAngle)
                if not transform.isIdentity():
                    img = img.transformed(transform, Qt.TransformationMode.SmoothTransformation)
            final_img = img

        if scale_factor != 1.0:
            new_w = int(final_img.width() * scale_factor)
            new_h = int(final_img.height() * scale_factor)
            final_img = final_img.scaled(new_w, new_h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

        fmt = None
        if "JPEG" in fmt_text:
            fmt = "JPG"
        elif "WebP" in fmt_text:
            fmt = "WEBP"
        elif "PNG" in fmt_text:
            fmt = "PNG"
        elif "BMP" in fmt_text:
            fmt = "BMP"

        success = final_img.save(fileName, fmt, quality if (fmt in ["JPG", "WEBP", "PNG"]) else -1)
        if success:
            from qfluentwidgets import InfoBar, InfoBarPosition
            InfoBar.success(
                title=tr('save_frame'),
                content=tr('ok'),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
