import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

from PyQt6.QtCore import Qt, QMimeData, QPoint, QPointF, QSize, QUrl, QByteArray
from PyQt6.QtGui import QDragEnterEvent, QDragMoveEvent, QDragLeaveEvent, QDropEvent, QIcon, QPixmap, QColor
from PyQt6.QtWidgets import QApplication, QListView, QListWidget, QListWidgetItem

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

from components.drop_list_widget import DropListWidget, INTERNAL_MIME_TYPE
from mixins.playlist.core_mixin import PlaylistCoreMixin
from mixins.ui.playlist_sidebar_ui import PlaylistDropFrame


def _make_item(name: str, color: str) -> QListWidgetItem:
    pm = QPixmap(32, 32)
    pm.fill(QColor(color))
    item = QListWidgetItem(QIcon(pm), name)
    item.setData(Qt.ItemDataRole.UserRole, f"C:/media/{name}")
    item.setSizeHint(QSize(120, 32))
    return item


def _make_internal_mime(rows: list[int]) -> QMimeData:
    mime = QMimeData()
    mime.setData(INTERNAL_MIME_TYPE, QByteArray(",".join(str(r) for r in rows).encode("utf-8")))
    return mime


def _dispatch_internal_drop(widget: DropListWidget, dragged_rows: list[int], drop_pos: QPoint) -> bool:
    mime = _make_internal_mime(dragged_rows)
    widget._dragged_rows = list(dragged_rows)
    pos_f = QPointF(drop_pos)

    enter_ev = QDragEnterEvent(drop_pos, Qt.DropAction.MoveAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    enter_ev.source = lambda: widget
    widget.dragEnterEvent(enter_ev)

    move_ev = QDragMoveEvent(drop_pos, Qt.DropAction.MoveAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    move_ev.source = lambda: widget
    widget.dragMoveEvent(move_ev)

    drop_ev = QDropEvent(pos_f, Qt.DropAction.MoveAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    drop_ev.source = lambda: widget
    widget.dropEvent(drop_ev)
    widget._dragged_rows = []
    return drop_ev.isAccepted()


class TestPlaylistDrop(unittest.TestCase):
    def setUp(self):
        self.list_widget = DropListWidget()
        self.list_widget.resize(260, 400)
        self.names = ["a.mp4", "b.mp4", "c.mp4", "d.mp4"]
        colors = ["#ff0000", "#00ff00", "#0000ff", "#ffff00"]
        for name, color in zip(self.names, colors):
            self.list_widget.addItem(_make_item(name, color))
        self.list_widget.show()
        app.processEvents()

    def tearDown(self):
        self.list_widget.hide()
        self.list_widget.deleteLater()

    def _snapshot(self):
        out = []
        for i in range(self.list_widget.count()):
            it = self.list_widget.item(i)
            out.append((
                it.text(),
                it.data(Qt.ItemDataRole.UserRole),
                it.icon().isNull(),
                it.sizeHint(),
            ))
        return out

    def _texts(self):
        return [self.list_widget.item(i).text() for i in range(self.list_widget.count())]

    def test_start_drag_is_overridden_to_prevent_qt_clear_or_remove(self):
        self.assertIsNot(DropListWidget.startDrag, QListWidget.startDrag)

    def test_drag_drop_flags_persist_across_view_modes(self):
        for mode in (QListView.ViewMode.IconMode, QListView.ViewMode.ListMode):
            self.list_widget.setViewMode(mode)
            self.list_widget.setMovement(QListView.Movement.Static)
            self.assertTrue(self.list_widget.dragEnabled())
            self.assertTrue(self.list_widget.acceptDrops())
            self.assertTrue(self.list_widget.viewport().acceptDrops())
            self.assertEqual(self.list_widget.dragDropMode(), DropListWidget.DragDropMode.DragDrop)
            self.assertEqual(self.list_widget.defaultDropAction(), Qt.DropAction.MoveAction)
            self.assertEqual(self.list_widget.movement(), QListView.Movement.Static)

    def test_list_mode_move_item_up_and_down_preserves_all_items(self):
        self.list_widget.setViewMode(QListView.ViewMode.ListMode)
        self.list_widget.doItemsLayout()
        app.processEvents()

        reordered_signals = []
        self.list_widget.orderChanged.connect(lambda: reordered_signals.append(True))

        # Move row 3 ("d.mp4") above row 1 ("b.mp4") -> upper half of row 1
        r1 = self.list_widget.visualItemRect(self.list_widget.item(1))
        pos_above_1 = QPoint(r1.center().x(), r1.top() + 2)
        accepted = _dispatch_internal_drop(self.list_widget, [3], pos_above_1)
        self.assertTrue(accepted)
        self.assertEqual(self.list_widget.count(), 4)
        self.assertEqual(self._texts(), ["a.mp4", "d.mp4", "b.mp4", "c.mp4"])
        self.assertEqual(len(reordered_signals), 1)

        # Move row 0 ("a.mp4") below row 2 ("b.mp4") -> lower half of row 2
        r2 = self.list_widget.visualItemRect(self.list_widget.item(2))
        pos_below_2 = QPoint(r2.center().x(), r2.bottom() - 2)
        accepted = _dispatch_internal_drop(self.list_widget, [0], pos_below_2)
        self.assertTrue(accepted)
        self.assertEqual(self.list_widget.count(), 4)
        self.assertEqual(self._texts(), ["d.mp4", "b.mp4", "a.mp4", "c.mp4"])
        self.assertEqual(len(reordered_signals), 2)

        # Verify metadata integrity
        for item_text, user_role, icon_is_null, size_hint in self._snapshot():
            self.assertEqual(user_role, f"C:/media/{item_text}")
            self.assertFalse(icon_is_null)
            self.assertEqual(size_hint, QSize(120, 32))

    def test_list_mode_drop_onto_self_or_bottom_empty_area(self):
        self.list_widget.setViewMode(QListView.ViewMode.ListMode)
        self.list_widget.doItemsLayout()
        app.processEvents()

        reordered_signals = []
        self.list_widget.orderChanged.connect(lambda: reordered_signals.append(True))

        # Drop row 1 onto itself (upper half = target 1, lower half = target 2 -> no-op)
        r1 = self.list_widget.visualItemRect(self.list_widget.item(1))
        _dispatch_internal_drop(self.list_widget, [1], QPoint(r1.center().x(), r1.top() + 2))
        self.assertEqual(self._texts(), ["a.mp4", "b.mp4", "c.mp4", "d.mp4"])
        _dispatch_internal_drop(self.list_widget, [1], QPoint(r1.center().x(), r1.bottom() - 2))
        self.assertEqual(self._texts(), ["a.mp4", "b.mp4", "c.mp4", "d.mp4"])
        self.assertEqual(len(reordered_signals), 0)

        # Drop row 0 into empty area below all items -> moves to end
        bottom_pos = QPoint(40, self.list_widget.viewport().height() - 10)
        _dispatch_internal_drop(self.list_widget, [0], bottom_pos)
        self.assertEqual(self._texts(), ["b.mp4", "c.mp4", "d.mp4", "a.mp4"])
        self.assertEqual(len(reordered_signals), 1)

    def test_multi_selection_contiguous_and_non_contiguous_reorder(self):
        self.list_widget.setViewMode(QListView.ViewMode.ListMode)
        self.list_widget.doItemsLayout()
        app.processEvents()

        # Non-contiguous [0, 2] ("a.mp4", "c.mp4") dropped at bottom
        bottom_pos = QPoint(40, self.list_widget.viewport().height() - 10)
        _dispatch_internal_drop(self.list_widget, [0, 2], bottom_pos)
        self.assertEqual(self.list_widget.count(), 4)
        self.assertEqual(self._texts(), ["b.mp4", "d.mp4", "a.mp4", "c.mp4"])

        # Contiguous [2, 3] ("a.mp4", "c.mp4") dropped at very top
        r0 = self.list_widget.visualItemRect(self.list_widget.item(0))
        _dispatch_internal_drop(self.list_widget, [2, 3], QPoint(r0.center().x(), r0.top() + 1))
        self.assertEqual(self.list_widget.count(), 4)
        self.assertEqual(self._texts(), ["a.mp4", "c.mp4", "b.mp4", "d.mp4"])

    def test_icon_mode_grid_drop_left_right_and_empty_space(self):
        self.list_widget.setViewMode(QListView.ViewMode.IconMode)
        self.list_widget.setIconSize(QSize(80, 80))
        self.list_widget.setSpacing(8)
        for i in range(self.list_widget.count()):
            self.list_widget.item(i).setSizeHint(QSize(80, 80))
        self.list_widget.doItemsLayout()
        app.processEvents()

        # Drop row 3 onto left half of row 0 -> inserts at 0
        r0 = self.list_widget.visualItemRect(self.list_widget.item(0))
        _dispatch_internal_drop(self.list_widget, [3], QPoint(r0.left() + 4, r0.center().y()))
        self.assertEqual(self.list_widget.count(), 4)
        self.assertEqual(self._texts(), ["d.mp4", "a.mp4", "b.mp4", "c.mp4"])

        # Drop row 0 onto right half of row 2 -> inserts after row 2
        r2 = self.list_widget.visualItemRect(self.list_widget.item(2))
        _dispatch_internal_drop(self.list_widget, [0], QPoint(r2.right() - 4, r2.center().y()))
        self.assertEqual(self.list_widget.count(), 4)
        self.assertEqual(self._texts(), ["a.mp4", "b.mp4", "d.mp4", "c.mp4"])

        # Drop row 0 into empty bottom space -> moves to end
        _dispatch_internal_drop(self.list_widget, [0], QPoint(200, self.list_widget.viewport().height() - 10))
        self.assertEqual(self.list_widget.count(), 4)
        self.assertEqual(self._texts(), ["b.mp4", "d.mp4", "c.mp4", "a.mp4"])

    def test_drag_leave_does_not_drop_or_lose_items(self):
        self.list_widget._drop_indicator_rect = self.list_widget.viewport().rect()
        self.assertIsNotNone(self.list_widget._drop_indicator_rect)
        self.list_widget.dragLeaveEvent(QDragLeaveEvent())
        self.assertIsNone(self.list_widget._drop_indicator_rect)
        self.assertEqual(self.list_widget.count(), 4)
        self.assertEqual(self._texts(), ["a.mp4", "b.mp4", "c.mp4", "d.mp4"])

    def test_external_url_drop_emits_filesDropped_and_filesDroppedAt(self):
        dropped_batches = []
        dropped_at = []
        self.list_widget.filesDropped.connect(lambda files: dropped_batches.append(files))
        self.list_widget.filesDroppedAt.connect(lambda files, row: dropped_at.append((files, row)))

        r1 = self.list_widget.visualItemRect(self.list_widget.item(1))
        drop_pos = QPointF(r1.center().x(), r1.top() + 2)

        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile("C:/music/song.mp3"), QUrl.fromLocalFile("C:/video/clip.mp4")])
        drop_ev = QDropEvent(drop_pos, Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        self.list_widget.dropEvent(drop_ev)

        self.assertTrue(drop_ev.isAccepted())
        self.assertEqual(dropped_batches, [["C:/music/song.mp3", "C:/video/clip.mp4"]])
        self.assertEqual(dropped_at, [(["C:/music/song.mp3", "C:/video/clip.mp4"], 1)])
        self.assertEqual(self.list_widget.count(), 4)

    def test_playlist_drop_frame_accepts_urls_and_ignores_internal_mime(self):
        frame = PlaylistDropFrame()
        dropped = []
        frame.filesDropped.connect(lambda files: dropped.append(files))

        internal_mime = _make_internal_mime([0])
        enter_internal = QDragEnterEvent(QPoint(10, 10), Qt.DropAction.MoveAction, internal_mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        frame.dragEnterEvent(enter_internal)
        self.assertFalse(enter_internal.isAccepted())

        url_mime = QMimeData()
        url_mime.setUrls([QUrl.fromLocalFile("C:/music/song.mp3")])
        enter_url = QDragEnterEvent(QPoint(10, 10), Qt.DropAction.CopyAction, url_mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        frame.dragEnterEvent(enter_url)
        self.assertTrue(enter_url.isAccepted())

        drop_url = QDropEvent(QPointF(10, 10), Qt.DropAction.CopyAction, url_mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        frame.dropEvent(drop_url)
        self.assertTrue(drop_url.isAccepted())
        self.assertEqual(dropped, [["C:/music/song.mp3"]])
        frame.deleteLater()

    def test_handle_view_drop_accepts_audio_files(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            mp3_path = os.path.join(tmp_dir, "track.mp3")
            txt_path = os.path.join(tmp_dir, "readme.txt")
            with open(mp3_path, "wb") as f:
                f.write(b"dummy")
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write("ignore")

            dummy = PlaylistCoreMixin()
            dummy.currentFilePath = None
            dummy.add_files_to_playlist = MagicMock()
            dummy.load_video = MagicMock()

            dummy.handle_view_drop([mp3_path, txt_path])
            dummy.add_files_to_playlist.assert_called_once_with([mp3_path], insert_row=None)
            dummy.load_video.assert_called_once_with(mp3_path)


if __name__ == "__main__":
    unittest.main()
