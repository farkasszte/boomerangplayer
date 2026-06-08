"""
DrawingMixin — drawing sidebar logic, tool management, pen, screenshot, chronometer.
"""

from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QColor, QPixmap, QPainter, QPen, QPainterPath, QIcon
from PyQt6.QtWidgets import QFileDialog, QColorDialog
from translations import tr
from utils import format_chrono_time


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QMainWindow, QLabel, QFrame, QSplitter, QButtonGroup
    from components import ZoomView, GPUPixmapItem
    from config import Configuration
    DrawingMixinBase = QMainWindow
else:
    DrawingMixinBase = object


class DrawingMixin(DrawingMixinBase):
    if TYPE_CHECKING:
        view: ZoomView
        chronometerOverlay: QFrame
        chronoTimeLabel: QLabel
        chronoSectionLabel: QLabel
        chronoPositionLabel: QLabel
        currentFilePath: str | None
        fps: float
        markers: list
        drawingContainer: QFrame
        playlistContainer: QFrame
        mainSplitter: QSplitter
        toolGroup: QButtonGroup
        config: Configuration
        paletteButtons: list
        penSizeLabel: QLabel
        penPreview: QLabel
        pixmapItem: GPUPixmapItem | None
    # ------------------------------------------------------------------ #
    # Drawing mode toggles                                                 #
    # ------------------------------------------------------------------ #

    def toggle_drawing_mode(self, checked):
        self.view.set_drawing_mode(checked)
        # When drawing mode is on, make the chronometer overlay transparent to mouse
        # so it doesn't intercept drawing events
        if hasattr(self, 'chronometerOverlay'):
            if checked:
                self.chronometerOverlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            else:
                self.chronometerOverlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

    def toggle_laser_mode(self, checked):
        self.view.laser_mode = checked

    def toggle_chronometer(self, checked):
        if checked:
            self.chronometerOverlay.show()
        else:
            self.chronometerOverlay.hide()

    # ------------------------------------------------------------------ #
    # Chronometer update (time since last section boundary)                 #
    # ------------------------------------------------------------------ #

    def update_chronometer(self):
        """Update the chronometer display with time since the last section boundary."""
        if not hasattr(self, 'chronometerOverlay') or not self.chronometerOverlay.isVisible():
            return
        if not self.currentFilePath or self.fps <= 0:
            self.chronoTimeLabel.setText("00:00.000")
            self.chronoSectionLabel.setText("")
            self.chronoPositionLabel.setText("")
            return

        
        current_frame = self.current_cache_index

        # Get the most recent marker/section boundary before or at the current frame
        last_section_start = 0
        if self.markers:
            for m in sorted(self.markers):
                if m <= current_frame:
                    last_section_start = m
                else:
                    break

        # Calculate elapsed time from the last section boundary
        elapsed_frames = current_frame - last_section_start
        elapsed_ms = int((elapsed_frames * 1000.0) / self.fps)

        # Also compute total time from the very beginning to current position
        total_ms = int((current_frame * 1000.0) / self.fps)

        self.chronoTimeLabel.setText(format_chrono_time(elapsed_ms))

        # Section start boundary line (accent colored)
        boundary_sec = int((last_section_start * 1000.0) / self.fps)
        self.chronoSectionLabel.setText(f"{tr('chrono_section')}: F {last_section_start} ({format_chrono_time(boundary_sec)})")

        # Position line (grey)
        self.chronoPositionLabel.setText(f"{tr('chrono_position')}: F {current_frame} ({format_chrono_time(total_ms)})")

        # Auto-resize after text is set
        self.chronometerOverlay.adjustSize()

    def toggle_drawing_panel(self):
        is_visible = self.drawingContainer.isVisible()
        if not is_visible:
            self.playlistContainer.hide()
        self.drawingContainer.setVisible(not is_visible)
        if hasattr(self, 'update_sidebar_fullscreen_state'):
            self.update_sidebar_fullscreen_state()

        if not is_visible and not getattr(self, 'is_full_screen', False):
            sizes = self.mainSplitter.sizes()
            if len(sizes) > 4 and sizes[4] < 250:
                sizes[4] = 250
                self.mainSplitter.setSizes(sizes)

    # ------------------------------------------------------------------ #
    # Active tool                                                          #
    # ------------------------------------------------------------------ #

    def set_active_tool(self, tool_id):
        self.view.drawing_tool = tool_id
        for btn in self.toolGroup.buttons():
            btn.setProperty('checked', btn.isChecked())
            
            btn.style().unpolish(btn)
            
            btn.style().polish(btn)

        if tool_id in ['obj_eraser', 'area_eraser']:
            self.view.cursor_circle.setBrush(QColor(255, 255, 255, 30))
        else:
            c = self.view.pen_color
            self.view.cursor_circle.setBrush(QColor(c.red(), c.green(), c.blue(), 50))

    # ------------------------------------------------------------------ #
    # Pen color & width                                                    #
    # ------------------------------------------------------------------ #

    def choose_pen_color(self):
        color = QColorDialog.getColor(self.view.pen_color, self, tr('select_color'))
        if color.isValid():
            self.view.pen_color = color
            
            # Update the active palette square
            active_idx = self.config.get('active_color_index', 2)
            palette = self.config.get('palette', [])
            if 0 <= active_idx < len(palette):
                palette[active_idx] = color.name().upper()
                self.config['palette'] = palette
            
            self.update_palette_ui()
            self.update_pen_preview()
            self.set_active_tool(self.view.drawing_tool)

    def select_palette_color(self):
        btn = self.sender()
        
        idx = btn.property('color_idx')
        palette = self.config.get('palette', [])
        if 0 <= idx < len(palette):
            self.config['active_color_index'] = idx
            self.view.pen_color = QColor(palette[idx])
            self.update_palette_ui()
            self.update_pen_preview()
            self.set_active_tool(self.view.drawing_tool)

    def update_palette_ui(self):
        palette = self.config.get('palette', [])
        active_idx = self.config.get('active_color_index', 2)
        accent = "#0099FF" # Accent color for border
        
        for i, btn in enumerate(self.paletteButtons):
            color = palette[i]
            border = f"2px solid {accent}" if i == active_idx else "1px solid rgba(255,255,255,40)"
            btn.setStyleSheet(f"background-color: {color}; border: {border}; border-radius: 4px;")

    def update_pen_width(self, val):
        self.view.pen_width = val
        if hasattr(self, 'penSizeLabel') and self.penSizeLabel:
            from PyQt6.QtWidgets import QLabel
            if isinstance(self.penSizeLabel, QLabel):
                self.penSizeLabel.setText(f"{val} px")
            else:
                self.penSizeLabel.blockSignals(True)
                self.penSizeLabel.setValue(val)
                self.penSizeLabel.blockSignals(False)
        self.view.update_cursor_size()
        self.update_pen_preview()

    def update_pen_preview(self):
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        color = self.view.pen_color
        r = min(14, self.view.pen_width / 2.0)

        painter.setPen(QPen(QColor(255, 255, 255, 20), 1))
        painter.setBrush(QColor(255, 255, 255, 5))
        painter.drawEllipse(QPointF(16, 16), 15, 15)

        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(16, 16), r, r)
        painter.end()

        self.penPreview.setPixmap(pixmap)

    # ------------------------------------------------------------------ #
    # Shape icon helper                                                    #
    # ------------------------------------------------------------------ #

    def create_shape_icon(self, shape_type):
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(Qt.GlobalColor.white, 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if shape_type == 'rect':
            painter.drawRect(5, 5, 22, 22)
        elif shape_type == 'ellipse':
            painter.drawEllipse(5, 5, 22, 22)
        elif shape_type == 'triangle':
            path = QPainterPath()
            path.moveTo(16, 5)
            path.lineTo(27, 27)
            path.lineTo(5, 27)
            path.closeSubpath()
            painter.drawPath(path)
        elif shape_type == 'arrow':
            painter.drawLine(6, 26, 26, 6)
            painter.drawLine(26, 6, 15, 6)
            painter.drawLine(26, 6, 26, 17)

        painter.end()
        return QIcon(pixmap)

    # ------------------------------------------------------------------ #
    # Stroke operations                                                    #
    # ------------------------------------------------------------------ #

    def undo_last_stroke(self):
        self.view.undo_stroke()

    def clear_all_strokes(self):
        for item in self.view.strokes:
            if item.scene():
                self.view.scene().removeItem(item)
        self.view.strokes.clear()

    # ------------------------------------------------------------------ #
    # Screenshot                                                           #
    # ------------------------------------------------------------------ #

    def save_drawing_screenshot(self):
        if self.pixmapItem is None or not self.pixmapItem.pixmap():
            return

        rect = self.pixmapItem.pixmap().rect()
        out_pixmap = QPixmap(rect.size())
        out_pixmap.fill(Qt.GlobalColor.black)

        painter = QPainter(out_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.view.scene().render(painter, QRectF(rect), QRectF(rect))
        painter.end()

        filePath, _ = QFileDialog.getSaveFileName(
            self, tr('save_screenshot'), "boomerang_analysis.png",
            tr('image_files') + " (*.png *.jpg)"
        )
        if filePath:
            out_pixmap.save(filePath)
