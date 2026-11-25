from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QRect
from PyQt6.QtGui import QPainter, QPen, QColor
from PyQt6.QtWidgets import QAbstractItemView, QListView, QListWidget


class DropListWidget(QListWidget):
    filesDropped = pyqtSignal(list)
    filesDroppedAt = pyqtSignal(list, int)
    orderChanged = pyqtSignal()
    itemRightClicked = pyqtSignal(object, QPoint)
    deleteRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drop_indicator_rect: QRect | None = None
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._ensure_drag_drop_enabled()

    def _ensure_drag_drop_enabled(self):
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        if self.viewport() is not None:
            self.viewport().setAcceptDrops(True)
        self.setDropIndicatorShown(False)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

    def setMovement(self, movement):
        super().setMovement(movement)
        # Qt's QListView.setMovement(Static) disables dragEnabled and acceptDrops; restore them.
        self._ensure_drag_drop_enabled()

    def setViewMode(self, mode):
        super().setViewMode(mode)
        self._ensure_drag_drop_enabled()

    def minimumSizeHint(self):
        from PyQt6.QtCore import QSize
        return QSize(50, 50)

    def sizeHint(self):
        from PyQt6.QtCore import QSize
        return QSize(100, 100)

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

    def _event_pos(self, event) -> QPoint:
        if hasattr(event, 'position'):
            return event.position().toPoint()
        return event.pos()

    def _compute_drop_target(self, pos: QPoint) -> tuple[int, QRect | None]:
        count = self.count()
        vp = self.viewport()
        vw = vp.width() if vp else self.width()
        vh = vp.height() if vp else self.height()
        if count == 0:
            return 0, QRect(4, 2, max(10, vw - 8), 2)

        is_icon_mode = self.viewMode() == QListView.ViewMode.IconMode
        item = self.itemAt(pos)

        if item is not None:
            row = self.row(item)
            rect = self.visualItemRect(item)
            if is_icon_mode:
                if pos.x() < rect.center().x():
                    x = max(1, rect.left() - 2)
                    return row, QRect(x, rect.top(), 3, rect.height())
                else:
                    x = min(vw - 4, rect.right() + 1)
                    return row + 1, QRect(x, rect.top(), 3, rect.height())
            else:
                if pos.y() < rect.center().y():
                    y = max(1, rect.top() - 1)
                    return row, QRect(4, y, max(10, vw - 8), 2)
                else:
                    y = min(vh - 3, rect.bottom())
                    return row + 1, QRect(4, y, max(10, vw - 8), 2)

        # Cursor is in spacing or empty area: find nearest item
        if is_icon_mode:
            best_row = count
            best_rect = None
            for i in range(count):
                r = self.visualItemRect(self.item(i))
                # If on the same visual row or above a lower row
                if pos.y() < r.top():
                    x = max(1, r.left() - 2)
                    return i, QRect(x, r.top(), 3, r.height())
                if r.top() <= pos.y() <= r.bottom():
                    if pos.x() < r.center().x():
                        x = max(1, r.left() - 2)
                        return i, QRect(x, r.top(), 3, r.height())
                    best_row = i + 1
                    x = min(vw - 4, r.right() + 1)
                    best_rect = QRect(x, r.top(), 3, r.height())
            if best_rect is not None:
                return best_row, best_rect
            last_rect = self.visualItemRect(self.item(count - 1))
            x = min(vw - 4, last_rect.right() + 1)
            return count, QRect(x, last_rect.top(), 3, last_rect.height())
        else:
            first_rect = self.visualItemRect(self.item(0))
            if pos.y() < first_rect.top():
                return 0, QRect(4, max(1, first_rect.top() - 1), max(10, vw - 8), 2)
            for i in range(count):
                r = self.visualItemRect(self.item(i))
                if pos.y() < r.center().y():
                    return i, QRect(4, max(1, r.top() - 1), max(10, vw - 8), 2)
            last_rect = self.visualItemRect(self.item(count - 1))
            y = min(vh - 3, last_rect.bottom())
            return count, QRect(4, y, max(10, vw - 8), 2)

    def dragEnterEvent(self, event):
        if event.source() is self:
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
        elif event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        pos = self._event_pos(event)
        if event.source() is self:
            _, self._drop_indicator_rect = self._compute_drop_target(pos)
            self.viewport().update()
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
        elif event.mimeData().hasUrls():
            _, self._drop_indicator_rect = self._compute_drop_target(pos)
            self.viewport().update()
            event.acceptProposedAction()
        else:
            self._drop_indicator_rect = None
            self.viewport().update()
            event.ignore()

    def dragLeaveEvent(self, event):
        self._drop_indicator_rect = None
        self.viewport().update()
        super().dragLeaveEvent(event)

    def move_rows(self, source_rows: list[int], target_row: int):
        """Move the given row indices to target_row (pre-removal index in 0..count())."""
        count = self.count()
        if not source_rows or count <= 1:
            return
        unique_rows = sorted(r for r in set(source_rows) if 0 <= r < count)
        if not unique_rows:
            return
        target_row = max(0, min(count, target_row))

        curr_item = self.currentItem()
        moving_items = [self.item(r) for r in unique_rows]
        shift = sum(1 for r in unique_rows if r < target_row)

        for r in reversed(unique_rows):
            self.takeItem(r)

        insert_at = max(0, min(self.count(), target_row - shift))
        for idx, item in enumerate(moving_items):
            self.insertItem(insert_at + idx, item)

        self.clearSelection()
        for item in moving_items:
            item.setSelected(True)
        if curr_item in moving_items:
            self.setCurrentItem(curr_item)
        elif moving_items:
            self.setCurrentItem(moving_items[0])

        if self.viewMode() == QListView.ViewMode.IconMode:
            self.doItemsLayout()
        self.viewport().update()
        self.orderChanged.emit()

    def dropEvent(self, event):
        pos = self._event_pos(event)
        target_row, _ = self._compute_drop_target(pos)
        self._drop_indicator_rect = None
        self.viewport().update()

        if event.source() is self:
            selected_rows = [self.row(i) for i in self.selectedItems()]
            if not selected_rows and self.currentItem():
                selected_rows = [self.row(self.currentItem())]
            self.move_rows(selected_rows, target_row)
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
            return

        if event.mimeData().hasUrls():
            files = [u.toLocalFile() for u in event.mimeData().urls() if u.toLocalFile()]
            if files:
                self.filesDroppedAt.emit(files, target_row)
                self.filesDropped.emit(files)
            event.acceptProposedAction()
            return

        event.ignore()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._drop_indicator_rect is not None:
            painter = QPainter(self.viewport())
            accent = self.palette().color(self.palette().ColorRole.Highlight)
            if not accent.isValid():
                accent = QColor("#00f2ff")
            painter.fillRect(self._drop_indicator_rect, accent)
            painter.end()

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
