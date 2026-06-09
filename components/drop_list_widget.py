from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtWidgets import QAbstractItemView, QListWidget

class DropListWidget(QListWidget):
    filesDropped = pyqtSignal(list)
    itemRightClicked = pyqtSignal(object, QPoint)
    deleteRequested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            self.deleteRequested.emit()
            event.accept()
        else:
            super().keyPressEvent(event)

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

    def wheelEvent(self, event):
        scrollbar = self.verticalScrollBar()
        if scrollbar and scrollbar.maximum() > scrollbar.minimum():
            delta = event.angleDelta().y()
            # Fine scrolling: 20 pixels per wheel tick (120 / 6) for maximum smoothness
            scroll_amount = -int(delta)
            scrollbar.setValue(scrollbar.value() + scroll_amount)
            event.accept()
        else:
            super().wheelEvent(event)
