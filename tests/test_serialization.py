import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPainterPath, QPen, QColor, QBrush, QTransform
from PyQt6.QtWidgets import QGraphicsPathItem
from components.drawing_serializer import serialize_item, deserialize_item

@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app

def test_serialize_deserialize_path(qapp):
    path = QPainterPath()
    path.moveTo(0, 0)
    path.lineTo(10, 20)
    
    item = QGraphicsPathItem(path)
    item.setPen(QPen(QColor("#FF0000"), 2))
    item.setBrush(QBrush(QColor("#00FF00")))
    item.setPos(5, 5)
    item.setZValue(10)
    
    t = QTransform()
    t.translate(1, 1)
    item.setTransform(t)
    
    serialized = serialize_item(item)
    assert serialized['type'] == 'path'
    assert serialized['pos'] == (5.0, 5.0)
    assert serialized['z'] == 10.0
    assert serialized['pen']['color'] == '#ffff0000'
    assert serialized['brush']['color'] == '#ff00ff00'
    
    deserialized = deserialize_item(serialized)
    assert isinstance(deserialized, QGraphicsPathItem)
    assert deserialized.pos().x() == 5.0
    assert deserialized.pos().y() == 5.0
    assert deserialized.zValue() == 10.0
    assert deserialized.pen().color().name() == '#ff0000'
    assert deserialized.brush().color().name() == '#00ff00'
