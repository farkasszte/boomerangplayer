import math
from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QRectF, QSize
from PyQt6.QtGui import QPainter, QPen, QColor, QPainterPath, QPainterPathStroker, QTransform, QFont
from PyQt6.QtWidgets import (QGraphicsView, QSlider, QInputDialog, QGraphicsPathItem, 
                             QGraphicsTextItem, QGraphicsEllipseItem, QGraphicsScene)
from qfluentwidgets import ListWidget

class DropListWidget(ListWidget):
    filesDropped = pyqtSignal(list)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        self.filesDropped.emit(files)

class MarkerSlider(QSlider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.loopStartFrame = 0
        self.loopEndFrame = 0
        
    def update_markers(self, start_frame, end_frame):
        self.loopStartFrame = start_frame
        self.loopEndFrame = end_frame
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            val = self.minimum() + ((self.maximum() - self.minimum()) * event.position().x()) / self.width()
            self.setValue(int(val))
            self.sliderMoved.emit(int(val))
        super().mousePressEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.maximum() <= 0:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w = self.width()
        start_x = int((self.loopStartFrame / self.maximum()) * w)
        end_x = int((self.loopEndFrame / self.maximum()) * w)
        
        pen = QPen(QColor(0, 153, 255))
        pen.setWidth(2)
        painter.setPen(pen)
        
        if self.loopStartFrame > 0:
            painter.drawLine(start_x, 0, start_x, self.height())
        if self.loopEndFrame > 0 and self.loopEndFrame < self.maximum():
            painter.drawLine(end_x, 0, end_x, self.height())

class ZoomView(QGraphicsView):
    zoomChanged = pyqtSignal(float)
    filesDropped = pyqtSignal(list)

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
        
        # Cursor preview
        self.cursor_item = QGraphicsEllipseItem()
        self.cursor_item.setPen(QPen(Qt.PenStyle.NoPen))
        self.cursor_item.setBrush(QColor(255, 255, 255, 50))
        self.cursor_item.setZValue(10001)
        self.cursor_item.hide()
        self.scene().addItem(self.cursor_item)

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
        self.cursor_item.setRect(-r, -r, self.pen_width, self.pen_width)

    def mousePressEvent(self, event):
        if self.drawing_mode and event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            
            if self.drawing_tool == 'obj_eraser':
                self.perform_object_erase(scene_pos)
                return
            elif self.drawing_tool == 'area_eraser':
                self.perform_area_erase(scene_pos)
                return
            elif self.drawing_tool == 'text':
                text, ok = QInputDialog.getText(self, "Add Text", "Enter text:")
                if ok and text:
                    item = QGraphicsTextItem(text)
                    item.setDefaultTextColor(self.pen_color)
                    font_size = max(12, self.pen_width * 2)
                    item.setFont(QFont("Segoe UI", font_size))
                    item.setPos(scene_pos)
                    item.setZValue(1000)
                    self.scene().addItem(item)
                    self.strokes.append(item)
                return
                
            self.start_scene_pos = scene_pos
            self.current_path = QPainterPath()
            self.current_path.moveTo(self.start_scene_pos)
            
            self.current_path_item = QGraphicsPathItem()
            
            if self.drawing_tool == 'laser':
                color = QColor(self.pen_color.red(), self.pen_color.green(), self.pen_color.blue(), 150)
                pen = QPen(color, self.pen_width * 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            else:
                pen = QPen(self.pen_color, self.pen_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            
            self.current_path_item.setPen(pen)
            self.current_path_item.setZValue(1000)
            
            self.scene().addItem(self.current_path_item)
            self.strokes.append(self.current_path_item)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drawing_mode:
            curr_pos = self.mapToScene(event.pos())
            self.cursor_item.setPos(curr_pos)
            
            if event.buttons() & Qt.MouseButton.LeftButton:
                if self.drawing_tool in ['obj_eraser', 'stroke_eraser']:
                    self.perform_object_erase(curr_pos)
                    return
                elif self.drawing_tool == 'area_eraser':
                    self.perform_area_erase(curr_pos)
                    return
                    
                if self.current_path_item:
                    if self.drawing_tool in ['pen', 'laser']:
                        self.current_path.lineTo(curr_pos)
                    else:
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
                    self.current_path_item.setPath(self.current_path)
        else:
            super().mouseMoveEvent(event)

    def perform_object_erase(self, scene_pos):
        hit_rect = QRectF(scene_pos.x()-2, scene_pos.y()-2, 4, 4)
        items = self.scene().items(hit_rect)
        for item in items:
            if (isinstance(item, (QGraphicsPathItem, QGraphicsTextItem))) and item in self.strokes:
                self.scene().removeItem(item)
                self.strokes.remove(item)

    def perform_area_erase(self, scene_pos):
        r = self.pen_width / 2.0
        eraser_path = QPainterPath()
        eraser_path.addEllipse(scene_pos, r, r)
        
        items = self.scene().items(eraser_path.boundingRect())
        for item in items:
            if isinstance(item, QGraphicsPathItem) and item in self.strokes:
                path = item.path()
                if item.brush().style() == Qt.BrushStyle.NoBrush:
                    stroker = QPainterPathStroker()
                    stroker.setWidth(item.pen().widthF())
                    stroker.setCapStyle(item.pen().capStyle())
                    stroker.setJoinStyle(item.pen().joinStyle())
                    path = stroker.createStroke(path)
                    item.setBrush(item.pen().color())
                    item.setPen(QPen(Qt.PenStyle.NoPen))
                
                new_path = path.subtracted(eraser_path)
                if new_path.isEmpty():
                    if item.scene():
                        self.scene().removeItem(item)
                    if item in self.strokes:
                        self.strokes.remove(item)
                else:
                    item.setPath(new_path)

    def mouseReleaseEvent(self, event):
        if self.drawing_mode and event.button() == Qt.MouseButton.LeftButton:
            if self.drawing_tool == 'laser' and self.current_path_item:
                if self.current_path_item.scene():
                    self.scene().removeItem(self.current_path_item)
                if self.current_path_item in self.strokes:
                    self.strokes.remove(self.current_path_item)
            self.current_path_item = None
            self.current_path = None
        else:
            super().mouseReleaseEvent(event)

    def undo_stroke(self):
        if self.strokes:
            last_stroke = self.strokes.pop()
            self.scene().removeItem(last_stroke)

    def clear_strokes(self):
        for stroke in self.strokes:
            self.scene().removeItem(stroke)
        self.strokes = []

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
        factor = 1.1 if event.angleDelta().y() > 0 else 1/1.1
        new_zoom = self.zoomLevel * factor
        if 1.0 <= new_zoom <= 10.0:
            self.zoomLevel = new_zoom
            self.scale(factor, factor)
            self.zoomChanged.emit(self.zoomLevel)
        elif new_zoom < 1.0:
            factor = 1.0 / self.zoomLevel
            self.zoomLevel = 1.0
            self.scale(factor, factor)
            self.zoomChanged.emit(self.zoomLevel)
