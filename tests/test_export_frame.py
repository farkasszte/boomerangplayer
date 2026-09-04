import unittest
from PyQt6.QtWidgets import QApplication, QGraphicsScene
from PyQt6.QtGui import QImage, QColor, QPainter, QTransform, QPixmap, QPen
from PyQt6.QtCore import QRectF, QPointF, QLineF
import sys

# Ensure QApplication exists
app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)


class TestExportFrameRotation(unittest.TestCase):
    def setUp(self):
        # Create a test image with distinct quadrant colors (200w x 100h)
        # Top-Left: Red, Top-Right: Green, Bottom-Left: Blue, Bottom-Right: Yellow
        self.img = QImage(200, 100, QImage.Format.Format_ARGB32)
        p = QPainter(self.img)
        p.fillRect(0, 0, 100, 50, QColor(255, 0, 0))      # TL Red
        p.fillRect(100, 0, 100, 50, QColor(0, 255, 0))    # TR Green
        p.fillRect(0, 50, 100, 50, QColor(0, 0, 255))     # BL Blue
        p.fillRect(100, 50, 100, 50, QColor(255, 255, 0)) # BR Yellow
        p.end()

    def test_direct_transform_rotation_90(self):
        t = QTransform()
        t.rotate(90)
        rotated = self.img.transformed(t)
        self.assertEqual(rotated.width(), 100)
        self.assertEqual(rotated.height(), 200)

        # In 90-degree clockwise rotation:
        # Original TL (Red) moves to TR
        # Original TR (Green) moves to BR
        # Original BL (Blue) moves to TL
        # Original BR (Yellow) moves to BL
        tl_color = rotated.pixelColor(25, 25)
        tr_color = rotated.pixelColor(75, 25)
        self.assertEqual(tl_color.blue(), 255)  # Blue at TL
        self.assertEqual(tr_color.red(), 255)   # Red at TR

    def test_scene_render_rotation_90_with_drawings(self):
        from components.gpu_pixmap_item import GPUPixmapItem
        scene = QGraphicsScene()
        pixmap_item = GPUPixmapItem()
        pixmap_item.setPixmap(QPixmap.fromImage(self.img))
        scene.addItem(pixmap_item)

        # Rotate 90 deg around center (identical to TransformMixin)
        cx = self.img.width() / 2.0
        cy = self.img.height() / 2.0
        transform = QTransform()
        transform.translate(cx, cy)
        transform.rotate(90)
        transform.translate(-cx, -cy)
        pixmap_item.setTransform(transform)

        # Add a drawing stroke on the scene
        from PyQt6.QtWidgets import QGraphicsLineItem
        drawing = QGraphicsLineItem(QLineF(50, 0, 60, 10))
        drawing.setPen(QPen(QColor(255, 255, 255), 4))
        scene.addItem(drawing)

        # Test the ExportFrameMixin logic using sceneBoundingRect
        scene_rect = pixmap_item.sceneBoundingRect()
        out_w = max(1, int(round(scene_rect.width())))
        out_h = max(1, int(round(scene_rect.height())))
        self.assertEqual(out_w, 100)
        self.assertEqual(out_h, 200)

        out_pixmap = QPixmap(out_w, out_h)
        out_pixmap.fill(QColor(0, 0, 0))
        painter = QPainter(out_pixmap)
        scene.render(painter, QRectF(0, 0, out_w, out_h), scene_rect)
        painter.end()

        final_img = out_pixmap.toImage()
        self.assertEqual(final_img.width(), 100)
        self.assertEqual(final_img.height(), 200)

        # Verify pixel colors match expected rotated orientation (not cropped or cut off)
        tl_color = final_img.pixelColor(25, 25)
        tr_color = final_img.pixelColor(75, 25)
        self.assertEqual(tl_color.blue(), 255)
        self.assertEqual(tr_color.red(), 255)


if __name__ == '__main__':
    unittest.main()
