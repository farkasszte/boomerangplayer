"""
DrawingMixin — drawing sidebar logic, tool management, pen, screenshot.
"""

from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QColor, QPixmap, QPainter, QPen, QPainterPath, QIcon
from PyQt6.QtWidgets import QFileDialog, QColorDialog
from translations import tr


class DrawingMixin:
    # ------------------------------------------------------------------ #
    # Drawing mode toggles                                                 #
    # ------------------------------------------------------------------ #

    def toggle_drawing_mode(self, checked):
        self.view.set_drawing_mode(checked)

    def toggle_laser_mode(self, checked):
        self.view.laser_mode = checked

    def toggle_drawing_panel(self):
        is_visible = self.drawingContainer.isVisible()
        if not is_visible:
            self.playlistContainer.hide()
        self.drawingContainer.setVisible(not is_visible)

        if not is_visible:
            sizes = self.mainSplitter.sizes()
            if sizes[4] < 250:
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
        self.penSizeLabel.setText(f"{val} px")
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
        if not self.pixmapItem.pixmap():
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
