import math
from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QRectF, QPoint
from PyQt6.QtGui import QPainter, QPen, QColor, QPainterPath, QPainterPathStroker, QFont, QImage
from PyQt6.QtWidgets import (QGraphicsView, QSlider, QInputDialog, QGraphicsPathItem, 
                             QGraphicsTextItem, QGraphicsEllipseItem, QGraphicsItemGroup,
                             QGraphicsPixmapItem, QStyleOptionGraphicsItem, QAbstractItemView)
from PyQt6.QtOpenGL import QOpenGLShaderProgram, QOpenGLShader, QOpenGLTexture
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtGui import QMatrix4x4
from qfluentwidgets import ListWidget, PushButton
from translations import tr

class DropListWidget(ListWidget):
    filesDropped = pyqtSignal(list)
    itemRightClicked = pyqtSignal(object, QPoint)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

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
        self.is_zoomed = False
        
    def update_markers(self, markers):
        self.markers = sorted(list(set(markers)))
        self.update()

    def set_zoomed(self, enabled):
        self.is_zoomed = enabled
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            r = self.maximum() - self.minimum()
            if r > 0:
                val = self.minimum() + (r * event.position().x()) / self.width()
                self.setValue(int(val))
                self.sliderMoved.emit(int(val))
        super().mousePressEvent(event)

    def paintEvent(self, event):
        if self.maximum() <= self.minimum():
            super().paintEvent(event)
            return

        w = self.width()
        h = self.height()
        r = self.maximum() - self.minimum()

        # 1. Draw Zoom Highlight BACKGROUND before the slider itself
        if self.is_zoomed:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            # Use a very subtle dark cyan tint for the background
            painter.setOpacity(0.15)
            painter.setBrush(QColor(0, 242, 255))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(0, 0, w, h)
            # Draw a slightly more visible border
            painter.setOpacity(0.4)
            painter.setPen(QPen(QColor(0, 242, 255), 1))
            painter.drawRect(0, 0, w-1, h-1)
            painter.end()

        # 2. Draw the standard QSlider (groove, sub-page/accent, handle)
        super().paintEvent(event)

        # 3. Draw Markers OVER the slider
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(0, 153, 255))
        pen.setWidth(2)
        painter.setPen(pen)
        
        for m in self.markers:
            if self.minimum() < m < self.maximum():
                mx = int(((m - self.minimum()) / r) * w)
                painter.drawLine(mx, 0, mx, h)
        painter.end()

class GPUPixmapItem(QGraphicsPixmapItem):
    """
    A GraphicsItem that draws a pixmap using an OpenGL shader for 
    real-time image adjustments (Brightness, Contrast, Gamma, Saturation).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.shader = None
        self.gpu_enabled = False
        
        # Image adjustment parameters
        self.brightness = 0.0    # -1.0 to 1.0
        self.contrast = 1.0      # 0.0 to 2.0
        self.gamma = 1.0         # 0.1 to 3.0
        self.saturation = 1.0    # 0.0 to 2.0
        
        self.texture = None
        self._last_pixmap_id = None

    def __del__(self):
        if self.texture:
            self.texture.destroy()

    def update_params(self, b, c, g, s):
        self.brightness = b / 100.0
        self.contrast = c
        self.gamma = g
        self.saturation = s
        self.update()

    def _init_shader(self):
        if self.shader is not None:
            return
            
        self.shader = QOpenGLShaderProgram()
        
        v_shader = """#version 120
        attribute vec4 vertex;
        attribute vec2 texCoord;
        uniform mat4 matrix;
        varying vec2 v_texCoord;
        void main(void) {
            gl_Position = matrix * vertex;
            v_texCoord = texCoord;
        }
        """
        
        f_shader = """#version 120
        varying vec2 v_texCoord;
        uniform sampler2D u_texture;
        uniform float u_opacity;
        
        uniform float u_brightness;
        uniform float u_contrast;
        uniform float u_gamma;
        uniform float u_saturation;
        
        void main(void) {
            vec4 color = texture2D(u_texture, v_texCoord);
            
            // 1. Brightness & Contrast
            // Apply (x - 0.5) * contrast + 0.5 + brightness
            vec3 rgb = color.rgb;
            rgb = (rgb - 0.5) * u_contrast + 0.5 + u_brightness;
            
            // 2. Gamma
            if (u_gamma != 1.0 && u_gamma > 0.0) {
                rgb = pow(max(rgb, vec3(0.0)), vec3(1.0 / u_gamma));
            }
            
            // 3. Saturation
            if (u_saturation != 1.0) {
                float gray = dot(rgb, vec3(0.299, 0.587, 0.114));
                rgb = mix(vec3(gray), rgb, u_saturation);
            }
            
            gl_FragColor = vec4(rgb, color.a * u_opacity);
        }
        """
        
        if not self.shader.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Vertex, v_shader):
            print("Vertex shader error:", self.shader.log())
        if not self.shader.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Fragment, f_shader):
            print("Fragment shader error:", self.shader.log())
            
        if not self.shader.link():
            print("Shader link error:", self.shader.log())

    def paint(self, painter, option, widget):
        try:
            if not self.gpu_enabled or self.pixmap().isNull():
                super().paint(painter, option, widget)
                return

            # Ensure we are rendering in an OpenGL context
            if not isinstance(widget, QOpenGLWidget):
                super().paint(painter, option, widget)
                return

            self._init_shader()
            
            if not self.shader or not self.shader.isLinked():
                super().paint(painter, option, widget)
                return

            pix = self.pixmap()
            img = pix.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
            
            # Update texture if pixmap changed
            current_key = pix.cacheKey()
            if self.texture is None or self.texture.width() != pix.width() or self.texture.height() != pix.height():
                if self.texture:
                    self.texture.destroy()
                self.texture = QOpenGLTexture(QOpenGLTexture.Target.Target2D)
                self.texture.setSize(pix.width(), pix.height())
                self.texture.setFormat(QOpenGLTexture.TextureFormat.RGBA8_UNorm)
                self.texture.allocateStorage()
                self.texture.setMinificationFilter(QOpenGLTexture.Filter.Linear)
                self.texture.setMagnificationFilter(QOpenGLTexture.Filter.Linear)
                self.texture.setWrapMode(QOpenGLTexture.WrapMode.ClampToEdge)
            
            if current_key != self._last_pixmap_id:
                # Optimized update: reuse memory, just copy pixels
                self.texture.setData(QOpenGLTexture.PixelFormat.RGBA, QOpenGLTexture.PixelType.UInt8, img.constBits())
                self._last_pixmap_id = current_key

            painter.beginNativePainting()
            
            self.shader.bind()
            
            # Get attribute locations
            v_loc = self.shader.attributeLocation("vertex")
            t_loc = self.shader.attributeLocation("texCoord")
            
            # Setup Projection Matrix
            matrix = QMatrix4x4(painter.combinedTransform())
            
            proj = QMatrix4x4()
            proj.ortho(0, widget.width(), widget.height(), 0, -1, 1)
            
            self.shader.setUniformValue("matrix", proj * matrix)
            self.shader.setUniformValue("u_brightness", float(self.brightness))
            self.shader.setUniformValue("u_contrast", float(self.contrast))
            self.shader.setUniformValue("u_gamma", float(self.gamma))
            self.shader.setUniformValue("u_saturation", float(self.saturation))
            self.shader.setUniformValue("u_opacity", float(painter.opacity()))
            self.shader.setUniformValue("u_texture", 0)

            self.texture.bind(0)
            
            # Draw Quad
            w = float(pix.width())
            h = float(pix.height())
            
            import numpy as np
            vertices = np.array([0.0, 0.0, w, 0.0, w, h, 0.0, h], dtype=np.float32).reshape(-1, 2)
            texCoords = np.array([0.0, 0.0, 1.0, 0.0, 1.0, 1.0, 0.0, 1.0], dtype=np.float32).reshape(-1, 2)
            
            from PyQt6.QtOpenGL import QOpenGLFunctions_2_1
            gl = QOpenGLFunctions_2_1()
            gl.initializeOpenGLFunctions()
            
            # Ensure viewport is correct
            gl.glViewport(0, 0, widget.width(), widget.height())
            
            self.shader.enableAttributeArray(v_loc)
            self.shader.enableAttributeArray(t_loc)
            
            # Use 2-argument call, shape will define the tuple size
            self.shader.setAttributeArray(v_loc, vertices)
            self.shader.setAttributeArray(t_loc, texCoords)
            
            gl.glDrawArrays(0x0006, 0, 4) # GL_TRIANGLE_FAN is 0x0006
            
            self.shader.disableAttributeArray(v_loc)
            self.shader.disableAttributeArray(t_loc)
            
            self.shader.release()
            self.texture.release()
            
            painter.endNativePainting()
            
        except Exception as e:
            # Fallback to standard painting on error
            print(f"Shader paint error: {e}")
            super().paint(painter, option, widget)

class ZoomView(QGraphicsView):
    zoomChanged = pyqtSignal(float)
    filesDropped = pyqtSignal(list)
    doubleClicked = pyqtSignal()

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
        self.last_eraser_pos = None
        self.measure_group = None

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
            self.doubleClicked.emit()
        else:
            super().mouseDoubleClickEvent(event)

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
                elif self.drawing_tool == 'measure' and self.measure_group:
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

    def perform_object_erase(self, scene_pos, delete_whole=False):
        # Use modifiers from QApplication if not passed
        from PyQt6.QtWidgets import QApplication
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
                # More robust hit test for text
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
            # If it's text, convert it to a path first so we can erase parts of it
            if isinstance(item, QGraphicsTextItem) and item in self.strokes:
                item = self._convert_text_to_path(item)
                if not item: continue

            if isinstance(item, QGraphicsPathItem) and item in self.strokes:
                # If the item was originally a stroke (NoBrush), we convert it to an area
                # so that subtraction removes "thickness" from the line.
                if item.brush().style() == Qt.BrushStyle.NoBrush:
                    path = item.path()
                    stroker = QPainterPathStroker()
                    stroker.setWidth(item.pen().widthF())
                    stroker.setCapStyle(item.pen().capStyle())
                    stroker.setJoinStyle(item.pen().joinStyle())
                    
                    filled_path = stroker.createStroke(path)
                    # Use WindingFill for stroke-to-area conversion to prevent weird holes
                    filled_path.setFillRule(Qt.FillRule.WindingFill)
                    
                    # Store original state for undo BEFORE modifying
                    if item not in self.original_paths_in_drag:
                        self.original_paths_in_drag[item] = item.path()
                        self.current_undo_transaction.append(('modify', item, item.path(), item.pen(), item.brush()))
                    
                    item.setPath(filled_path)
                    item.setBrush(item.pen().color())
                    item.setPen(QPen(Qt.PenStyle.NoPen))
                
                # Now perform subtraction on the (now filled) path
                path = item.path()
                # Map eraser path to item's local coordinates
                local_eraser_path = item.mapFromScene(eraser_path)
                
                if not path.intersects(local_eraser_path):
                    continue

                new_path = path.subtracted(local_eraser_path)
                if new_path.isEmpty():
                    if item.scene():
                        if item not in self.original_paths_in_drag: # Should already be there if modified
                             self.current_undo_transaction.append(('delete', item, item.path(), item.pen(), item.brush(), item.zValue()))
                        else:
                            # If already in modify, we need a way to restore it as deleted
                            # For simplicity, we just delete it from scene
                            pass
                        
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
        # Match QGraphicsTextItem default margin
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
        
        # Replace in strokes list
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

