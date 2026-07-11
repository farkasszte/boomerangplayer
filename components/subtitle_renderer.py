from typing import Any
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QFont, QColor

class SubtitleRenderer:
    """Handles rendering of subtitles onto a QPainter viewport."""

    _COLOR_MAP = {
        'White': '#ffffff', 'Yellow': '#ffff00', 'Cyan': '#00ffff',
        'Green': '#00ff00', 'Magenta': '#ff00ff', 'Red': '#ff0000',
        'Black': '#000000', 'Dark Grey': '#222222', 'Navy Blue': '#000080'
    }

    @staticmethod
    def _resolve(name_or_hex, default='#ffffff'):
        if name_or_hex.startswith('#'):
            return name_or_hex
        return SubtitleRenderer._COLOR_MAP.get(name_or_hex, default)

    @staticmethod
    def _resolve_bg_rgb(name_or_hex):
        if name_or_hex.startswith('#'):
            c = QColor(name_or_hex)
            return (c.red(), c.green(), c.blue())
        bg_map = {
            'Black': (0, 0, 0), 'Dark Grey': (34, 34, 34), 'Navy Blue': (0, 0, 128)
        }
        return bg_map.get(name_or_hex, (0, 0, 0))
    
    @staticmethod
    def draw_subtitles(painter: QPainter, active_text: str, viewport_w: int, viewport_h: int, win: Any) -> None:
        painter.save()
        # Reset transform to paint in viewport (pixel) coordinates
        painter.resetTransform()

        font_family = win.config.get('subtitle_font_family', 'Segoe UI')
        font_size = win.config.get('subtitle_font_size', 24)
        font = QFont(font_family)
        font.setPixelSize(font_size)
        font.setBold(True)
        painter.setFont(font)

        # Define maximum width for subtitle block
        max_allowed_w = max(200, int(viewport_w * 0.85))
        
        # We start with a large temporary rectangle to measure the wrapped text height
        temp_rect = QRectF(0, 0, max_allowed_w, 10000)
        flags = Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap
        
        # Measure wrapped text bounding rect
        bounds = painter.boundingRect(temp_rect, flags, active_text)
        
        padding_h = 16
        padding_v = 6
        
        text_w = bounds.width()
        text_h = bounds.height()
        
        # The block width and height including padding
        block_w = text_w + padding_h * 2
        block_h = text_h + padding_v * 2

        # Center horizontally, with horizontal offset
        h_offset = win.config.get('subtitle_h_offset', 0)
        h_offset_px = int(viewport_w * (h_offset / 100.0))
        block_x = (viewport_w - block_w) / 2.0 + h_offset_px
        
        # Vertical offset from bottom
        v_offset = win.config.get('subtitle_v_offset', 5)
        v_offset_px = int(viewport_h * (v_offset / 100.0))
        margin_bottom = v_offset_px
        
        # If fullscreen and controls card is visible
        if getattr(win, 'is_full_screen', False) and hasattr(win, 'controlsCard') and win.controlsCard.isVisible():
            margin_bottom += win.controlsCard.height()
            
        block_y = viewport_h - block_h - margin_bottom
        
        # Define the block rect
        block_rect = QRectF(block_x, block_y, block_w, block_h)
        
        # Define the text drawing rect (which is inside the block rect, offset by padding)
        text_rect = QRectF(block_x + padding_h, block_y + padding_v, text_w, text_h)

        # Draw background
        bg_color_val = win.config.get('subtitle_bg_color', '#000000')
        rgb = SubtitleRenderer._resolve_bg_rgb(bg_color_val)
        opacity = win.config.get('subtitle_bg_opacity', 60) # 0 to 100
        bg_color = QColor(rgb[0], rgb[1], rgb[2], int(255 * (opacity / 100.0)))
        
        painter.setBrush(bg_color)
        painter.setPen(Qt.PenStyle.NoPen)
        # Draw rounded rect with border-radius 6px
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.drawRoundedRect(block_rect, 6.0, 6.0)

        # Draw shadow
        shadow_enabled = win.config.get('subtitle_shadow_enabled', False)
        if shadow_enabled:
            shadow_dx = win.config.get('subtitle_shadow_dx', 2)
            shadow_dy = win.config.get('subtitle_shadow_dy', 2)
            shadow_color_val = win.config.get('subtitle_shadow_color', '#000000')
            shadow_color_hex = SubtitleRenderer._resolve(shadow_color_val, '#000000')
            shadow_color = QColor(shadow_color_hex)
            
            painter.setPen(shadow_color)
            painter.drawText(text_rect.translated(shadow_dx, shadow_dy), flags, active_text)

        # Draw outline
        outline_enabled = win.config.get('subtitle_outline_enabled', False)
        if outline_enabled:
            outline_width = win.config.get('subtitle_outline_width', 2)
            outline_color_val = win.config.get('subtitle_outline_color', '#000000')
            outline_color_hex = SubtitleRenderer._resolve(outline_color_val, '#000000')
            outline_color = QColor(outline_color_hex)
            
            painter.setPen(outline_color)
            w = int(outline_width)
            if w > 0:
                for dx in range(-w, w + 1):
                    for dy in range(-w, w + 1):
                        if dx == 0 and dy == 0:
                            continue
                        painter.drawText(text_rect.translated(dx, dy), flags, active_text)

        # Draw foreground text on top
        text_color_val = win.config.get('subtitle_text_color', '#ffffff')
        text_color_hex = SubtitleRenderer._resolve(text_color_val, '#ffffff')
        painter.setPen(QColor(text_color_hex))
        painter.drawText(text_rect, flags, active_text)

        painter.restore()
