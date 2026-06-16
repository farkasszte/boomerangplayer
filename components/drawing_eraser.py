"""
DrawingEraserMixin — handles precision area/object erasure and path conversion/splitting.
"""

from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPen, QBrush, QPainterPath, QPainterPathStroker, QFont, QColor
from PyQt6.QtWidgets import QGraphicsPathItem, QGraphicsTextItem, QApplication

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene
    from components.zoom_view import ZoomView
    DrawingEraserMixinBase = ZoomView
else:
    DrawingEraserMixinBase = object


class DrawingEraserMixin(DrawingEraserMixinBase):
    if TYPE_CHECKING:
        pen_width: int
        strokes: list
        current_undo_transaction: list
        original_paths_in_drag: dict
        last_eraser_pos: QPointF
        
        scene: callable
        strokesChanged: any

    def perform_object_erase(self, scene_pos, delete_whole=False):
        if not delete_whole:
            delete_whole = bool(QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier)

        hit_rect = QRectF(scene_pos.x()-4, scene_pos.y()-4, 8, 8)
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
                        
                        local_pos = item.mapFromScene(scene_pos)
                        if hit_test_path.contains(local_pos):
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
                                self.current_undo_transaction.append(('modify', item, item.path(), item.pen(), item.brush()))
                            
                            new_path = QPainterPath()
                            for p in new_pieces:
                                new_path.addPath(p)
                            item.setPath(new_path)
                return
            elif isinstance(item, QGraphicsTextItem) and item in self.strokes:
                if item.contains(item.mapFromScene(scene_pos)):
                    self.current_undo_transaction.append(('delete', item, None, None, None, item.zValue()))
                    self.scene().removeItem(item)
                    self.strokes.remove(item)
                    return

    def perform_area_erase(self, scene_pos=None, eraser_path=None):
        if eraser_path is None:
            if scene_pos is None: return
            r = self.pen_width / 2.0
            eraser_path = QPainterPath()
            eraser_path.addEllipse(scene_pos, r, r)
        
        items = self.scene().items(eraser_path.boundingRect())
        for item in items:
            if isinstance(item, QGraphicsTextItem) and item in self.strokes:
                item = self._convert_text_to_path(item)
                if not item: continue

            if isinstance(item, QGraphicsPathItem) and item in self.strokes:
                if item.brush().style() == Qt.BrushStyle.NoBrush:
                    path = item.path()
                    stroker = QPainterPathStroker()
                    stroker.setWidth(item.pen().widthF())
                    stroker.setCapStyle(item.pen().capStyle())
                    stroker.setJoinStyle(item.pen().joinStyle())
                    
                    filled_path = stroker.createStroke(path)
                    filled_path.setFillRule(Qt.FillRule.WindingFill)
                    
                    if item not in self.original_paths_in_drag:
                        self.original_paths_in_drag[item] = item.path()
                        self.current_undo_transaction.append(('modify', item, item.path(), item.pen(), item.brush()))
                    
                    item.setPath(filled_path)
                    item.setBrush(item.pen().color())
                    item.setPen(QPen(Qt.PenStyle.NoPen))
                
                path = item.path()
                local_eraser_path = item.mapFromScene(eraser_path)
                
                if not path.intersects(local_eraser_path):
                    continue

                new_path = path.subtracted(local_eraser_path)
                if new_path.isEmpty():
                    if item.scene():
                        if item not in self.original_paths_in_drag:
                             self.current_undo_transaction.append(('delete', item, item.path(), item.pen(), item.brush(), item.zValue()))
                        
                        self.scene().removeItem(item)
                        if item in self.strokes:
                            self.strokes.remove(item)
                else:
                    if item not in self.original_paths_in_drag:
                        self.original_paths_in_drag[item] = item.path()
                        self.current_undo_transaction.append(('modify', item, item.path(), item.pen(), item.brush()))
                    
                    item.setPath(new_path)

    def _create_text_path_item(self, text, pos, color, font_size, z_value):
        """Creates a QGraphicsPathItem from text string."""
        font = QFont("Segoe UI", int(font_size))
        text_path = QPainterPath()
        margin = 4.0
        from PyQt6.QtGui import QFontMetricsF
        metrics = QFontMetricsF(font)
        ascent = metrics.ascent()
        
        text_path.addText(margin, margin + ascent, font, text)
        
        path_item = QGraphicsPathItem()
        path_item.setPath(text_path)
        path_item.setPen(QPen(Qt.PenStyle.NoPen))
        path_item.setBrush(color)
        path_item.setZValue(z_value)
        path_item.setPos(pos)
        return path_item

    def _convert_text_to_path(self, item):
        """Helper to convert an existing QGraphicsTextItem into a QGraphicsPathItem."""
        if not isinstance(item, QGraphicsTextItem) or item not in self.strokes:
            return None

        self.current_undo_transaction.append(('delete', item, None, None, None, item.zValue()))
        
        text = item.toPlainText()
        font = item.font()
        font_size = font.pointSize() if font.pointSize() > 0 else font.pixelSize()
        
        path_item = self._create_text_path_item(text, QPointF(0,0), item.defaultTextColor(), font_size, item.zValue())
        path_item.setTransform(item.sceneTransform())
        
        idx = self.strokes.index(item)
        self.strokes[idx] = path_item
        self.current_undo_transaction.append(('add', path_item))
        
        self.scene().removeItem(item)
        self.scene().addItem(path_item)
        return path_item

    def _split_into_logical_pieces(self, path):
        subpaths = self._split_path(path)
        if len(subpaths) <= 1:
            return subpaths
            
        pieces = []
        used = [False] * len(subpaths)
        
        indices = sorted(range(len(subpaths)), 
                          key=lambda i: subpaths[i].boundingRect().width() * subpaths[i].boundingRect().height(), 
                          reverse=True)
        
        for i in indices:
            if used[i]: continue
            
            current_piece = QPainterPath(subpaths[i])
            used[i] = True
            
            outer_path = subpaths[i]
            outer_rect = outer_path.boundingRect().adjusted(-0.5, -0.5, 0.5, 0.5)
            for j in indices:
                if used[j]: continue
                inner_rect = subpaths[j].boundingRect()
                if outer_rect.contains(inner_rect):
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
                    c1 = path.elementAt(i)
                    c2 = path.elementAt(i+1)
                    end = path.elementAt(i+2)
                    subpaths[-1].cubicTo(c1.x, c1.y, c2.x, c2.y, end.x, end.y)
                i += 3
            else:
                i += 1
        return subpaths
