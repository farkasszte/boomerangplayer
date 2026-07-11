import math
import os
from typing import TYPE_CHECKING, Optional, Any

from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QColor, QPainterPath, QPen, QPainterPathStroker, QFont, QPixmap
from PyQt6.QtWidgets import (QInputDialog, QGraphicsPathItem, QGraphicsTextItem, 
                             QFileDialog, QGraphicsPixmapItem, QGraphicsItemGroup, QDialog)

from translations import tr
from components.watermark_dialog import WatermarkPropertiesDialog

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QGraphicsScene
    from components.zoom_view import ZoomView
    ZoomViewDrawingMixinBase = ZoomView
else:
    ZoomViewDrawingMixinBase = object


class ZoomViewDrawingMixin(ZoomViewDrawingMixinBase):
    """Mixin class containing mouse event handling and helper methods for drawing tools."""
    
    if TYPE_CHECKING:
        drawing_mode: bool
        drawing_tool: str
        pen_color: QColor
        pen_width: int
        laser_mode: bool
        strokes: list
        undo_stack: list
        current_undo_transaction: list
        original_paths_in_drag: dict
        moving_watermark_item: Optional[QGraphicsPixmapItem]
        watermark_start_pos: Optional[QPointF]
        watermark_drag_offset: Optional[QPointF]
        last_eraser_pos: Optional[QPointF]
        start_scene_pos: Optional[QPointF]
        current_path: Optional[QPainterPath]
        current_path_item: Optional[QGraphicsPathItem]
        measure_group: Optional[QGraphicsItemGroup]
        measure_line: Optional[QGraphicsPathItem]
        measure_text: Optional[QGraphicsTextItem]
        cursor_item: QGraphicsItemGroup
        text_preview_item: QGraphicsTextItem
        
        def mapToScene(self, point) -> QPointF: ...
        def scene(self) -> 'QGraphicsScene': ...
        def strokesChanged(self) -> any: ...
        def doubleClicked(self) -> any: ...
        def undo_stroke(self) -> None: ...
        def perform_object_erase(self, scene_pos: QPointF) -> None: ...
        def perform_area_erase(self, scene_pos: Optional[QPointF], eraser_path: Optional[QPainterPath] = None) -> None: ...
        def _create_text_path_item(self, text: str, pos: QPointF, color: QColor, font_size: float, z_value: float) -> QGraphicsPathItem: ...

    def mousePressEvent(self, event) -> None:
        if self.drawing_mode and event.button() == Qt.MouseButton.LeftButton:
            self.current_undo_transaction = []
            self.original_paths_in_drag = {}
            scene_pos = self.mapToScene(event.pos())
            
            # 1. Check watermark drag/interaction
            if self._try_drag_watermark(scene_pos, event):
                return
            
            # 2. Check and handle click action based on drawing tool
            if self._handle_tool_press(scene_pos):
                return
                
            # 3. Standard drawing path initialization (pen, shapes)
            self._init_path_drawing(scene_pos)
        else:
            super().mousePressEvent(event)

    def _try_drag_watermark(self, scene_pos: QPointF, event) -> bool:
        clicked_items = self.scene().items(scene_pos)
        for item in clicked_items:
            if isinstance(item, QGraphicsPixmapItem) and item in self.strokes:
                self.moving_watermark_item = item
                self.watermark_start_pos = item.pos()
                self.watermark_drag_offset = scene_pos - item.pos()
                super().mousePressEvent(event)
                return True
        return False

    def _handle_tool_press(self, scene_pos: QPointF) -> bool:
        if self.drawing_tool in ['obj_eraser', 'stroke_eraser']:
            self.perform_object_erase(scene_pos)
            self.last_eraser_pos = scene_pos
            return True
        elif self.drawing_tool == 'area_eraser':
            self.last_eraser_pos = scene_pos
            self.perform_area_erase(scene_pos) # initial hit
            return True
        elif self.drawing_tool == 'text':
            self._add_text_item(scene_pos)
            return True
        elif self.drawing_tool == 'watermark':
            self._add_watermark_item(scene_pos)
            return True
        elif self.drawing_tool == 'measure':
            self._init_measure_item(scene_pos)
            return True
        return False

    def _add_text_item(self, scene_pos: QPointF) -> None:
        self.text_preview_item.hide()
        text, ok = QInputDialog.getText(self, tr('add_text_title'), tr('enter_text'))
        if ok and text:
            font_size = max(12, self.pen_width * 2)
            path_item = self._create_text_path_item(text, scene_pos, self.pen_color, font_size, 1000)
            self.scene().addItem(path_item)
            self.strokes.append(path_item)
            self.current_undo_transaction.append(('add', path_item))

    def _add_watermark_item(self, scene_pos: QPointF) -> None:
        self.text_preview_item.hide()
        fileName, _ = QFileDialog.getOpenFileName(
            self,
            tr('select_watermark_title'),
            "",
            f"{tr('image_files_filter')} (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.avif *.ico)"
        )
        if fileName and os.path.exists(fileName):
            opacity, ok = QInputDialog.getDouble(self, tr('watermark_opacity_title'), tr('enter_opacity'), 0.5, 0.0, 1.0, 2)
            if ok:
                pixmap = QPixmap(fileName)
                max_dim = max(100, self.pen_width * 50)
                if pixmap.width() > max_dim or pixmap.height() > max_dim:
                    pixmap = pixmap.scaled(max_dim, max_dim, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                
                path_item = QGraphicsPixmapItem(pixmap)
                path_item.setOpacity(opacity)
                path_item.setPos(scene_pos - QPointF(pixmap.width()/2.0, pixmap.height()/2.0))
                path_item.setZValue(1000)
                
                path_item.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsMovable, True)
                path_item.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsSelectable, True)
                
                self.scene().addItem(path_item)
                self.strokes.append(path_item)
                self.current_undo_transaction.append(('add', path_item))
                self.undo_stack.append(self.current_undo_transaction)
                self.current_undo_transaction = []
                self.strokesChanged.emit()

    def _init_measure_item(self, scene_pos: QPointF) -> None:
        self.current_undo_transaction = []
        self.start_scene_pos = scene_pos
        
        # Group for measure items
        self.measure_group = QGraphicsItemGroup()
        self.measure_line = QGraphicsPathItem(self.measure_group)
        self.measure_line.setPen(QPen(self.pen_color, 2))
        
        self.measure_text = QGraphicsTextItem(self.measure_group)
        self.measure_text.setDefaultTextColor(self.pen_color)
        self.measure_text.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        # Background for readability
        self.measure_text.setHtml(f'<div style="background-color: rgba(0,0,0,150); padding: 2px;">0 px / 0°</div>')
        
        self.measure_group.setZValue(1001)
        self.scene().addItem(self.measure_group)
        self.strokes.append(self.measure_group)
        self.current_undo_transaction.append(('add', self.measure_group))

    def _init_path_drawing(self, scene_pos: QPointF) -> None:
        self.start_scene_pos = scene_pos
        self.current_path = QPainterPath()
        self.current_path.moveTo(self.start_scene_pos)
        
        self.current_path_item = QGraphicsPathItem()
        
        if self.laser_mode:
            color = QColor(self.pen_color.red(), self.pen_color.green(), self.pen_color.blue(), 150)
            pen = QPen(color, self.pen_width * 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        else:
            pen = QPen(self.pen_color, self.pen_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        
        self.current_path_item.setPen(pen)
        self.current_path_item.setZValue(1000)
        
        self.scene().addItem(self.current_path_item)
        self.strokes.append(self.current_path_item)
        self.current_undo_transaction.append(('add', self.current_path_item))

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            clicked_items = self.scene().items(scene_pos)
            for item in clicked_items:
                if isinstance(item, QGraphicsPixmapItem) and item in self.strokes:
                    old_opacity = item.opacity()
                    old_pixmap = item.pixmap()
                    old_pos = item.pos()
                    
                    dialog = WatermarkPropertiesDialog(item, self)
                    res = dialog.exec()
                    if res == 2: # Delete
                        self.current_undo_transaction = [('delete', item, None, None, None, item.zValue())]
                        self.undo_stack.append(self.current_undo_transaction)
                        self.current_undo_transaction = []
                        self.scene().removeItem(item)
                        self.strokes.remove(item)
                        self.strokesChanged.emit()
                    elif res == QDialog.DialogCode.Accepted:
                        self.current_undo_transaction = [('modify_watermark', item, old_opacity, old_pixmap, old_pos)]
                        self.undo_stack.append(self.current_undo_transaction)
                        self.current_undo_transaction = []
                        self.strokesChanged.emit()
                    else:
                        item.setOpacity(old_opacity)
                        item.setPixmap(old_pixmap)
                        item.setPos(old_pos)
                    return
            self.doubleClicked.emit()
        else:
            super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self.moving_watermark_item is not None:
            curr_pos = self.mapToScene(event.pos())
            offset = self.watermark_drag_offset if self.watermark_drag_offset else QPointF(0,0)
            self.moving_watermark_item.setPos(curr_pos - offset)
            self.cursor_item.setPos(curr_pos)
            super().mouseMoveEvent(event)
            return

        if self.drawing_mode:
            curr_pos = self.mapToScene(event.pos())
            self.cursor_item.setPos(curr_pos)
            
            # Show/hide text preview
            if self.drawing_tool == 'text':
                self.text_preview_item.setPos(curr_pos)
                self.text_preview_item.setDefaultTextColor(self.pen_color)
                font_size = max(12, self.pen_width * 2)
                self.text_preview_item.setFont(QFont("Segoe UI", font_size))
                self.text_preview_item.setPlainText("Text") # Preview placeholder
                self.text_preview_item.show()
            else:
                self.text_preview_item.hide()
            
            # Continuous drawing/erasing while dragging left mouse button
            if event.buttons() & Qt.MouseButton.LeftButton:
                if self._handle_tool_drag(curr_pos):
                    return
                
                # Handle path or shape updates
                self._update_path_drawing(curr_pos)
            
            super().mouseMoveEvent(event)
        else:
            super().mouseMoveEvent(event)

    def _handle_tool_drag(self, curr_pos: QPointF) -> bool:
        if self.drawing_tool in ['obj_eraser', 'stroke_eraser']:
            self.perform_object_erase(curr_pos)
            return True
        elif self.drawing_tool == 'area_eraser':
            # Continuous erasure: create a path from last to current pos
            if self.last_eraser_pos:
                r = self.pen_width / 2.0
                eraser_line = QPainterPath()
                eraser_line.moveTo(self.last_eraser_pos)
                eraser_line.lineTo(curr_pos)
                
                stroker = QPainterPathStroker()
                stroker.setWidth(self.pen_width)
                stroker.setCapStyle(Qt.PenCapStyle.RoundCap)
                
                # The "capsule" path between last and current pos
                eraser_path = stroker.createStroke(eraser_line)
                eraser_path.addEllipse(curr_pos, r, r) # Ensure circle at end
                eraser_path.addEllipse(self.last_eraser_pos, r, r) # Ensure circle at start
                
                self.perform_area_erase(None, eraser_path)
            else:
                self.perform_area_erase(curr_pos)
            
            self.last_eraser_pos = curr_pos
            return True
        return False

    def _update_path_drawing(self, curr_pos: QPointF) -> None:
        if self.current_path_item:
            if self.drawing_tool == 'pen':
                self.current_path.lineTo(curr_pos)
            else:
                if self.start_scene_pos is not None:
                    self.current_path = self._create_shape_path(self.drawing_tool, self.start_scene_pos, curr_pos)
            
            if self.current_path and not self.current_path.isEmpty():
                try:
                    self.current_path_item.setPath(self.current_path)
                except RuntimeError:
                    self.current_path_item = None
                    
        elif self.drawing_tool == 'measure' and self.measure_group and self.start_scene_pos is not None:
            new_path = QPainterPath()
            new_path.moveTo(self.start_scene_pos)
            new_path.lineTo(curr_pos)
            self.measure_line.setPath(new_path)
            
            # Update text
            dx = curr_pos.x() - self.start_scene_pos.x()
            dy = curr_pos.y() - self.start_scene_pos.y()
            dist = math.sqrt(dx*dx + dy*dy)
            angle = -math.degrees(math.atan2(dy, dx))
            if angle < 0: 
                angle += 360
            
            self.measure_text.setHtml(f'<div style="background-color: rgba(0,0,0,150); color: {self.pen_color.name()}; font-family: Segoe UI; font-weight: bold;"> {int(dist)} px / {int(angle)}° </div>')
            self.measure_text.setPos(curr_pos + QPointF(10, 10))

    def _create_shape_path(self, tool: str, start_pos: QPointF, end_pos: QPointF) -> QPainterPath:
        new_path = QPainterPath()
        rect = QRectF(start_pos, end_pos).normalized()
        
        if tool == 'rect':
            new_path.addRect(rect)
        elif tool == 'ellipse':
            new_path.addEllipse(rect)
        elif tool == 'triangle':
            new_path.moveTo(rect.left() + rect.width()/2, rect.top())
            new_path.lineTo(rect.bottomLeft())
            new_path.lineTo(rect.bottomRight())
            new_path.closeSubpath()
        elif tool == 'line':
            new_path.moveTo(start_pos)
            new_path.lineTo(end_pos)
        elif tool == 'arrow':
            new_path.moveTo(start_pos)
            new_path.lineTo(end_pos)
            angle = math.atan2(end_pos.y() - start_pos.y(), end_pos.x() - start_pos.x())
            headSize = max(15, self.pen_width * 3)
            p1 = end_pos - QPointF(headSize * math.cos(angle - math.pi / 6),
                                 headSize * math.sin(angle - math.pi / 6))
            p2 = end_pos - QPointF(headSize * math.cos(angle + math.pi / 6),
                                 headSize * math.sin(angle + math.pi / 6))
            new_path.moveTo(end_pos)
            new_path.lineTo(p1)
            new_path.moveTo(end_pos)
            new_path.lineTo(p2)
            
        return new_path

    def mouseReleaseEvent(self, event) -> None:
        if self.moving_watermark_item is not None:
            if self.moving_watermark_item.pos() != self.watermark_start_pos:
                move_transaction = [('modify_watermark', self.moving_watermark_item, self.moving_watermark_item.opacity(), self.moving_watermark_item.pixmap(), self.watermark_start_pos)]
                self.undo_stack.append(move_transaction)
                self.strokesChanged.emit()
            self.moving_watermark_item = None

        if self.drawing_mode and event.button() == Qt.MouseButton.LeftButton:
            was_eraser = self.drawing_tool in ['obj_eraser', 'area_eraser', 'stroke_eraser']
            
            if self.current_undo_transaction:
                self.undo_stack.append(self.current_undo_transaction)
                self.current_undo_transaction = []
                
                # In laser mode, erasers are temporary - restore everything immediately
                if self.laser_mode and was_eraser:
                    self.undo_stroke()
            
            if self.laser_mode and self.current_path_item:
                try:
                    scene = self.scene()
                    if scene and self.current_path_item.scene() == scene:
                        scene.removeItem(self.current_path_item)
                    
                    if self.current_path_item in self.strokes:
                        self.strokes.remove(self.current_path_item)
                except Exception:
                    pass

            if self.laser_mode and self.measure_group:
                try:
                    scene = self.scene()
                    if scene and self.measure_group.scene() == scene:
                        scene.removeItem(self.measure_group)
                    
                    if self.measure_group in self.strokes:
                        self.strokes.remove(self.measure_group)
                except Exception:
                    pass
                    
            self.current_path_item = None
            self.current_path = None
            self.measure_group = None
            
            if not self.laser_mode:
                self.strokesChanged.emit()
        
        # Always call super to ensure QGraphicsView internal state is updated
        super().mouseReleaseEvent(event)
