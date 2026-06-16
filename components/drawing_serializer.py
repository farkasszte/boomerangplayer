"""
DrawingSerializer — functions to serialize and deserialize vector drawings (paths, watermarks, text, and groups).
"""

import base64
from PyQt6.QtCore import Qt, QByteArray, QBuffer, QIODevice, QPointF
from PyQt6.QtGui import QColor, QPen, QBrush, QTransform, QFont, QPainterPath, QImage, QPixmap
from PyQt6.QtWidgets import QGraphicsPathItem, QGraphicsPixmapItem, QGraphicsTextItem, QGraphicsItemGroup


def serialize_item(item):
    if isinstance(item, QGraphicsPathItem):
        path = item.path()
        elements = []
        for i in range(path.elementCount()):
            el = path.elementAt(i)
            elements.append((el.type.value, el.x, el.y))
        
        pen = item.pen()
        pen_data = {
            'color': pen.color().name(QColor.NameFormat.HexArgb),
            'width': pen.widthF(),
            'style': pen.style().value,
            'cap': pen.capStyle().value,
            'join': pen.joinStyle().value
        }
        
        brush = item.brush()
        brush_data = {
            'color': brush.color().name(QColor.NameFormat.HexArgb),
            'style': brush.style().value
        }
        
        t = item.transform()
        return {
            'type': 'path',
            'elements': elements,
            'pen': pen_data,
            'brush': brush_data,
            'pos': (item.pos().x(), item.pos().y()),
            'z': item.zValue(),
            'transform': [t.m11(), t.m12(), t.m13(), t.m21(), t.m22(), t.m23(), t.m31(), t.m32(), t.m33()]
        }
        
    elif isinstance(item, QGraphicsPixmapItem):
        pixmap = item.pixmap()
        ba = QByteArray()
        buffer = QBuffer(ba)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        pixmap.toImage().save(buffer, "PNG")
        b64 = base64.b64encode(ba.data()).decode('utf-8')
        t = item.transform()
        return {
            'type': 'watermark',
            'image_b64': b64,
            'opacity': item.opacity(),
            'pos': (item.pos().x(), item.pos().y()),
            'z': item.zValue(),
            'transform': [t.m11(), t.m12(), t.m13(), t.m21(), t.m22(), t.m23(), t.m31(), t.m32(), t.m33()]
        }
        
    elif isinstance(item, QGraphicsTextItem):
        t = item.transform()
        return {
            'type': 'text',
            'html': item.toHtml(),
            'text_color': item.defaultTextColor().name(QColor.NameFormat.HexArgb),
            'font_family': item.font().family(),
            'font_size': item.font().pointSize(),
            'font_bold': item.font().bold(),
            'pos': (item.pos().x(), item.pos().y()),
            'z': item.zValue(),
            'transform': [t.m11(), t.m12(), t.m13(), t.m21(), t.m22(), t.m23(), t.m31(), t.m32(), t.m33()]
        }
        
    elif isinstance(item, QGraphicsItemGroup):
        children = []
        for child in item.childItems():
            c_data = serialize_item(child)
            if c_data:
                children.append(c_data)
        t = item.transform()
        return {
            'type': 'group',
            'children': children,
            'pos': (item.pos().x(), item.pos().y()),
            'z': item.zValue(),
            'transform': [t.m11(), t.m12(), t.m13(), t.m21(), t.m22(), t.m23(), t.m31(), t.m32(), t.m33()]
        }
    return None


def deserialize_item(data):
    t_data = data.get('transform', [1, 0, 0, 0, 1, 0, 0, 0, 1])
    t = QTransform(t_data[0], t_data[1], t_data[2], t_data[3], t_data[4], t_data[5], t_data[6], t_data[7], t_data[8])
    
    item_type = data.get('type')
    if item_type == 'path':
        path = QPainterPath()
        elements = data.get('elements', [])
        i = 0
        while i < len(elements):
            el_type, x, y = elements[i]
            if el_type == 0:  # MoveTo
                path.moveTo(x, y)
                i += 1
            elif el_type == 1:  # LineTo
                path.lineTo(x, y)
                i += 1
            elif el_type == 2:  # CurveTo
                if i + 2 < len(elements):
                    c1_x, c1_y = elements[i][1], elements[i][2]
                    c2_x, c2_y = elements[i+1][1], elements[i+1][2]
                    end_x, end_y = elements[i+2][1], elements[i+2][2]
                    path.cubicTo(c1_x, c1_y, c2_x, c2_y, end_x, end_y)
                i += 3
            else:
                i += 1
                
        item = QGraphicsPathItem()
        item.setPath(path)
        
        p_data = data.get('pen', {})
        if p_data:
            pen = QPen(QColor(p_data['color']))
            pen.setWidthF(p_data.get('width', 1.0))
            pen.setStyle(Qt.PenStyle(p_data.get('style', 1)))
            pen.setCapStyle(Qt.PenCapStyle(p_data.get('cap', 0x10)))
            pen.setJoinStyle(Qt.PenJoinStyle(p_data.get('join', 0x80)))
            item.setPen(pen)
            
        b_data = data.get('brush', {})
        if b_data:
            brush = QBrush(QColor(b_data['color']))
            brush.setStyle(Qt.BrushStyle(b_data.get('style', 0)))
            item.setBrush(brush)
            
        item.setZValue(data.get('z', 1000))
        pos = data.get('pos', (0, 0))
        item.setPos(QPointF(pos[0], pos[1]))
        item.setTransform(t)
        return item
        
    elif item_type == 'watermark':
        b64 = data.get('image_b64', '')
        ba = QByteArray.fromBase64(b64.encode('utf-8'))
        img = QImage()
        img.loadFromData(ba)
        pixmap = QPixmap.fromImage(img)
        
        item = QGraphicsPixmapItem(pixmap)
        item.setOpacity(data.get('opacity', 0.5))
        item.setZValue(data.get('z', 1000))
        pos = data.get('pos', (0, 0))
        item.setPos(QPointF(pos[0], pos[1]))
        item.setTransform(t)
        return item
        
    elif item_type == 'text':
        item = QGraphicsTextItem()
        item.setHtml(data.get('html', ''))
        item.setDefaultTextColor(QColor(data.get('text_color', '#ffffff')))
        
        font = QFont(data.get('font_family', 'Segoe UI'), data.get('font_size', 12))
        font.setBold(data.get('font_bold', False))
        item.setFont(font)
        
        item.setZValue(data.get('z', 1000))
        pos = data.get('pos', (0, 0))
        item.setPos(QPointF(pos[0], pos[1]))
        item.setTransform(t)
        return item
        
    elif item_type == 'group':
        item = QGraphicsItemGroup()
        for c_data in data.get('children', []):
            child = deserialize_item(c_data)
            if child:
                item.addToGroup(child)
        item.setZValue(data.get('z', 1000))
        pos = data.get('pos', (0, 0))
        item.setPos(QPointF(pos[0], pos[1]))
        item.setTransform(t)
        return item
        
    return None
