"""
ExportSegmentMixin — save/export loop segment of the video.
"""

import os
import subprocess
from PyQt6.QtWidgets import QFileDialog, QDialog
from PyQt6.QtGui import QImage
from PyQt6.QtCore import Qt
from translations import tr
from utils import get_resource_path

from components.marker_dialogs import SaveLoopOptionsDialog

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QMainWindow, QSlider
    from config import Configuration
    ExportSegmentMixinBase = QMainWindow
else:
    ExportSegmentMixinBase = object


class ExportSegmentMixin(ExportSegmentMixinBase):
    if TYPE_CHECKING:
        current_cache_index: int
        cached_frame_dict: dict
        fps: float
        speedSlider: QSlider
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
        currentVideoPath: str | None
        total_frames: int
        progressBar: any
        isMirrored: bool
        isMirroredVertical: bool
        rotationAngle: int
        is_motion_photo: bool
        
        get_active_loop_range: callable
        update_pixmap_from_cache: callable
        _get_adj_lut: callable

    def save_loop_segment(self):
        if not self.currentFilePath:
            return

        dialog = SaveLoopOptionsDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        is_lossless = dialog.modeCombo.currentIndex() == 0
        fmt_text = dialog.formatCombo.currentText()
        codec_idx = dialog.codecCombo.currentIndex()
        if codec_idx == 0:
            codec_lib = "libx264"
        elif codec_idx == 1:
            codec_lib = "libx265"
        else:
            codec_lib = getattr(dialog, 'av1_encoder', "libx264")
        quality_val = dialog.qualitySlider.value()
        scale_idx = dialog.scaleCombo.currentIndex()
        include_drawings = dialog.drawingsCheckbox.isChecked()
        apply_adjustments = dialog.adjustmentsCheckbox.isChecked()
        apply_speed = dialog.speedCheckbox.isChecked()
        mute_audio = dialog.muteCheckbox.isChecked()

        input_file = getattr(self, 'currentVideoPath', self.currentFilePath)
        is_motion = getattr(self, 'is_motion_photo', False)

        # Determine file extension and filter
        ext = ".mp4"
        file_filter = "Video Files (*.mp4)"
        if is_lossless:
            ext = os.path.splitext(input_file)[1] or ".mp4"
            file_filter = f"Video Files (*{ext} *.mp4 *.mkv)"
        else:
            if "MP4" in fmt_text:
                ext = ".mp4"
                file_filter = "Video Files (*.mp4)"
            elif "MKV" in fmt_text:
                ext = ".mkv"
                file_filter = "Video Files (*.mkv)"
            elif "GIF" in fmt_text:
                ext = ".gif"
                file_filter = "Animated GIF (*.gif)"

        fileName, _ = QFileDialog.getSaveFileName(self, tr('save_loop'), f"loop{ext}", file_filter)
        if not fileName:
            return

        ffmpeg_path = get_resource_path("ffmpeg.exe" if os.name == 'nt' else "ffmpeg")
        if not os.path.exists(ffmpeg_path):
            ffmpeg_path = "ffmpeg"

        start_f, end_f = self.get_active_loop_range()
        
        # Map player frames to actual video frames for ffmpeg
        if is_motion:
            start_f_vid = max(0, start_f - 1)
            end_f_vid = max(0, end_f - 1)
        else:
            start_f_vid = start_f
            end_f_vid = end_f

        if self.fps > 0:
            start_sec = max(0.0, (start_f_vid / self.fps) - 0.001)
            frames_count = max(1, end_f_vid - start_f_vid)
            duration_sec = (frames_count / self.fps) + 0.005
        else:
            start_sec = 0.0
            duration_sec = (end_f_vid - start_f_vid) / 30.0

        speed_mult = self.speedSlider.value() / 100.0 if hasattr(self, 'speedSlider') else 1.0

        if include_drawings and not is_lossless:
            # Case C: Re-encode WITH drawings (Piped raw frames)
            import numpy as np
            from PyQt6.QtGui import QPainter, QPixmap, QTransform
            from PyQt6.QtCore import QRectF, QCoreApplication
            from PyQt6.QtWidgets import QProgressDialog
            from qfluentwidgets import InfoBar, InfoBarPosition

            # Function to extract single frame image on the fly if not cached
            def get_frame_image(idx):
                if idx in self.cached_frame_dict:
                    data = self.cached_frame_dict[idx]
                    img = QImage()
                    if isinstance(data, bytes):
                        img.loadFromData(data)
                    elif isinstance(data, str):
                        img.load(data)
                    if not img.isNull():
                        return img
                
                # Extract on the fly
                import tempfile
                temp_file = os.path.join(tempfile.gettempdir(), f"export_temp_{idx}.jpg")
                sec = (idx - 1 if is_motion else idx) / (self.fps if self.fps > 0 else 30.0)
                cmd_extract = [
                    ffmpeg_path, "-y",
                    "-ss", f"{sec:.6f}",
                    "-i", input_file,
                    "-vframes", "1",
                    "-q:v", "2",
                    temp_file
                ]
                cflags = 0
                if os.name == 'nt':
                    cflags = subprocess.CREATE_NO_WINDOW
                try:
                    subprocess.run(cmd_extract, creationflags=cflags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    img = QImage(temp_file)
                    try:
                        os.remove(temp_file)
                    except OSError:
                        pass
                    if not img.isNull():
                        return img
                except Exception as e:
                    print(f"Error extracting frame {idx}: {e}")
                
                return QImage()

            def apply_image_effects(img):
                if not apply_adjustments:
                    return img
                
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

                # Mirroring & rotation
                transform = QTransform()
                if getattr(self, 'isMirrored', False):
                    transform.scale(-1, 1)
                if getattr(self, 'isMirroredVertical', False):
                    transform.scale(1, -1)
                angle = int(getattr(self, 'rotationAngle', 0)) % 360
                if angle != 0:
                    transform.rotate(angle)
                if not transform.isIdentity():
                    img = img.transformed(transform, Qt.TransformationMode.SmoothTransformation)
                
                return img

            # Save state
            original_pixmap = self.pixmapItem.pixmap()
            original_index = self.current_cache_index

            # Get first frame to determine resolution scale size
            first_img = get_frame_image(start_f)
            if first_img.isNull():
                print("Error: Could not retrieve any video frames for loop export.")
                return
            
            # Temporary setup to calculate output dimensions after scale
            scale_factors = [1.0, 0.75, 0.5, 2.0, 1.5]
            scale_factor = scale_factors[scale_idx]

            first_adjusted = apply_image_effects(first_img)
            self.pixmapItem.setPixmap(QPixmap.fromImage(first_adjusted))
            rect = self.pixmapItem.pixmap().rect()
            
            out_width = rect.width()
            out_height = rect.height()
            if scale_factor != 1.0:
                out_width = int(out_width * scale_factor)
                out_height = int(out_height * scale_factor)
            # Ensure dimensions are even for H.264
            out_width = (out_width // 2) * 2
            out_height = (out_height // 2) * 2

            # Configure dynamic FFmpeg arguments
            audio_input_args = []
            audio_map_args = []
            if not mute_audio:
                audio_input_args = ["-ss", f"{start_sec:.6f}", "-t", f"{duration_sec:.6f}", "-i", input_file]
                if apply_speed and speed_mult != 1.0:
                    af_filters = []
                    temp = speed_mult
                    while temp > 2.0:
                        af_filters.append("atempo=2.0")
                        temp /= 2.0
                    while temp < 0.5:
                        af_filters.append("atempo=0.5")
                        temp /= 0.5
                    if abs(temp - 1.0) > 0.01:
                        af_filters.append(f"atempo={temp:.3f}")
                    af_str = ",".join(af_filters)
                    audio_map_args = ["-filter_complex", f"[1:a]{af_str}[aout]", "-map", "[aout]"]
                else:
                    audio_map_args = ["-map", "1:a?", "-c:a", "aac", "-b:a", "192k"]
            else:
                audio_map_args = ["-an"]

            # Video/Palette generation for GIF or X264 encoding options
            filter_complex_parts = []
            video_map_label = "0:v"
            
            if apply_speed and speed_mult != 1.0:
                filter_complex_parts.append(f"[0:v]setpts=PTS/{speed_mult:.3f}[vout]")
                video_map_label = "[vout]"

            if "GIF" in fmt_text:
                if video_map_label == "[vout]":
                    filter_complex_parts.append("[vout]split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse[gifout]")
                else:
                    filter_complex_parts.append("[0:v]split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse[gifout]")
                video_map_label = "[gifout]"
                audio_map_args = ["-an"]
                encode_args = []
            else:
                crf = int((100 - quality_val) * 0.4) + 10
                if codec_lib == "av1_nvenc":
                    encode_args = ["-c:v", "av1_nvenc", "-rc", "vbr", "-cq", str(crf), "-preset", "p4", "-pix_fmt", "yuv420p"]
                elif codec_lib == "av1_amf":
                    encode_args = ["-c:v", "av1_amf", "-rc", "qvbr", "-qvbr_quality_level", str(crf), "-preset", "quality", "-pix_fmt", "yuv420p"]
                elif codec_lib == "av1_qsv":
                    encode_args = ["-c:v", "av1_qsv", "-global_quality", str(crf), "-preset", "medium", "-pix_fmt", "yuv420p"]
                elif codec_lib == "libx265":
                    encode_args = ["-c:v", "libx265", "-crf", str(crf), "-preset", "fast", "-pix_fmt", "yuv420p"]
                else:
                    encode_args = ["-c:v", "libx264", "-crf", str(crf), "-preset", "fast", "-pix_fmt", "yuv420p"]

            if filter_complex_parts:
                filter_complex_arg = ["-filter_complex", ";".join(filter_complex_parts)]
            else:
                filter_complex_arg = []

            cmd = [
                ffmpeg_path, "-y",
                "-f", "rawvideo",
                "-pixel_format", "rgba",
                "-video_size", f"{out_width}x{out_height}",
                "-framerate", f"{self.fps if self.fps > 0 else 30.0:.6f}",
                "-i", "-"
            ] + audio_input_args + filter_complex_arg + ["-map", video_map_label] + audio_map_args + encode_args + [fileName]

            cflags = 0
            if os.name == 'nt':
                cflags = subprocess.CREATE_NO_WINDOW
                
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=cflags
            )

            progress = QProgressDialog(tr('save_loop'), tr('cancel'), start_f, end_f, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            progress.setValue(start_f)

            try:
                for f in range(start_f, end_f + 1):
                    if progress.wasCanceled():
                        break
                    
                    progress.setValue(f)
                    progress.setLabelText(f"{tr('save_loop')}... ({f - start_f + 1}/{end_f - start_f + 1})")
                    QCoreApplication.processEvents()
                    
                    img = get_frame_image(f)
                    if img.isNull():
                        continue
                        
                    adjusted_img = apply_image_effects(img)
                    self.pixmapItem.setPixmap(QPixmap.fromImage(adjusted_img))
                    
                    rect = self.pixmapItem.pixmap().rect()
                    out_pixmap = QPixmap(rect.size())
                    out_pixmap.fill(Qt.GlobalColor.black)

                    painter = QPainter(out_pixmap)
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                    self.view.scene().render(painter, QRectF(rect), QRectF(rect))
                    painter.end()

                    final_img = out_pixmap.toImage()
                    
                    if scale_factor != 1.0 or final_img.width() != out_width or final_img.height() != out_height:
                        final_img = final_img.scaled(out_width, out_height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    
                    final_img = final_img.convertToFormat(QImage.Format.Format_RGBA8888)
                    
                    ptr = final_img.bits()
                    ptr.setsize(final_img.sizeInBytes())
                    process.stdin.write(bytes(ptr))
            except Exception as e:
                print(f"Error during frame piping: {e}")
            finally:
                if process.stdin:
                    process.stdin.close()
                process.wait()
                
                # Restore original state
                self.pixmapItem.setPixmap(original_pixmap)
                self.current_cache_index = original_index
                self.update_pixmap_from_cache()
                progress.close()

                if progress.wasCanceled():
                    try:
                        if os.path.exists(fileName):
                            os.remove(fileName)
                    except OSError:
                        pass
                else:
                    InfoBar.success(
                        title=tr('save_loop'),
                        content=tr('ok'),
                        orient=Qt.Orientation.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=2000,
                        parent=self
                    )

        else:
            # Case A & B: Lossless Stream Copy or Custom Re-encode WITHOUT drawings (Fast ffmpeg direct execution)
            vf_filters = []
            
            if not is_lossless and apply_adjustments:
                # Mirror
                if getattr(self, 'isMirrored', False):
                    vf_filters.append("hflip")
                if getattr(self, 'isMirroredVertical', False):
                    vf_filters.append("vflip")
                # Rotate
                angle = int(getattr(self, 'rotationAngle', 0)) % 360
                if angle == 90:
                    vf_filters.append("transpose=1")
                elif angle == 180:
                    vf_filters.append("hflip,vflip")
                elif angle == 270:
                    vf_filters.append("transpose=2")

                # Color Adjustments
                b_val = self.brightnessSlider.value() / 100.0
                c_val = self.contrastSlider.value() / 100.0
                g_val = self.gammaSlider.value() / 100.0
                exp_val = self.exposureSlider.value() if hasattr(self, 'exposureSlider') else 0
                b_val += exp_val / 100.0
                
                vf_filters.append(f"eq=brightness={b_val:.3f}:contrast={c_val:.3f}:gamma={g_val:.3f}")

                # Hue / Saturation
                hue_val = self.hueSlider.value() if hasattr(self, 'hueSlider') else 0
                sat_val = self.saturationSlider.value() / 100.0
                if hue_val != 0 or sat_val != 1.0:
                    vf_filters.append(f"hue=h={hue_val}:s={sat_val:.3f}")

                # Invert
                if hasattr(self, 'invertButton') and self.invertButton.isChecked():
                    vf_filters.append("negate")

                # Sharpen / Blur
                sharpen_val = self.sharpenSlider.value() if hasattr(self, 'sharpenSlider') else 0
                blur_val = self.blurSlider.value() if hasattr(self, 'blurSlider') else 0
                if sharpen_val > 0:
                    amount = (sharpen_val / 100.0) * 1.5
                    vf_filters.append(f"unsharp=5:5:{amount:.3f}:5:5:0.0")
                if blur_val > 0:
                    rad = (blur_val / 100.0) * 5.0
                    vf_filters.append(f"gblur=sigma={rad:.3f}")

            # Scale factor
            scale_factors = [1.0, 0.75, 0.5, 2.0, 1.5]
            scale_factor = scale_factors[scale_idx]
            if not is_lossless and scale_factor != 1.0:
                vf_filters.append(f"scale=trunc(iw*{scale_factor}/2)*2:trunc(ih*{scale_factor}/2)*2")

            # Playback speed multiplier
            if not is_lossless and apply_speed and speed_mult != 1.0:
                vf_filters.append(f"setpts=PTS/{speed_mult:.3f}")

            # Audio setup
            audio_args = []
            if mute_audio:
                audio_args = ["-an"]
            else:
                if is_lossless:
                    audio_args = ["-c:a", "copy"]
                else:
                    if apply_speed and speed_mult != 1.0:
                        af_filters = []
                        temp = speed_mult
                        while temp > 2.0:
                            af_filters.append("atempo=2.0")
                            temp /= 2.0
                        while temp < 0.5:
                            af_filters.append("atempo=0.5")
                            temp /= 0.5
                        if abs(temp - 1.0) > 0.01:
                            af_filters.append(f"atempo={temp:.3f}")
                        
                        af_str = ",".join(af_filters)
                        audio_args = ["-filter_complex", f"[0:a]{af_str}[aout]", "-map", "[aout]"]
                    else:
                        audio_args = ["-map", "0:a?", "-c:a", "aac", "-b:a", "192k"]

            # Video setup / maps
            video_map_args = ["-map", "0:v"]
            vf_arg = []
            if vf_filters:
                vf_arg = ["-vf", ",".join(vf_filters)]

            # Encoding arguments (CRF vs GIF vs Copy)
            if is_lossless:
                encode_args = ["-c:v", "copy"]
            elif "GIF" in fmt_text:
                vf_str = ",".join(vf_filters)
                if vf_str:
                    complex_filter = f"[0:v]{vf_str}[vfilt];[vfilt]split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse[gifout]"
                else:
                    complex_filter = "[0:v]split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse[gifout]"
                video_map_args = ["-filter_complex", complex_filter, "-map", "[gifout]"]
                audio_args = ["-an"]
                encode_args = []
                vf_arg = []
            else:
                crf = int((100 - quality_val) * 0.4) + 10
                if codec_lib == "av1_nvenc":
                    encode_args = ["-c:v", "av1_nvenc", "-rc", "vbr", "-cq", str(crf), "-preset", "p4", "-pix_fmt", "yuv420p"]
                elif codec_lib == "av1_amf":
                    encode_args = ["-c:v", "av1_amf", "-rc", "qvbr", "-qvbr_quality_level", str(crf), "-preset", "quality", "-pix_fmt", "yuv420p"]
                elif codec_lib == "av1_qsv":
                    encode_args = ["-c:v", "av1_qsv", "-global_quality", str(crf), "-preset", "medium", "-pix_fmt", "yuv420p"]
                elif codec_lib == "libx265":
                    encode_args = ["-c:v", "libx265", "-crf", str(crf), "-preset", "fast", "-pix_fmt", "yuv420p"]
                else:
                    encode_args = ["-c:v", "libx264", "-crf", str(crf), "-preset", "fast", "-pix_fmt", "yuv420p"]

            # Assemble command
            if end_f == 0 or end_f >= self.progressBar.maximum():
                cmd = [
                    ffmpeg_path, "-y",
                    "-ss", f"{start_sec:.6f}",
                    "-i", input_file
                ] + video_map_args + vf_arg + audio_args + encode_args + [fileName]
            else:
                cmd = [
                    ffmpeg_path, "-y",
                    "-ss", f"{start_sec:.6f}",
                    "-i", input_file,
                    "-t", f"{duration_sec:.6f}"
                ] + video_map_args + vf_arg + audio_args + encode_args + [fileName]

            try:
                creationflags = 0
                if os.name == 'nt':
                    creationflags = subprocess.CREATE_NO_WINDOW
                subprocess.Popen(cmd, creationflags=creationflags)
                
                from qfluentwidgets import InfoBar, InfoBarPosition
                InfoBar.info(
                    title=tr('save_loop'),
                    content=tr('export_started'),
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
            except Exception as e:
                print(f"Error saving loop: {e}")
