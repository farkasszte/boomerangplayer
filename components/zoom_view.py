import math
from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QRectF, QPoint
from PyQt6.QtGui import QPainter, QPen, QColor, QPainterPath, QPainterPathStroker, QFont, QPixmap, QImage
from PyQt6.QtWidgets import (QGraphicsView, QInputDialog, QGraphicsPathItem, 
                             QGraphicsTextItem, QGraphicsEllipseItem, QGraphicsItemGroup,
                             QGraphicsScene, QFileDialog, QGraphicsPixmapItem)
from translations import tr
from components.watermark_dialog import WatermarkPropertiesDialog
from components.drawing_serializer import serialize_item, deserialize_item
from components.drawing_eraser import DrawingEraserMixin


class ZoomView(QGraphicsView, DrawingEraserMixin):
    zoomChanged = pyqtSignal(float)
    filesDropped = pyqtSignal(list)
    doubleClicked = pyqtSignal()
    strokesChanged = pyqtSignal()

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setAcceptDrops(True)
        self.zoomLevel = 1.0
        
        # Drawing state
        self.drawing_mode = False
        self.drawing_tool = 'pen'
        self.pen_color = QColor(255, 0, 0)
        self.pen_width = 3
        self.start_scene_pos = None
        self.current_path = None
        self.current_path_item = None
        self.strokes = [] # List of items in the scene for undo/clear
        self.laser_mode = False
        
        # Cursor preview group
        self.cursor_item = QGraphicsItemGroup()
        
        # 1. Circle representing pen width
        self.cursor_circle = QGraphicsEllipseItem(self.cursor_item)
        self.cursor_circle.setPen(QPen(QColor(255, 255, 255, 180), 1))
        self.cursor_circle.setBrush(QColor(255, 255, 255, 40))
        
        # 2. Crosshair for precision (High contrast: Black outline + White inner)
        cross_path = QPainterPath()
        cross_path.moveTo(-15, 0)
        cross_path.lineTo(15, 0)
        cross_path.moveTo(0, -15)
        cross_path.lineTo(0, 15)
        cross_path.addRect(-0.5, -0.5, 1, 1) # Center point
        
        self.cursor_cross_bg = QGraphicsPathItem(self.cursor_item)
        bg_pen = QPen(Qt.GlobalColor.black, 3)
        bg_pen.setCosmetic(True)
        self.cursor_cross_bg.setPen(bg_pen)
        self.cursor_cross_bg.setPath(cross_path)
        
        self.cursor_cross_fg = QGraphicsPathItem(self.cursor_item)
        fg_pen = QPen(Qt.GlobalColor.white, 1)
        fg_pen.setCosmetic(True)
        self.cursor_cross_fg.setPen(fg_pen)
        self.cursor_cross_fg.setPath(cross_path)
        
        self.cursor_item.setZValue(20000)
        self.cursor_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.cursor_item.setEnabled(False)
        self.cursor_item.hide()
        self.scene().addItem(self.cursor_item)

        # Text preview ghost
        self.text_preview_item = QGraphicsTextItem()
        self.text_preview_item.setOpacity(0.5)
        self.text_preview_item.setZValue(19999)
        self.text_preview_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.scene().addItem(self.text_preview_item)
        self.text_preview_item.hide()
        self.text_preview_item.setDefaultTextColor(Qt.GlobalColor.white)

        # Undo system
        self.undo_stack = []
        self.current_undo_transaction = []
        self.original_paths_in_drag = {} # item -> path before this drag
        self.measure_group = None

    def scene(self) -> QGraphicsScene:
        s = super().scene()
        if s is None:
            raise RuntimeError("Scene is not set")
        return s

    def set_drawing_mode(self, enabled):
        self.drawing_mode = enabled
        self.cursor_item.setVisible(enabled)
        if enabled:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setCursor(Qt.CursorShape.BlankCursor)
            self.update_cursor_size()
        else:
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def update_cursor_size(self):
        r = self.pen_width / 2.0
        self.cursor_circle.setRect(-r, -r, self.pen_width, self.pen_width)

    def mousePressEvent(self, event):
        if self.drawing_mode and event.button() == Qt.MouseButton.LeftButton:
            self.current_undo_transaction = []
            self.original_paths_in_drag = {}
            scene_pos = self.mapToScene(event.pos())
            
            # If clicked on a watermark, allow dragging it directly even in drawing mode
            clicked_items = self.scene().items(scene_pos)
            for item in clicked_items:
                if isinstance(item, QGraphicsPixmapItem) and item in self.strokes:
                    self.moving_watermark_item = item
                    self.watermark_start_pos = item.pos()
                    self.watermark_drag_offset = scene_pos - item.pos()
                    super().mousePressEvent(event)
                    return
            
            if self.drawing_tool in ['obj_eraser', 'stroke_eraser']:
                self.perform_object_erase(scene_pos)
                self.last_eraser_pos = scene_pos
                return
            elif self.drawing_tool == 'area_eraser':
                self.last_eraser_pos = scene_pos
                self.perform_area_erase(scene_pos) # initial hit
                return
            elif self.drawing_tool == 'text':
                self.text_preview_item.hide()
                text, ok = QInputDialog.getText(self, tr('add_text_title'), tr('enter_text'))
                if ok and text:
                    font_size = max(12, self.pen_width * 2)
                    path_item = self._create_text_path_item(text, scene_pos, self.pen_color, font_size, 1000)
                    self.scene().addItem(path_item)
                    self.strokes.append(path_item)
                    self.current_undo_transaction.append(('add', path_item))
                return
            elif self.drawing_tool == 'watermark':
                self.text_preview_item.hide()
                import os
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
                return
            elif self.drawing_tool == 'measure':
                self.current_undo_transaction = []
                scene_pos = self.mapToScene(event.pos())
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
                return
                
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
        else:
            super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
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

    def mouseMoveEvent(self, event):
        if getattr(self, 'moving_watermark_item', None) is not None:
            curr_pos = self.mapToScene(event.pos())
            offset = getattr(self, 'watermark_drag_offset', QPointF(0,0))
            self.moving_watermark_item.setPos(curr_pos - offset)
            self.cursor_item.setPos(curr_pos)
            super().mouseMoveEvent(event)
            return

        if self.drawing_mode:
            curr_pos = self.mapToScene(event.pos())
            self.cursor_item.setPos(curr_pos)
            
            if self.drawing_tool == 'text':
                self.text_preview_item.setPos(curr_pos)
                self.text_preview_item.setDefaultTextColor(self.pen_color)
                font_size = max(12, self.pen_width * 2)
                self.text_preview_item.setFont(QFont("Segoe UI", font_size))
                self.text_preview_item.setPlainText("Text") # Preview placeholder
                self.text_preview_item.show()
            else:
                self.text_preview_item.hide()
            
            if event.buttons() & Qt.MouseButton.LeftButton:
                if self.drawing_tool in ['obj_eraser', 'stroke_eraser']:
                    self.perform_object_erase(curr_pos)
                    return
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
                    return
                    
                if self.current_path_item:
                    if self.drawing_tool == 'pen':
                        
                        self.current_path.lineTo(curr_pos)
                    else:
                        if self.start_scene_pos is not None:
                            new_path = QPainterPath()
                            rect = QRectF(self.start_scene_pos, curr_pos).normalized()
                            
                            if self.drawing_tool == 'rect':
                                new_path.addRect(rect)
                            elif self.drawing_tool == 'ellipse':
                                new_path.addEllipse(rect)
                            elif self.drawing_tool == 'triangle':
                                new_path.moveTo(rect.left() + rect.width()/2, rect.top())
                                new_path.lineTo(rect.bottomLeft())
                                new_path.lineTo(rect.bottomRight())
                                new_path.closeSubpath()
                            elif self.drawing_tool == 'line':
                                new_path.moveTo(self.start_scene_pos)
                                new_path.lineTo(curr_pos)
                            elif self.drawing_tool == 'arrow':
                                new_path.moveTo(self.start_scene_pos)
                                new_path.lineTo(curr_pos)
                                angle = math.atan2(curr_pos.y() - self.start_scene_pos.y(), curr_pos.x() - self.start_scene_pos.x())
                                headSize = max(15, self.pen_width * 3)
                                p1 = curr_pos - QPointF(headSize * math.cos(angle - math.pi / 6),
                                                     headSize * math.sin(angle - math.pi / 6))
                                p2 = curr_pos - QPointF(headSize * math.cos(angle + math.pi / 6),
                                                     headSize * math.sin(angle + math.pi / 6))
                                new_path.moveTo(curr_pos)
                                new_path.lineTo(p1)
                                new_path.moveTo(curr_pos)
                                new_path.lineTo(p2)
                            
                            self.current_path = new_path
                    
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
                    if angle < 0: angle += 360
                    
                    self.measure_text.setHtml(f'<div style="background-color: rgba(0,0,0,150); color: {self.pen_color.name()}; font-family: Segoe UI; font-weight: bold;"> {int(dist)} px / {int(angle)}° </div>')
                    self.measure_text.setPos(curr_pos + QPointF(10, 10))
            
            super().mouseMoveEvent(event)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if getattr(self, 'moving_watermark_item', None) is not None:
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
                    
            self.current_path_item = None
            self.current_path = None
            self.measure_group = None
            
            if not self.laser_mode:
                self.strokesChanged.emit()
        
        # Always call super to ensure QGraphicsView internal state is updated
        super().mouseReleaseEvent(event)

    def undo_stroke(self):
        if self.undo_stack:
            transaction = self.undo_stack.pop()
            # Process in reverse to maintain order
            for action in reversed(transaction):
                type = action[0]
                if type == 'add':
                    item = action[1]
                    if item in self.strokes:
                        self.strokes.remove(item)
                    if item.scene():
                        self.scene().removeItem(item)
                elif type == 'delete':
                    item, path, pen, brush, z = action[1], action[2], action[3], action[4], action[5]
                    if path is not None: # PathItem
                        item.setPath(path)
                        item.setPen(pen)
                        item.setBrush(brush)
                    # TextItem or PathItem
                    item.setZValue(z)
                    self.scene().addItem(item)
                    self.strokes.append(item)
                elif type == 'modify':
                    item, old_path, old_pen, old_brush = action[1], action[2], action[3], action[4]
                    item.setPath(old_path)
                    item.setPen(old_pen)
                    item.setBrush(old_brush)
                elif type == 'modify_watermark':
                    item, old_opacity, old_pixmap, old_pos = action[1], action[2], action[3], action[4]
                    item.setOpacity(old_opacity)
                    item.setPixmap(old_pixmap)
                    item.setPos(old_pos)
            self.strokesChanged.emit()

    def clear_strokes(self):
        for stroke in self.strokes:
            self.scene().removeItem(stroke)
        self.strokes = []
        self.strokesChanged.emit()

    def serialize_strokes(self):
        serialized = []
        for item in self.strokes:
            try:
                data = serialize_item(item)
                if data:
                    serialized.append(data)
            except Exception as e:
                print(f"Error serializing item {item}: {e}")
        return serialized

    def deserialize_strokes(self, data_list):
        # Temporarily block signals to avoid recursion or multiple saves
        self.blockSignals(True)
        try:
            self.clear_strokes()
            if data_list:
                for data in data_list:
                    try:
                        item = deserialize_item(data)
                        if item:
                            self.scene().addItem(item)
                            self.strokes.append(item)
                    except Exception as e:
                         print(f"Error deserializing stroke data {data}: {e}")
        finally:
            self.blockSignals(False)
        self.strokesChanged.emit()

    def get_scroll_state(self):
        
        return (self.horizontalScrollBar().value(), self.verticalScrollBar().value())
    
    def set_scroll_state(self, x, y):
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(50, lambda: self._apply_scroll(x, y))

    def _apply_scroll(self, x, y):
        
        self.horizontalScrollBar().setValue(x)
        
        self.verticalScrollBar().setValue(y)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            files = [u.toLocalFile() for u in event.mimeData().urls()]
            self.filesDropped.emit(files)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def wheelEvent(self, event):
        viewport_pos = event.position()
        old_scene_pos = self.mapToScene(viewport_pos.toPoint())
        
        # 2. Calculate zoom factor
        factor = 1.1 if event.angleDelta().y() > 0 else 1/1.1
        new_zoom = self.zoomLevel * factor
        
        # 3. Clamp zoom level
        if new_zoom > 10.0:
            if self.zoomLevel == 10.0: return
            actual_factor = 10.0 / self.zoomLevel
            self.zoomLevel = 10.0
        elif new_zoom < 1.0:
            if self.zoomLevel == 1.0: return
            actual_factor = 1.0 / self.zoomLevel
            self.zoomLevel = 1.0
        else:
            self.zoomLevel = new_zoom
            actual_factor = factor
            
        # 4. Apply scale with NoAnchor to handle it manually
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.scale(actual_factor, actual_factor)
        
        # 5. Get new scene position of the same viewport point
        new_scene_pos = self.mapToScene(viewport_pos.toPoint())
        
        # 6. Calculate the shift needed in scene coordinates
        delta = new_scene_pos - old_scene_pos
        
        # 7. Translate the view (scroll) to keep the point fixed
        self.translate(delta.x(), delta.y())
        
        # 8. Re-enable anchor for other interactions
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        
        self.zoomChanged.emit(self.zoomLevel)
        
        # Update cursor preview position immediately
        if self.drawing_mode:
            self.cursor_item.setPos(self.mapToScene(viewport_pos.toPoint()))
