import math
from typing import List, Tuple, Any, Optional

from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QRectF, QPoint, QTimer
from PyQt6.QtGui import (QPainter, QPen, QColor, QPainterPath, 
                         QPainterPathStroker, QFont, QPixmap, QImage)
from PyQt6.QtWidgets import (QGraphicsView, QInputDialog, QGraphicsPathItem, 
                             QGraphicsTextItem, QGraphicsEllipseItem, QGraphicsItemGroup,
                             QGraphicsScene, QFileDialog, QGraphicsPixmapItem, QDialog)

from translations import tr
from components.watermark_dialog import WatermarkPropertiesDialog
from components.drawing_serializer import serialize_item, deserialize_item
from components.drawing_eraser import DrawingEraserMixin
from components.zoom_view_drawing_mixin import ZoomViewDrawingMixin
from components.subtitle_renderer import SubtitleRenderer


class ZoomView(ZoomViewDrawingMixin, DrawingEraserMixin, QGraphicsView):
    zoomChanged = pyqtSignal(float)
    filesDropped = pyqtSignal(list)
    doubleClicked = pyqtSignal()
    strokesChanged = pyqtSignal()

    def __init__(self, scene: QGraphicsScene, parent=None):
        super().__init__(scene, parent)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setAcceptDrops(True)
        self.zoomLevel: float = 1.0
        
        # Drawing state
        self.drawing_mode: bool = False
        self.drawing_tool: str = 'pen'
        self.pen_color: QColor = QColor(255, 0, 0)
        self.pen_width: int = 3
        self.start_scene_pos: Optional[QPointF] = None
        self.current_path: Optional[QPainterPath] = None
        self.current_path_item: Optional[QGraphicsPathItem] = None
        self.strokes: List[Any] = []  # List of items in the scene for undo/clear
        self.laser_mode: bool = False
        
        # Temporary move/eraser state
        self.moving_watermark_item: Optional[QGraphicsPixmapItem] = None
        self.watermark_start_pos: Optional[QPointF] = None
        self.watermark_drag_offset: Optional[QPointF] = None
        self.last_eraser_pos: Optional[QPointF] = None
        
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
        self.undo_stack: List[List[Tuple]] = []
        self.current_undo_transaction: List[Tuple] = []
        self.original_paths_in_drag: dict = {} # item -> path before this drag
        self.measure_group: Optional[QGraphicsItemGroup] = None
        self.measure_line: Optional[QGraphicsPathItem] = None
        self.measure_text: Optional[QGraphicsTextItem] = None

    def scene(self) -> QGraphicsScene:
        s = super().scene()
        if s is None:
            raise RuntimeError("Scene is not set")
        return s

    def set_drawing_mode(self, enabled: bool) -> None:
        self.drawing_mode = enabled
        self.cursor_item.setVisible(enabled)
        if enabled:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setCursor(Qt.CursorShape.BlankCursor)
            self.update_cursor_size()
        else:
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def update_cursor_size(self) -> None:
        r = self.pen_width / 2.0
        self.cursor_circle.setRect(-r, -r, self.pen_width, self.pen_width)

    def undo_stroke(self) -> None:
        if self.undo_stack:
            transaction = self.undo_stack.pop()
            # Process in reverse to maintain order
            for action in reversed(transaction):
                action_type = action[0]
                if action_type == 'add':
                    item = action[1]
                    if item in self.strokes:
                        self.strokes.remove(item)
                    if item.scene():
                        self.scene().removeItem(item)
                elif action_type == 'delete':
                    item, path, pen, brush, z = action[1], action[2], action[3], action[4], action[5]
                    if path is not None: # PathItem
                        item.setPath(path)
                        item.setPen(pen)
                        item.setBrush(brush)
                    # TextItem or PathItem
                    item.setZValue(z)
                    self.scene().addItem(item)
                    self.strokes.append(item)
                elif action_type == 'modify':
                    item, old_path, old_pen, old_brush = action[1], action[2], action[3], action[4]
                    item.setPath(old_path)
                    item.setPen(old_pen)
                    item.setBrush(old_brush)
                elif action_type == 'modify_watermark':
                    item, old_opacity, old_pixmap, old_pos = action[1], action[2], action[3], action[4]
                    item.setOpacity(old_opacity)
                    item.setPixmap(old_pixmap)
                    item.setPos(old_pos)
            self.strokesChanged.emit()

    def clear_strokes(self) -> None:
        for stroke in self.strokes:
            self.scene().removeItem(stroke)
        self.strokes = []
        self.strokesChanged.emit()

    def serialize_strokes(self) -> List[dict]:
        serialized = []
        for item in self.strokes:
            try:
                data = serialize_item(item)
                if data:
                    serialized.append(data)
            except Exception as e:
                print(f"Error serializing item {item}: {e}")
        return serialized

    def deserialize_strokes(self, data_list: List[dict]) -> None:
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

    def get_scroll_state(self) -> Tuple[int, int]:
        return (self.horizontalScrollBar().value(), self.verticalScrollBar().value())
    
    def set_scroll_state(self, x: int, y: int) -> None:
        QTimer.singleShot(50, lambda: self._apply_scroll(x, y))

    def _apply_scroll(self, x: int, y: int) -> None:
        self.horizontalScrollBar().setValue(x)
        self.verticalScrollBar().setValue(y)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            files = [u.toLocalFile() for u in event.mimeData().urls()]
            self.filesDropped.emit(files)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def wheelEvent(self, event) -> None:
        viewport_pos = event.position()
        old_scene_pos = self.mapToScene(viewport_pos.toPoint())
        
        # Calculate zoom factor
        factor = 1.1 if event.angleDelta().y() > 0 else 1/1.1
        new_zoom = self.zoomLevel * factor
        
        # Clamp zoom level
        if new_zoom > 10.0:
            if self.zoomLevel == 10.0: 
                return
            actual_factor = 10.0 / self.zoomLevel
            self.zoomLevel = 10.0
        elif new_zoom < 1.0:
            if self.zoomLevel == 1.0: 
                return
            actual_factor = 1.0 / self.zoomLevel
            self.zoomLevel = 1.0
        else:
            self.zoomLevel = new_zoom
            actual_factor = factor
            
        # Apply scale with NoAnchor to handle it manually
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.scale(actual_factor, actual_factor)
        
        # Get new scene position of the same viewport point
        new_scene_pos = self.mapToScene(viewport_pos.toPoint())
        
        # Calculate the shift needed in scene coordinates
        delta = new_scene_pos - old_scene_pos
        
        # Translate the view (scroll) to keep the point fixed
        self.translate(delta.x(), delta.y())
        
        # Re-enable anchor for other interactions
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        
        self.zoomChanged.emit(self.zoomLevel)
        
        # Update cursor preview position immediately
        if self.drawing_mode:
            self.cursor_item.setPos(self.mapToScene(viewport_pos.toPoint()))

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:
        super().drawForeground(painter, rect)
        
        # Get parent window to check config and current subtitle
        win = self.window()
        if not hasattr(win, 'config') or not hasattr(win, 'subtitles'):
            return
            
        if not win.config.get('enable_subtitles', True) or not win.subtitles:
            return
            
        # Get active subtitle text
        fps = getattr(win, 'fps', 30.0)
        if fps <= 0:
            fps = 30.0
        current_time = int((getattr(win, 'current_cache_index', 0) * 1000) / fps)
        offset = win.config.get('subtitle_offset', 0)
        adjusted_time = current_time + offset
        
        active_text = ""
        for cue in win.subtitles:
            if cue['start'] <= adjusted_time <= cue['end']:
                active_text = cue['text']
                break
                
        if not active_text:
            return

        SubtitleRenderer.draw_subtitles(painter, active_text, self.viewport().width(), self.viewport().height(), win)
