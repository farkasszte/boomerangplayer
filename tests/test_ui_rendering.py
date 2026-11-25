import unittest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QPaintEvent
import sys

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

from player_window import PlayerWindow
from mixins.ui_mixin import PlayerInterface


class TestUIRendering(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.win = PlayerWindow()

    def test_player_interface_attributes(self):
        pi = self.win.playerInterface
        self.assertIsInstance(pi, PlayerInterface)
        self.assertTrue(pi.testAttribute(Qt.WidgetAttribute.WA_StyledBackground))
        self.assertTrue(pi.testAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent))
        self.assertTrue(pi.autoFillBackground())

    def test_player_interface_paint_event(self):
        pi = self.win.playerInterface
        event = QPaintEvent(QRect(0, 0, 100, 100))
        # Ensure paintEvent executes cleanly without error
        try:
            pi.paintEvent(event)
        except Exception as e:
            self.fail(f"paintEvent raised exception: {e}")

    def test_controls_card_attributes(self):
        cc = self.win.controlsCard
        self.assertTrue(cc.testAttribute(Qt.WidgetAttribute.WA_StyledBackground))
        self.assertTrue(cc.autoFillBackground())

    def test_stacked_widget_attributes(self):
        sw = self.win.stackedWidget
        self.assertTrue(sw.testAttribute(Qt.WidgetAttribute.WA_StyledBackground))
        self.assertTrue(sw.autoFillBackground())

    def test_update_pixmap_from_cache(self):
        from PyQt6.QtGui import QImage
        from PyQt6.QtCore import QByteArray, QBuffer, QIODevice
        
        test_img = QImage(64, 64, QImage.Format.Format_RGB32)
        test_img.fill(0xFF00FF)
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        test_img.save(buf, "JPEG")
        buf.close()
        
        self.win.frame_cache = {0: bytes(ba)}
        self.win.current_frame_index = 0
        
        orig_gpu = self.win.config.get('gpu_acceleration', True)
        try:
            for gpu_flag in (True, False):
                self.win.config['gpu_acceleration'] = gpu_flag
                self.win.update_pixmap_from_cache()
        finally:
            self.win.config['gpu_acceleration'] = orig_gpu
            self.win.config.flush()

    def test_frameless_margins_and_opaque_background(self):
        self.assertFalse(self.win.isMicaEffectEnabled())
        self.assertEqual(self.win._normalBackgroundColor().alpha(), 255)
        self.assertFalse(self.win.playlistContainer.isHidden())
        if sys.platform == 'win32':
            self.assertTrue(bool(self.win.windowFlags() & Qt.WindowType.FramelessWindowHint))
            self.win.show()
            app.processEvents()
            margins = self.win.windowHandle().frameMargins()
            self.assertEqual((margins.left(), margins.top(), margins.right(), margins.bottom()), (0, 0, 0, 0))
            self.assertEqual(self.win.geometry(), self.win.frameGeometry())
            self.win.refresh_window_frame()
            app.processEvents()
            self.assertEqual(self.win.geometry(), self.win.frameGeometry())
            self.win.hide()

    def test_dialogs_do_not_create_native_child_siblings(self):
        from PyQt6.QtWidgets import QMessageBox
        from mixins.file_dialog import MediaFileDialog

        self.assertTrue(app.testAttribute(Qt.ApplicationAttribute.AA_DontCreateNativeWidgetSiblings))
        self.assertTrue(self.win.testAttribute(Qt.WidgetAttribute.WA_DontCreateNativeAncestors))

        # Test delete confirmation dialog (QMessageBox + style_dialog)
        box = QMessageBox(self.win)
        self.win.style_dialog(box)
        self.assertTrue(box.testAttribute(Qt.WidgetAttribute.WA_DontCreateNativeAncestors))
        self.assertFalse(self.win.stackedWidget.testAttribute(Qt.WidgetAttribute.WA_NativeWindow))
        self.assertIsNone(self.win.stackedWidget.windowHandle())
        self.assertFalse(self.win.titleBar.testAttribute(Qt.WidgetAttribute.WA_NativeWindow))
        self.assertIsNone(self.win.titleBar.windowHandle())
        box.deleteLater()

        # Test open media dialog (MediaFileDialog)
        dlg = MediaFileDialog(self.win, self.win.config)
        self.assertTrue(dlg.testAttribute(Qt.WidgetAttribute.WA_DontCreateNativeAncestors))
        self.assertFalse(self.win.stackedWidget.testAttribute(Qt.WidgetAttribute.WA_NativeWindow))
        self.assertIsNone(self.win.stackedWidget.windowHandle())
        self.assertFalse(self.win.titleBar.testAttribute(Qt.WidgetAttribute.WA_NativeWindow))
        self.assertIsNone(self.win.titleBar.windowHandle())
        dlg.deleteLater()

    def test_gpu_pixmap_item_hidpi_projection_bounds(self):
        from PyQt6.QtGui import QImage, QMatrix4x4, QVector4D

        img = QImage(1920, 1080, QImage.Format.Format_RGB32)
        self.win.pixmapItem.setImage(img)
        self.win.apply_transformations(fit=True)

        viewport = self.win.view.viewport()
        world_matrix = QMatrix4x4(self.win.pixmapItem.sceneTransform() * self.win.view.viewportTransform())
        proj = QMatrix4x4()
        proj.ortho(0, viewport.width(), viewport.height(), 0, -1, 1)
        mvp = proj * world_matrix

        tl_ndc = mvp.map(QVector4D(0.0, 0.0, 0.0, 1.0))
        br_ndc = mvp.map(QVector4D(1920.0, 1080.0, 0.0, 1.0))

        self.assertGreaterEqual(tl_ndc.x(), -1.01)
        self.assertLessEqual(tl_ndc.y(), 1.01)
        self.assertLessEqual(br_ndc.x(), 1.01)
        self.assertGreaterEqual(br_ndc.y(), -1.01)

    def test_playlist_drag_drop_and_manual_reorder(self):
        from PyQt6.QtWidgets import QListWidgetItem

        pl = self.win.playlistList
        self.assertTrue(self.win.playlistContainer.acceptDrops())
        self.assertTrue(pl.acceptDrops())
        self.assertTrue(pl.viewport().acceptDrops())
        self.assertTrue(pl.dragEnabled())

        # Ensure layout mode changes never disable drag & drop
        self.win.update_playlist_layout(force_reload_thumbs=False)
        self.assertTrue(pl.acceptDrops())
        self.assertTrue(pl.viewport().acceptDrops())
        self.assertTrue(pl.dragEnabled())

        pl.clear()
        for name in ["a.mp4", "b.mp4", "c.mp4", "d.mp4"]:
            it = QListWidgetItem(name)
            it.setData(Qt.ItemDataRole.UserRole, name)
            pl.addItem(it)

        # Move index 0 ("a.mp4") after index 2 ("c.mp4") -> target_row = 3
        pl.move_rows([0], 3)
        order = [pl.item(i).data(Qt.ItemDataRole.UserRole) for i in range(pl.count())]
        self.assertEqual(order, ["b.mp4", "c.mp4", "a.mp4", "d.mp4"])

        # Move index 3 ("d.mp4") to the top -> target_row = 0
        pl.move_rows([3], 0)
        order = [pl.item(i).data(Qt.ItemDataRole.UserRole) for i in range(pl.count())]
        self.assertEqual(order, ["d.mp4", "b.mp4", "c.mp4", "a.mp4"])

        # Multi-select move: move indices [0, 2] ("d.mp4", "c.mp4") to end -> target_row = 4
        pl.move_rows([0, 2], 4)
        order = [pl.item(i).data(Qt.ItemDataRole.UserRole) for i in range(pl.count())]
        self.assertEqual(order, ["b.mp4", "a.mp4", "d.mp4", "c.mp4"])
        pl.clear()


if __name__ == '__main__':
    unittest.main()
