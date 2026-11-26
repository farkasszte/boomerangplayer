from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QRect, QByteArray, QMimeData, QSize, QTimer
from PyQt6.QtGui import QDrag, QPainter, QPen, QColor, QPixmap
from PyQt6.QtWidgets import QAbstractItemView, QListView, QListWidget

INTERNAL_MIME_TYPE = "application/x-boomerang-playlist-rows"


class DropListWidget(QListWidget):
    filesDropped = pyqtSignal(list)
    filesDroppedAt = pyqtSignal(list, int)
    orderChanged = pyqtSignal()
    itemRightClicked = pyqtSignal(object, QPoint)
    deleteRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drop_indicator_rect: QRect | None = None
        self._dragged_rows: list[int] = []
        self._auto_scroll_dir: int = 0
        self._auto_scroll_timer = QTimer(self)
        self._auto_scroll_timer.setInterval(30)
        self._auto_scroll_timer.timeout.connect(self._on_auto_scroll_tick)
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
        self.setDragDropOverwriteMode(False)

    def setMovement(self, movement):
        super().setMovement(movement)
        # Qt's QListView.setMovement(Static) disables dragEnabled and acceptDrops; restore them.
        self._ensure_drag_drop_enabled()

    def setViewMode(self, mode):
        super().setViewMode(mode)
        # Keep IconMode grid-ordered instead of free-floating, and preserve drag-drop flags.
        super().setMovement(QListView.Movement.Static)
        self._ensure_drag_drop_enabled()

    def minimumSizeHint(self):
        return QSize(50, 50)

    def sizeHint(self):
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

    def startDrag(self, supportedActions):
        # Do NOT call super().startDrag(): QAbstractItemView::startDrag() runs clearOrRemove()
        # on MoveAction, which deletes items right after dropEvent() finishes.
        rows = sorted({
            idx.row()
            for idx in self.selectedIndexes()
            if 0 <= idx.row() < self.count()
        })
        if not rows:
            return

        self._dragged_rows = rows
        mime = QMimeData()
        mime.setData(INTERNAL_MIME_TYPE, QByteArray(",".join(str(r) for r in rows).encode("utf-8")))

        drag = QDrag(self)
        drag.setMimeData(mime)
        preview = self._build_drag_pixmap(rows)
        if preview is not None and not preview.isNull():
            drag.setPixmap(preview)
            drag.setHotSpot(QPoint(min(16, preview.width() // 2), min(16, preview.height() // 2)))

        try:
            drag.exec(Qt.DropAction.MoveAction)
        finally:
            self._dragged_rows = []
            self._clear_drop_indicator()

    def _build_drag_pixmap(self, rows: list[int]) -> QPixmap | None:
        first_item = self.item(rows[0])
        if first_item is None:
            return None
        icon = first_item.icon()
        if icon and not icon.isNull():
            pm = icon.pixmap(48, 48)
            if not pm.isNull():
                return pm

        label = first_item.text() if len(rows) == 1 else f"{len(rows)} items"
        if not label:
            label = f"{len(rows)} items"
        pm = QPixmap(140, 26)
        pm.fill(QColor(45, 45, 45, 220))
        painter = QPainter(pm)
        accent = self.palette().color(self.palette().ColorRole.Highlight)
        painter.setPen(QPen(accent if accent.isValid() else QColor("#00f2ff"), 1))
        painter.drawRect(0, 0, pm.width() - 1, pm.height() - 1)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(
            pm.rect().adjusted(6, 0, -6, 0),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            label[:18],
        )
        painter.end()
        return pm

    def _event_pos(self, event) -> QPoint:
        if hasattr(event, 'position'):
            return event.position().toPoint()
        return event.pos()

    def _is_internal_drag(self, event) -> bool:
        return event.source() is self and (
            event.mimeData().hasFormat(INTERNAL_MIME_TYPE) or not event.mimeData().hasUrls()
        )

    def _parse_mime_rows(self, mime: QMimeData) -> list[int]:
        if mime and mime.hasFormat(INTERNAL_MIME_TYPE):
            raw = bytes(mime.data(INTERNAL_MIME_TYPE)).decode("utf-8", errors="ignore")
            parsed = []
            for part in raw.split(","):
                part = part.strip()
                if part.isdigit():
                    r = int(part)
                    if 0 <= r < self.count():
                        parsed.append(r)
            if parsed:
                return sorted(set(parsed))
        if self._dragged_rows:
            return [r for r in self._dragged_rows if 0 <= r < self.count()]
        selected_rows = [self.row(i) for i in self.selectedItems() if 0 <= self.row(i) < self.count()]
        if selected_rows:
            return sorted(set(selected_rows))
        if self.currentItem():
            r = self.row(self.currentItem())
            if 0 <= r < self.count():
                return [r]
        return []

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
                x = min(vw - 4, rect.right() + 1)
                return row + 1, QRect(x, rect.top(), 3, rect.height())
            if pos.y() < rect.center().y():
                y = max(1, rect.top() - 1)
                return row, QRect(4, y, max(10, vw - 8), 2)
            y = min(vh - 3, rect.bottom())
            return row + 1, QRect(4, y, max(10, vw - 8), 2)

        # Cursor is in spacing or empty area: find nearest valid item
        valid_rects = [(i, self.visualItemRect(self.item(i))) for i in range(count)]
        valid_rects = [(i, r) for i, r in valid_rects if r.isValid()]
        if not valid_rects:
            return count, None

        if is_icon_mode:
            pad = max(4, self.spacing())
            band_items = [
                (i, r) for i, r in valid_rects
                if (r.top() - pad) <= pos.y() <= (r.bottom() + pad)
            ]
            if band_items:
                band_items.sort(key=lambda pair: pair[1].left())
                for i, r in band_items:
                    if pos.x() < r.center().x():
                        x = max(1, r.left() - 2)
                        return i, QRect(x, r.top(), 3, r.height())
                last_i, last_r = band_items[-1]
                x = min(vw - 4, last_r.right() + 1)
                return last_i + 1, QRect(x, last_r.top(), 3, last_r.height())

            for i, r in valid_rects:
                if pos.y() < r.center().y():
                    x = max(1, r.left() - 2)
                    return i, QRect(x, r.top(), 3, r.height())
            last_r = valid_rects[-1][1]
            x = min(vw - 4, last_r.right() + 1)
            return count, QRect(x, last_r.top(), 3, last_r.height())

        first_rect = valid_rects[0][1]
        if pos.y() < first_rect.top():
            return 0, QRect(4, max(1, first_rect.top() - 1), max(10, vw - 8), 2)
        for i, r in valid_rects:
            if pos.y() < r.center().y():
                return i, QRect(4, max(1, r.top() - 1), max(10, vw - 8), 2)
        last_rect = valid_rects[-1][1]
        y = min(vh - 3, last_rect.bottom())
        return count, QRect(4, y, max(10, vw - 8), 2)

    def _clear_drop_indicator(self):
        self._auto_scroll_dir = 0
        if self._auto_scroll_timer.isActive():
            self._auto_scroll_timer.stop()
        if self._drop_indicator_rect is not None:
            self._drop_indicator_rect = None
            if self.viewport() is not None:
                self.viewport().update()

    def _update_auto_scroll(self, pos: QPoint):
        sb = self.verticalScrollBar()
        if not sb or sb.maximum() <= sb.minimum():
            self._auto_scroll_dir = 0
            if self._auto_scroll_timer.isActive():
                self._auto_scroll_timer.stop()
            return

        vh = self.viewport().height() if self.viewport() else self.height()
        margin = 24
        if pos.y() < margin:
            self._auto_scroll_dir = -1
        elif pos.y() > vh - margin:
            self._auto_scroll_dir = 1
        else:
            self._auto_scroll_dir = 0

        if self._auto_scroll_dir != 0 and not self._auto_scroll_timer.isActive():
            self._auto_scroll_timer.start()
        elif self._auto_scroll_dir == 0 and self._auto_scroll_timer.isActive():
            self._auto_scroll_timer.stop()

    def _on_auto_scroll_tick(self):
        if self._auto_scroll_dir == 0:
            self._auto_scroll_timer.stop()
            return
        sb = self.verticalScrollBar()
        if sb:
            sb.setValue(sb.value() + self._auto_scroll_dir * 8)

    def dragEnterEvent(self, event):
        pos = self._event_pos(event)
        if self._is_internal_drag(event):
            _, self._drop_indicator_rect = self._compute_drop_target(pos)
            self.viewport().update()
            self._update_auto_scroll(pos)
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
        elif event.mimeData().hasUrls():
            _, self._drop_indicator_rect = self._compute_drop_target(pos)
            self.viewport().update()
            self._update_auto_scroll(pos)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        pos = self._event_pos(event)
        if self._is_internal_drag(event):
            _, self._drop_indicator_rect = self._compute_drop_target(pos)
            self.viewport().update()
            self._update_auto_scroll(pos)
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
        elif event.mimeData().hasUrls():
            _, self._drop_indicator_rect = self._compute_drop_target(pos)
            self.viewport().update()
            self._update_auto_scroll(pos)
            event.acceptProposedAction()
        else:
            self._clear_drop_indicator()
            event.ignore()

    def dragLeaveEvent(self, event):
        self._clear_drop_indicator()
        super().dragLeaveEvent(event)

    def move_rows(self, source_rows: list[int], target_row: int) -> bool:
        """Move the given row indices to target_row (pre-removal index in 0..count())."""
        count = self.count()
        if not source_rows or count <= 1:
            return False
        unique_rows = sorted(r for r in set(source_rows) if 0 <= r < count)
        if not unique_rows:
            return False

        target_row = max(0, min(count, target_row))
        shift = sum(1 for r in unique_rows if r < target_row)
        insert_at = max(0, min(count - len(unique_rows), target_row - shift))

        row_set = set(unique_rows)
        remaining = [i for i in range(count) if i not in row_set]
        new_order = remaining[:insert_at] + unique_rows + remaining[insert_at:]
        if new_order == list(range(count)):
            return False

        curr_item = self.currentItem()
        taken_desc = [self.takeItem(r) for r in reversed(unique_rows)]
        moving_items = [it for it in reversed(taken_desc) if it is not None]
        if not moving_items:
            return False

        for idx, item in enumerate(moving_items):
            self.insertItem(insert_at + idx, item)

        self.clearSelection()
        for item in moving_items:
            item.setSelected(True)
        if curr_item in moving_items:
            self.setCurrentItem(curr_item)
        else:
            self.setCurrentItem(moving_items[0])

        self.doItemsLayout()
        self.viewport().update()
        self.orderChanged.emit()
        return True

    def dropEvent(self, event):
        pos = self._event_pos(event)
        target_row, _ = self._compute_drop_target(pos)
        self._clear_drop_indicator()

        if self._is_internal_drag(event):
            rows = self._parse_mime_rows(event.mimeData())
            self.move_rows(rows, target_row)
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
            return

        if event.mimeData().hasUrls():
            files = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile() and u.toLocalFile()]
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
