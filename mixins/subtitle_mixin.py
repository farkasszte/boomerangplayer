import os
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QFileDialog
from PyQt6.QtGui import QColor, QPainter, QFont
from translations import tr
from utils import parse_subtitle_file, get_embedded_subtitles_info, extract_embedded_subtitle, parse_srt

class OutlineLabel(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.outline_color = QColor(0, 0, 0)
        self.outline_width = 2
        self.outline_enabled = False
        self._cached_pixmap = None
        self._cached_text = ""
        self._cached_width = 0
        self._cached_height = 0

    def setOutline(self, enabled, color=QColor(0, 0, 0), width=2):
        self.outline_enabled = enabled
        self.outline_color = color
        self.outline_width = width
        self._cached_pixmap = None
        self.update()

    def _update_cache(self):
        text = self.text()
        if not text:
            self._cached_pixmap = None
            self._cached_text = ""
            return

        rect = self.contentsRect()
        if rect.width() <= 0 or rect.height() <= 0:
            return

        if (self._cached_pixmap is not None 
                and self._cached_text == text 
                and self._cached_width == rect.width() 
                and self._cached_height == rect.height()):
            return

        from PyQt6.QtGui import QPixmap
        pixmap = QPixmap(rect.size())
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        font = self.font()
        painter.setFont(font)

        draw_rect = rect.translated(-rect.topLeft())
        flags = self.alignment() | Qt.TextFlag.TextWordWrap

        # Draw outline
        w = self.outline_width
        painter.setPen(self.outline_color)
        if self.outline_enabled and w > 0:
            for dx in range(-w, w + 1):
                for dy in range(-w, w + 1):
                    if dx == 0 and dy == 0:
                        continue
                    painter.drawText(draw_rect.translated(dx, dy), flags, text)

        # Draw foreground text on top
        original_color = self.palette().color(self.foregroundRole())
        painter.setPen(original_color)
        painter.drawText(draw_rect, flags, text)

        painter.end()

        # Cache values
        self._cached_pixmap = pixmap
        self._cached_text = text
        self._cached_width = rect.width()
        self._cached_height = rect.height()

    def paintEvent(self, event):
        if not self.outline_enabled or self.outline_width <= 0:
            super().paintEvent(event)
            return

        # 1. Let QLabel paint the background and text first
        super().paintEvent(event)

        # 2. Update cache and blit the cached pixmap
        self._update_cache()

        if self._cached_pixmap is not None:
            painter = QPainter(self)
            rect = self.contentsRect()
            painter.drawPixmap(rect.topLeft(), self._cached_pixmap)
            painter.end()

class SubtitleMixin:
    def init_subtitle_state(self):
        self.subtitles = []
        self.subtitleFilePath = None
        self._last_subtitle_text = None
        
        # Subtitle overlay label using our custom OutlineLabel
        self.subtitleLabel = OutlineLabel(self.view)
        self.subtitleLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitleLabel.setWordWrap(True)
        self.subtitleLabel.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.subtitleLabel.hide()
        
        self.update_sub_style()

    def update_sub_style(self):
        if not hasattr(self, 'subtitleLabel'):
            return
            
        font_family = self.config.get('subtitle_font_family', 'Segoe UI')
        font_size = self.config.get('subtitle_font_size', 24)
        text_color_name = self.config.get('subtitle_text_color', 'White')
        bg_color_name = self.config.get('subtitle_bg_color', 'Black')
        opacity = self.config.get('subtitle_bg_opacity', 60)

        color_map = {
            'White': '#ffffff', 'Yellow': '#ffff00', 'Cyan': '#00ffff',
            'Green': '#00ff00', 'Magenta': '#ff00ff', 'Red': '#ff0000',
            'Black': '#000000', 'Dark Grey': '#222222', 'Navy Blue': '#000080'
        }
        bg_map = {
            'Black': '0, 0, 0', 'Dark Grey': '34, 34, 34', 'Navy Blue': '0, 0, 128'
        }

        color_hex = color_map.get(text_color_name, '#ffffff')
        
        if bg_color_name == 'None':
            bg_style = "background-color: transparent;"
        else:
            rgb = bg_map.get(bg_color_name, '0, 0, 0')
            bg_style = f"background-color: rgba({rgb}, {opacity / 100.0});"

        style = f"""
            QLabel {{
                color: {color_hex};
                font-family: '{font_family}';
                font-size: {font_size}px;
                font-weight: bold;
                {bg_style}
                border-radius: 6px;
                padding: 6px 16px;
            }}
        """
        self.subtitleLabel.setStyleSheet(style)
        
        # Explicitly set QFont with correct family and pixel size, so QFontMetrics and OutlineLabel painter use it correctly.
        font = QFont(font_family)
        font.setPixelSize(font_size)
        font.setBold(True)
        self.subtitleLabel.setFont(font)
        
        # Apply outline styling
        outline_enabled = self.config.get('subtitle_outline_enabled', False)
        outline_width = self.config.get('subtitle_outline_width', 2)
        outline_color_name = self.config.get('subtitle_outline_color', 'Black')
        outline_color_hex = color_map.get(outline_color_name, '#000000')
        self.subtitleLabel.setOutline(outline_enabled, QColor(outline_color_hex), outline_width)
        
        # Apply drop shadow graphics effect
        shadow_enabled = self.config.get('subtitle_shadow_enabled', False)
        if shadow_enabled:
            from PyQt6.QtWidgets import QGraphicsDropShadowEffect
            shadow_blur = self.config.get('subtitle_shadow_blur', 5)
            shadow_dx = self.config.get('subtitle_shadow_dx', 2)
            shadow_dy = self.config.get('subtitle_shadow_dy', 2)
            shadow_color_name = self.config.get('subtitle_shadow_color', 'Black')
            shadow_color_hex = color_map.get(shadow_color_name, '#000000')
            
            effect = QGraphicsDropShadowEffect(self)
            effect.setBlurRadius(shadow_blur)
            effect.setOffset(shadow_dx, shadow_dy)
            effect.setColor(QColor(shadow_color_hex))
            self.subtitleLabel.setGraphicsEffect(effect)
        else:
            self.subtitleLabel.setGraphicsEffect(None)
            
        self.position_subtitle_label()

    def position_subtitle_label(self):
        if not hasattr(self, 'subtitleLabel') or not self.subtitleLabel.isVisible():
            return
            
        view_w = self.view.width()
        view_h = self.view.height()
        
        text = self.subtitleLabel.text()
        if not text:
            return

        # Use QFontMetrics to compute the text width accurately
        from PyQt6.QtGui import QFontMetrics
        metrics = QFontMetrics(self.subtitleLabel.font())
        
        # Preserving manual line-breaks, find the longest line's width
        lines = text.split('\n')
        max_line_w = 0
        for line in lines:
            max_line_w = max(max_line_w, metrics.horizontalAdvance(line))
            
        # Add padding (16px left + 16px right = 32px) and a safety margin
        text_w = max_line_w + 32 + 10
        
        # Maximum allowed width is 85% of the screen width
        max_allowed_w = max(200, int(view_w * 0.85))
        
        # Limit the label width to max_allowed_w (which triggers wrapping if exceeded)
        target_w = min(text_w, max_allowed_w)
        self.subtitleLabel.setFixedWidth(target_w)
        
        # Allow vertical resizing to compute height dynamically
        self.subtitleLabel.setMinimumHeight(0)
        self.subtitleLabel.setMaximumHeight(view_h - 40)
        self.subtitleLabel.adjustSize()
        
        lbl_w = self.subtitleLabel.width()
        lbl_h = self.subtitleLabel.height()
        
        # Center horizontally, with horizontal offset (as percentage of view width)
        h_offset = self.config.get('subtitle_h_offset', 0)
        h_offset_px = int(view_w * (h_offset / 100.0))
        x = (view_w - lbl_w) // 2 + h_offset_px
        
        # Offset from bottom (as percentage of view height)
        v_offset = self.config.get('subtitle_v_offset', 5)
        v_offset_px = int(view_h * (v_offset / 100.0))
        margin_bottom = v_offset_px
        if getattr(self, 'is_full_screen', False) and hasattr(self, 'controlsCard') and self.controlsCard.isVisible():
            margin_bottom += self.controlsCard.height()
        y = view_h - lbl_h - margin_bottom
        
        self.subtitleLabel.move(x, y)

    def on_enable_subtitles_changed(self, checked):
        self.config['enable_subtitles'] = checked
        self.config.save()
        if not checked:
            self.subtitleLabel.hide()
        else:
            self.update_subtitles_for_current_time()

    def browse_subtitle_file(self):
        title = tr('load_subtitle_file')
        filter_str = f"{tr('subtitle_files')} (*.srt *.vtt *.ass *.ssa *.sub)"
        filepath, _ = QFileDialog.getOpenFileName(self, title, "", filter_str)
        if filepath:
            self.load_subtitles(filepath)

    def load_subtitles(self, filepath):
        if not os.path.exists(filepath):
            return
            
        self.subtitleFilePath = filepath
        self.subtitles = parse_subtitle_file(filepath, fps=getattr(self, 'fps', 30.0))
        self._last_subtitle_text = None
        print(f"[Subtitles] Loaded {len(self.subtitles)} cues from {filepath}")
        
        # Update combo to show External File is active
        self.subTrackCombo.blockSignals(True)
        ext_idx = -1
        for i in range(self.subTrackCombo.count()):
            if self.subTrackCombo.itemData(i) == -2:
                ext_idx = i
                break
        if ext_idx == -1:
            self.subTrackCombo.addItem(tr('load_subtitle_file'), -2)
            ext_idx = self.subTrackCombo.count() - 1
        self.subTrackCombo.setCurrentIndex(ext_idx)
        self.subTrackCombo.blockSignals(False)
        
        self.update_subtitles_for_current_time()

    def populate_subtitle_tracks(self, video_path):
        if not hasattr(self, 'subTrackCombo'):
            return
        self.subTrackCombo.blockSignals(True)
        self.subTrackCombo.clear()
        self.subTrackCombo.addItem(tr('off'), -1)
        
        tracks = get_embedded_subtitles_info(video_path)
        for t in tracks:
            idx = t['index']
            lang = t['language']
            codec = t['codec']
            title = t['title']
            
            label = f"Track {idx}: {lang.upper()} ({codec})"
            if title:
                label += f" - {title}"
            self.subTrackCombo.addItem(label, idx)
        self.subTrackCombo.blockSignals(False)

    def on_sub_track_changed(self, idx):
        if idx < 0 or idx >= self.subTrackCombo.count():
            return
            
        stream_index = self.subTrackCombo.itemData(idx)
        if stream_index == -1: # Off
            self.subtitleLabel.hide()
            self.subtitles = []
            self._last_subtitle_text = None
        elif stream_index == -2: # External file
            pass
        else: # Embedded
            if self.currentFilePath and os.path.exists(self.currentFilePath):
                srt_content = extract_embedded_subtitle(self.currentFilePath, stream_index)
                self.subtitles = parse_srt(srt_content)
                self._last_subtitle_text = None
                print(f"[Subtitles] Extracted and loaded {len(self.subtitles)} embedded cues from stream {stream_index}")
                self.update_subtitles_for_current_time()

    def auto_load_subtitles_for_video(self, video_path):
        if not video_path:
            return
            
        self.populate_subtitle_tracks(video_path)
            
        dir_name = os.path.dirname(video_path)
        base_name, _ = os.path.splitext(os.path.basename(video_path))
        
        sub_exts = ['.srt', '.vtt', '.sub', '.ass', '.ssa']
        for ext in sub_exts:
            sub_path = os.path.join(dir_name, base_name + ext)
            if os.path.exists(sub_path):
                self.load_subtitles(sub_path)
                return
            sub_path_lower = os.path.join(dir_name, base_name + ext.upper())
            if os.path.exists(sub_path_lower):
                self.load_subtitles(sub_path_lower)
                return

        # If no external file is found, but there are embedded tracks, load the first one!
        if self.subTrackCombo.count() > 1:
            self.subTrackCombo.setCurrentIndex(1)

    def update_subtitles_for_current_time(self):
        if not hasattr(self, 'subtitleLabel'):
            return
            
        if not self.subtitles or not self.config.get('enable_subtitles', True):
            if self.subtitleLabel.isVisible():
                self.subtitleLabel.hide()
                self._last_subtitle_text = None
            return

        # Calculate current time in ms
        fps = getattr(self, 'fps', 30.0)
        if fps <= 0:
            fps = 30.0
        current_time = int((self.current_cache_index * 1000) / fps)
        
        # Apply offset delay
        offset = self.config.get('subtitle_offset', 0)
        adjusted_time = current_time + offset

        # Find matching subtitle
        active_text = ""
        for cue in self.subtitles:
            if cue['start'] <= adjusted_time <= cue['end']:
                active_text = cue['text']
                break

        # Only update UI when subtitle text changes
        last_text = getattr(self, '_last_subtitle_text', None)
        if active_text != last_text:
            self._last_subtitle_text = active_text
            if active_text:
                self.subtitleLabel.setText(active_text)
                self.subtitleLabel.show()
                self.position_subtitle_label()
            else:
                self.subtitleLabel.hide()

    # --- UI adjustment slots ---
    def on_sub_font_changed(self, idx):
        font = self.subFontCombo.itemText(idx)
        self.config['subtitle_font_family'] = font
        self.config.save()
        self.update_sub_style()

    def on_sub_size_slider_changed(self, val):
        self.subFontSizeSpin.blockSignals(True)
        self.subFontSizeSpin.setValue(val)
        self.subFontSizeSpin.blockSignals(False)
        self.config['subtitle_font_size'] = val
        self.config.save()
        self.update_sub_style()

    def on_sub_size_spin_changed(self, val):
        self.subFontSizeSlider.blockSignals(True)
        self.subFontSizeSlider.setValue(val)
        self.subFontSizeSlider.blockSignals(False)
        self.config['subtitle_font_size'] = val
        self.config.save()
        self.update_sub_style()

    def on_sub_text_color_changed(self, idx):
        color = self.subTextColorCombo.itemData(idx)
        if not color:
            color = self.subTextColorCombo.itemText(idx)
        self.config['subtitle_text_color'] = color
        self.config.save()
        self.update_sub_style()

    def on_sub_bg_color_changed(self, idx):
        color = self.subBgColorCombo.itemData(idx)
        if not color:
            color = self.subBgColorCombo.itemText(idx)
        self.config['subtitle_bg_color'] = color
        self.config.save()
        self.update_sub_style()

    def on_sub_opacity_slider_changed(self, val):
        self.subBgOpacitySpin.blockSignals(True)
        self.subBgOpacitySpin.setValue(val)
        self.subBgOpacitySpin.blockSignals(False)
        self.config['subtitle_bg_opacity'] = val
        self.config.save()
        self.update_sub_style()

    def on_sub_opacity_spin_changed(self, val):
        self.subBgOpacitySlider.blockSignals(True)
        self.subBgOpacitySlider.setValue(val)
        self.subBgOpacitySlider.blockSignals(False)
        self.config['subtitle_bg_opacity'] = val
        self.config.save()
        self.update_sub_style()

    def on_sub_offset_slider_changed(self, val):
        self.subOffsetSpin.blockSignals(True)
        self.subOffsetSpin.setValue(val)
        self.subOffsetSpin.blockSignals(False)
        self.config['subtitle_offset'] = val
        self.config.save()
        self.update_subtitles_for_current_time()

    def on_sub_offset_spin_changed(self, val):
        self.subOffsetSlider.blockSignals(True)
        self.subOffsetSlider.setValue(val)
        self.subOffsetSlider.blockSignals(False)
        self.config['subtitle_offset'] = val
        self.config.save()
        self.update_subtitles_for_current_time()

    def toggle_subtitle_panel(self):
        if not hasattr(self, 'subtitleContainer'):
            return
        is_visible = self.subtitleContainer.isVisible()
        
        # Enforce mutual exclusivity with settings panel on the left
        if not is_visible:
            if hasattr(self, 'settingsContainer') and self.settingsContainer.isVisible():
                self.settingsContainer.hide()
            if hasattr(self, 'globalSettingsContainer') and self.globalSettingsContainer.isVisible():
                self.globalSettingsContainer.hide()
                
        self.subtitleContainer.setVisible(not is_visible)
        
        if hasattr(self, 'update_sidebar_fullscreen_state'):
            self.update_sidebar_fullscreen_state()
        if hasattr(self, 'update_sidebar_margins'):
            self.update_sidebar_margins()

        if not is_visible and not getattr(self, 'is_full_screen', False):
            sizes = self.mainSplitter.sizes()
            if len(sizes) > 2 and sizes[2] < 250:
                sizes[2] = 250
                self.mainSplitter.setSizes(sizes)

    def adjust_subtitle_delay(self, ms):
        current = self.config.get('subtitle_offset', 0)
        new_val = max(-10000, min(10000, current + ms))
        self.config['subtitle_offset'] = new_val
        self.config.save()

        # Update UI controls
        if hasattr(self, 'subOffsetSpin'):
            self.subOffsetSpin.blockSignals(True)
            self.subOffsetSpin.setValue(new_val)
            self.subOffsetSpin.blockSignals(False)
        if hasattr(self, 'subOffsetSlider'):
            self.subOffsetSlider.blockSignals(True)
            self.subOffsetSlider.setValue(new_val)
            self.subOffsetSlider.blockSignals(False)

        # Update subtitles for current time
        self.update_subtitles_for_current_time()

        # Show on-screen notification using InfoBar
        from qfluentwidgets import InfoBar, InfoBarPosition
        from translations import tr
        
        sign = "+" if new_val > 0 else ""
        content_text = f"{tr('subtitle_offset')}: {sign}{new_val} ms"
        
        InfoBar.info(
            title=tr('subtitles'),
            content=content_text,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=1500,
            parent=self
        )

    def on_sub_outline_changed(self, checked):
        self.config['subtitle_outline_enabled'] = checked
        self.config.save()
        self.update_sub_style()

    def on_sub_outline_width_changed(self, val):
        self.config['subtitle_outline_width'] = val
        self.config.save()
        self.update_sub_style()

    def on_sub_outline_color_changed(self, idx):
        color = self.subOutlineColorCombo.itemData(idx)
        if not color:
            color = self.subOutlineColorCombo.itemText(idx)
        self.config['subtitle_outline_color'] = color
        self.config.save()
        self.update_sub_style()

    def on_sub_shadow_changed(self, checked):
        self.config['subtitle_shadow_enabled'] = checked
        self.config.save()
        self.update_sub_style()

    def on_sub_shadow_blur_changed(self, val):
        self.config['subtitle_shadow_blur'] = val
        self.config.save()
        self.update_sub_style()

    def on_sub_shadow_dx_changed(self, val):
        self.config['subtitle_shadow_dx'] = val
        self.config.save()
        self.update_sub_style()

    def on_sub_shadow_dy_changed(self, val):
        self.config['subtitle_shadow_dy'] = val
        self.config.save()
        self.update_sub_style()

    def on_sub_shadow_color_changed(self, idx):
        color = self.subShadowColorCombo.itemData(idx)
        if not color:
            color = self.subShadowColorCombo.itemText(idx)
        self.config['subtitle_shadow_color'] = color
        self.config.save()
        self.update_sub_style()

    def on_sub_v_offset_changed(self, val):
        self.config['subtitle_v_offset'] = val
        self.config.save()
        self.position_subtitle_label()

    def on_sub_h_offset_changed(self, val):
        self.config['subtitle_h_offset'] = val
        self.config.save()
        self.position_subtitle_label()
