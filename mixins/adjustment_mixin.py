"""
AdjustmentMixin — image/video pixel adjustments (brightness, contrast, gamma, saturation, temp, blur/sharpen, invert)
                  and software/GPU rendering pipelines.
"""

import os
import numpy as np
from PyQt6.QtGui import QImage, QPixmap, QPainter, QColor, QFont
from PyQt6.QtCore import Qt, QRectF, QBuffer, QIODevice
from translations import tr
from utils import apply_software_adjustments

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QMainWindow, QLabel, QSlider
    from config import Configuration
    from components import GPUPixmapItem
    AdjustmentMixinBase = QMainWindow
else:
    AdjustmentMixinBase = object


class AdjustmentMixin(AdjustmentMixinBase):
    if TYPE_CHECKING:
        config: Configuration
        cached_frame_dict: dict
        current_cache_index: int
        is_audio_only: bool
        is_motion_photo: bool
        currentFilePath: str | None
        total_frames: int
        fps: float
        is_scrubbing: bool
        is_playing: bool
        pixmapItem: GPUPixmapItem | None
        loadingOverlay: QLabel
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
        brightnessSpinBox: any
        contrastSpinBox: any
        gammaSpinBox: any
        saturationSpinBox: any
        hueSpinBox: any
        tempSpinBox: any
        exposureSpinBox: any
        sharpenSpinBox: any
        blurSpinBox: any
        frameLabel: QLabel
        currentTimeLabel: QLabel
        isMirrored: bool
        isMirroredVertical: bool
        rotationAngle: int
        is_loading_video: bool
        _last_adj_params: tuple
        _adj_lut: np.ndarray
        _last_rendered_index: int
        _last_base_index: int
        _current_base_image: QImage

        apply_transformations: callable
        save_current_markers: callable
        sync_progress_bar: callable
        update_subtitles_for_current_time: callable

    def reset_adjustments(self):
        self.brightnessSlider.setValue(0)
        self.contrastSlider.setValue(100)
        self.gammaSlider.setValue(100)
        self.saturationSlider.setValue(100)
        if hasattr(self, 'hueSlider') and self.hueSlider: self.hueSlider.setValue(0)
        if hasattr(self, 'tempSlider') and self.tempSlider: self.tempSlider.setValue(0)
        if hasattr(self, 'exposureSlider') and self.exposureSlider: self.exposureSlider.setValue(0)
        if hasattr(self, 'sharpenSlider') and self.sharpenSlider: self.sharpenSlider.setValue(0)
        if hasattr(self, 'blurSlider') and self.blurSlider: self.blurSlider.setValue(0)
        if hasattr(self, 'invertButton') and self.invertButton: self.invertButton.setChecked(False)
        
        if hasattr(self, 'brightnessSpinBox'): self.brightnessSpinBox.setValue(0)
        if hasattr(self, 'contrastSpinBox'): self.contrastSpinBox.setValue(100)
        if hasattr(self, 'gammaSpinBox'): self.gammaSpinBox.setValue(100)
        if hasattr(self, 'saturationSpinBox'): self.saturationSpinBox.setValue(100)
        if hasattr(self, 'hueSpinBox') and self.hueSpinBox: self.hueSpinBox.setValue(0)
        if hasattr(self, 'tempSpinBox') and self.tempSpinBox: self.tempSpinBox.setValue(0)
        if hasattr(self, 'exposureSpinBox') and self.exposureSpinBox: self.exposureSpinBox.setValue(0)
        if hasattr(self, 'sharpenSpinBox') and self.sharpenSpinBox: self.sharpenSpinBox.setValue(0)
        if hasattr(self, 'blurSpinBox') and self.blurSpinBox: self.blurSpinBox.setValue(0)
        
        self.isMirrored = False
        self.isMirroredVertical = False
        self.rotationAngle = 0
        
        if hasattr(self, '_last_adj_params'):
            delattr(self, '_last_adj_params')
        self.update_pixmap_from_cache()
        
        self.apply_transformations(fit=True)
        if not getattr(self, 'is_loading_video', False):
            self.save_current_markers()



    def generate_audio_placeholder(self):
        """Generates a simple flat grey audio placeholder image with text labels."""
        width, height = 1920, 1080
        img = QImage(width, height, QImage.Format.Format_ARGB32)
        img.fill(QColor("#2a2a2a"))
        
        painter = QPainter(img)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        font_sub = QFont("Segoe UI", 24, QFont.Weight.DemiBold)
        font_sub.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 6)
        painter.setFont(font_sub)
        painter.setPen(QColor("#aaaaaa"))
        
        audio_text = tr('audio').upper()
        
        rect_sub = QRectF(0, height / 2 - 100, width, 60)
        painter.drawText(rect_sub, Qt.AlignmentFlag.AlignCenter, audio_text)
        
        filename = os.path.basename(self.currentFilePath) if self.currentFilePath else ""
        rect_title = QRectF(100, height / 2 + 10, width - 200, 200)
        painter.drawText(rect_title, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, filename)
        
        painter.end()
        
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        img.save(buffer, "PNG")
        self.cached_frame_dict = {0: buffer.data().data()}

    def update_pixmap_from_cache(self):
        is_audio = getattr(self, 'is_audio_only', False)
        target_index = 0 if is_audio else self.current_cache_index

        if target_index in getattr(self, 'cached_frame_dict', {}):
            data = self.cached_frame_dict[target_index]

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

            gpu_enabled = self.config.get('gpu_acceleration', False)
            if gpu_enabled:
                if self.pixmapItem is not None:
                    if target_index == getattr(self, '_last_rendered_index', -1):
                        self.pixmapItem.update_params(b, c, g, s, hue_val, temp_val, exposure_mult, invert_val, sharpen_val, blur_val)
                    else:
                        if target_index in getattr(self, 'decoded_frame_cache', {}):
                            image = self.decoded_frame_cache[target_index]
                        else:
                            image = QImage()
                            if isinstance(data, bytes):
                                image.loadFromData(data)
                            elif isinstance(data, str):
                                image.load(data)
                        
                        self.pixmapItem.setImage(image)
                        self.pixmapItem.update_params(b, c, g, s, hue_val, temp_val, exposure_mult, invert_val, sharpen_val, blur_val)
                        
                        fit_val = False
                        if getattr(self, 'is_motion_photo', False):
                            last_idx = getattr(self, '_last_rendered_index', -1)
                            if target_index == 0 or last_idx == 0:
                                fit_val = True
                        
                        self.apply_transformations(fit=fit_val)
                        self._last_rendered_index = target_index
            else:
                # Software rendering path
                if (hasattr(self, '_last_base_index') and self._last_base_index == target_index 
                        and hasattr(self, '_current_base_image') and not self._current_base_image.isNull()):
                    img = self._current_base_image.copy()
                else:
                    if target_index in getattr(self, 'decoded_frame_cache', {}):
                        img = self.decoded_frame_cache[target_index].copy()
                    else:
                        pixmap = QPixmap()
                        if isinstance(data, bytes):
                            pixmap.loadFromData(data)
                        elif isinstance(data, str):
                            pixmap.load(data)
                        img = pixmap.toImage()
                    self._current_base_image = img
                    self._last_base_index = target_index

                if b != 0 or c != 1.0 or g != 1.0 or s != 1.0 or hue_val != 0 or temp_val != 0 or exposure_mult != 1.0 or invert_val != 0 or sharpen_val > 0 or blur_val > 0:
                    img = img.convertToFormat(QImage.Format.Format_ARGB32)
                    width, height = img.width(), img.height()
                    ptr = img.bits()
                    ptr.setsize(img.sizeInBytes())
                    arr = np.frombuffer(ptr, np.uint8).reshape((height, width, 4))
                    apply_software_adjustments(arr, b, c, g, s, hue_val, temp_val, exposure_mult, invert_val, sharpen_val, blur_val)

                pixmap = QPixmap.fromImage(img)

                if self.pixmapItem is not None:
                    self.pixmapItem.setPixmap(pixmap)
                    
                    fit_val = False
                    if getattr(self, 'is_motion_photo', False):
                        last_idx = getattr(self, '_last_rendered_index', -1)
                        if target_index == 0 or last_idx == 0:
                            fit_val = True
                    
                    self.apply_transformations(fit=fit_val)
                    self._last_rendered_index = target_index

            if hasattr(self, 'frameLabel'):
                if is_audio:
                    self.frameLabel.setText(" [Audio]")
                else:
                    self.frameLabel.setText(
                        f" [F: {self.current_cache_index + 1} / {self.total_frames}]"
                    )

        if not self.is_scrubbing and not self.is_playing:
            self.sync_progress_bar()

        if self.fps > 0:
            pos = int((self.current_cache_index * 1000) / self.fps)
            from utils import format_time
            self.currentTimeLabel.setText(format_time(pos))

        if hasattr(self, 'update_subtitles_for_current_time'):
            self.update_subtitles_for_current_time()

        if hasattr(self, 'manage_predecode_pool'):
            self.manage_predecode_pool()
