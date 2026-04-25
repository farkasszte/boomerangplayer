import math
from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QRectF, QPoint
from PyQt6.QtGui import QPainter, QPen, QColor, QPainterPath, QPainterPathStroker, QFont
from PyQt6.QtWidgets import (QGraphicsView, QSlider, QInputDialog, QGraphicsPathItem, 
                             QGraphicsTextItem, QGraphicsEllipseItem, QGraphicsItemGroup)
from qfluentwidgets import ListWidget, PushButton
from translations import tr

class DropListWidget(ListWidget):
    filesDropped = pyqtSignal(list)
    itemRightClicked = pyqtSignal(object, QPoint)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def contextMenuEvent(self, event):
        item = self.itemAt(event.pos())
        if item:
            self.itemRightClicked.emit(item, event.globalPos())

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
        self.markers = []
        
    def update_markers(self, markers):
        self.markers = sorted(list(set(markers)))
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
        pen = QPen(QColor(0, 153, 255))
        pen.setWidth(2)
        painter.setPen(pen)
        
        for m in self.markers:
            if 0 < m < self.maximum():
                mx = int((m / self.maximum()) * w)
                painter.drawLine(mx, 0, mx, self.height())

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
            
            if self.drawing_tool == 'obj_eraser':
                self.perform_object_erase(scene_pos)
                return
            elif self.drawing_tool == 'area_eraser':
                self.perform_area_erase(scene_pos)
                return
            elif self.drawing_tool == 'text':
                self.text_preview_item.hide()
                text, ok = QInputDialog.getText(self, tr('add_text_title'), tr('enter_text'))
                if ok and text:
                    item = QGraphicsTextItem(text)
                    item.setDefaultTextColor(self.pen_color)
                    font_size = max(12, self.pen_width * 2)
                    item.setFont(QFont("Segoe UI", font_size))
                    item.setPos(scene_pos)
                    item.setZValue(1000)
                    self.scene().addItem(item)
                    self.strokes.append(item)
                    self.current_undo_transaction.append(('add', item))
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

    def mouseMoveEvent(self, event):
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
                    self.perform_area_erase(curr_pos)
                    return
                    
                if self.current_path_item:
                    if self.drawing_tool == 'pen':
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
                    
                    if self.current_path and not self.current_path.isEmpty():
                        try:
                            self.current_path_item.setPath(self.current_path)
                        except RuntimeError:
                            # Item might have been deleted
                            self.current_path_item = None
            
            # Always call super for movement even in drawing mode to ensure cursor/hover state is correct
            super().mouseMoveEvent(event)
        else:
            super().mouseMoveEvent(event)

    def perform_object_erase(self, scene_pos, delete_whole=False):
        # Use modifiers from QApplication if not passed
        from PyQt6.QtWidgets import QApplication
        if not delete_whole:
            delete_whole = bool(QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier)

        hit_rect = QRectF(scene_pos.x()-2, scene_pos.y()-2, 4, 4)
        items = self.scene().items(hit_rect)
        for item in items:
            if isinstance(item, QGraphicsPathItem) and item in self.strokes:
                path = item.path()
                pieces = self._split_into_logical_pieces(path)
                
                if len(pieces) <= 1 or delete_whole:
                    # Single piece or user wants to delete whole item
                    self.current_undo_transaction.append(('delete', item, item.path(), item.pen(), item.brush(), item.zValue()))
                    self.scene().removeItem(item)
                    self.strokes.remove(item)
                else:
                    # Multiple pieces, find which one was hit
                    new_pieces = []
                    removed_any = False
                    for piece in pieces:
                        hit_test_path = piece
                        if item.brush().style() == Qt.BrushStyle.NoBrush:
                            stroker = QPainterPathStroker()
                            stroker.setWidth(item.pen().widthF() + 4)
                            hit_test_path = stroker.createStroke(piece)
                        
                        if hit_test_path.contains(scene_pos):
                            removed_any = True
                            continue
                        new_pieces.append(piece)
                    
                    if removed_any:
                        if not new_pieces:
                            self.current_undo_transaction.append(('delete', item, item.path(), item.pen(), item.brush(), item.zValue()))
                            self.scene().removeItem(item)
                            self.strokes.remove(item)
                        else:
                            if item not in self.original_paths_in_drag:
                                self.original_paths_in_drag[item] = item.path()
                                self.current_undo_transaction.append(('modify', item, item.path()))
                            
                            new_path = QPainterPath()
                            for p in new_pieces:
                                new_path.addPath(p)
                            item.setPath(new_path)
                return
            elif isinstance(item, QGraphicsTextItem) and item in self.strokes:
                self.current_undo_transaction.append(('delete', item, None, None, None, item.zValue())) # Special for text
                self.scene().removeItem(item)
                self.strokes.remove(item)
                return

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
                        self.current_undo_transaction.append(('delete', item, item.path(), item.pen(), item.brush(), item.zValue()))
                        self.scene().removeItem(item)
                    if item in self.strokes:
                        self.strokes.remove(item)
                else:
                    # Record original path before first modification in this drag
                    if item not in self.original_paths_in_drag:
                        self.original_paths_in_drag[item] = item.path()
                        self.current_undo_transaction.append(('modify', item, item.path()))
                    
                    # STOP splitting into multiple items to maintain object identity
                    item.setPath(new_path)
            elif isinstance(item, QGraphicsTextItem) and item in self.strokes:
                # Convert text to path for precise erasing
                font = item.font()
                text_path = QPainterPath()
                # Add text at (0,0) - this is the baseline
                text_path.addText(0, 0, font, item.toPlainText())
                
                # Align the path to match the visual text position
                # QGraphicsTextItem has a default margin of 4px
                br = text_path.boundingRect()
                # Normalize path to start at (0,0)
                text_path.translate(-br.x(), -br.y())
                
                path_item = QGraphicsPathItem()
                path_item.setPath(text_path)
                
                # Match visual position (default margin is 4px)
                margin = item.document().documentMargin()
                path_item.setPos(item.pos() + QPointF(margin, margin))
                
                path_item.setPen(QPen(Qt.PenStyle.NoPen))
                path_item.setBrush(item.defaultTextColor())
                path_item.setZValue(item.zValue())
                
                # Replace the text item with the path item
                idx = self.strokes.index(item)
                self.strokes[idx] = path_item
                self.scene().removeItem(item)
                self.scene().addItem(path_item)
                
                # Perform the erase
                self.perform_area_erase(scene_pos)

    def _split_into_logical_pieces(self, path):
        subpaths = self._split_path(path)
        if len(subpaths) <= 1:
            return subpaths
            
        pieces = []
        used = [False] * len(subpaths)
        
        # Sort by bounding box area descending
        indices = sorted(range(len(subpaths)), 
                         key=lambda i: subpaths[i].boundingRect().width() * subpaths[i].boundingRect().height(), 
                         reverse=True)
        
        for i in indices:
            if used[i]: continue
            
            current_piece = QPainterPath(subpaths[i])
            used[i] = True
            
            # Find subpaths that are inside this one (holes)
            outer_path = subpaths[i]
            outer_rect = outer_path.boundingRect().adjusted(-0.5, -0.5, 0.5, 0.5)
            for j in indices:
                if used[j]: continue
                inner_rect = subpaths[j].boundingRect()
                if outer_rect.contains(inner_rect):
                    # Additional check: Does the outer path actually enclose a point of the inner one?
                    if outer_path.contains(inner_rect.center()):
                        current_piece.addPath(subpaths[j])
                        used[j] = True
            
            pieces.append(current_piece)
        return pieces

    def _split_path(self, path):
        subpaths = []
        count = path.elementCount()
        i = 0
        while i < count:
            el = path.elementAt(i)
            if el.isMoveTo():
                new_p = QPainterPath()
                new_p.moveTo(el.x, el.y)
                subpaths.append(new_p)
                i += 1
            elif el.isLineTo():
                if subpaths:
                    subpaths[-1].lineTo(el.x, el.y)
                i += 1
            elif el.isCurveTo():
                if subpaths:
                    # CurveTo elements come in triplets: C1, C2, and end point.
                    # Element i is C1, i+1 is C2, i+2 is the end point.
                    c1 = path.elementAt(i)
                    c2 = path.elementAt(i+1)
                    end = path.elementAt(i+2)
                    subpaths[-1].cubicTo(c1.x, c1.y, c2.x, c2.y, end.x, end.y)
                i += 3
            else:
                i += 1
        return subpaths

    def mouseReleaseEvent(self, event):
        if self.drawing_mode and event.button() == Qt.MouseButton.LeftButton:
            if self.current_undo_transaction:
                self.undo_stack.append(self.current_undo_transaction)
                self.current_undo_transaction = []
            
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
                    item, old_path = action[1], action[2]
                    item.setPath(old_path)

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
        # ... (keep existing wheelEvent content)
        viewport_pos = event.position()
        old_scene_pos = self.mapToScene(viewport_pos.toPoint())
        
        # 2. Calculate zoom factor
        factor = 1.1 if event.angleDelta().y() > 0 else 1/1.1
        new_zoom = self.zoomLevel * factor
        
        # 3. Clamp zoom level
        if new_zoom > 10.0:
            return
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

class ShortcutButton(PushButton):
    keyChanged = pyqtSignal(int)
    
    def __init__(self, key_code, parent=None):
        super().__init__(parent)
        self.key_code = key_code
        self.is_recording = False
        self.update_text()
        self.clicked.connect(self.start_recording)
        
    def update_text(self):
        if self.is_recording:
            self.setText(tr('press_key'))
        else:
            try:
                from PyQt6.QtGui import QKeySequence
                self.setText(QKeySequence(self.key_code).toString())
            except Exception:
                self.setText("None")
            
    def start_recording(self):
        self.is_recording = True
        self.update_text()
        self.setFocus()
        
    def keyPressEvent(self, event):
        if self.is_recording:
            key = event.key()
            if key != Qt.Key.Key_Escape:
                self.key_code = key
                self.keyChanged.emit(key)
            self.is_recording = False
            self.update_text()
            self.clearFocus()
        else:
            super().keyPressEvent(event)

