"""
TransformMixin — zoom, mirror, rotate, apply_transformations, resize.
"""

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QGraphicsView
from PyQt6.QtGui import QTransform


class TransformMixin:
    # ------------------------------------------------------------------ #
    # Zoom                                                                 #
    # ------------------------------------------------------------------ #

    def update_zoom(self, value):
        snapped = round(value / 20) * 20
        if snapped < 100:
            snapped = 100
        if snapped != value:
            self.zoomSlider.setValue(snapped)
            return
        self.zoomLevel = snapped / 100.0
        factor = self.zoomLevel / self.view.zoomLevel

        self.view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.view.scale(factor, factor)
        self.view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

        self.view.zoomLevel = self.zoomLevel
        self.zoomValueLabel.setText(f"{snapped}%")

    def sync_zoom_ui(self, zoom_level):
        self.zoomLevel = zoom_level
        val = int(zoom_level * 100)
        self._apply_sync_zoom(val)

    def _apply_sync_zoom(self, val):
        self.zoomSlider.blockSignals(True)
        self.zoomSlider.setValue(val)
        self.zoomSlider.setSliderPosition(val)
        self.zoomSlider.blockSignals(False)
        self.zoomValueLabel.setText(f"{val}%")
        self.zoomSlider.update()

    # ------------------------------------------------------------------ #
    # Mirror / rotate                                                      #
    # ------------------------------------------------------------------ #

    def toggle_mirror(self):
        self.isMirrored = not self.isMirrored
        self.apply_transformations(fit=True)
        self.save_current_markers()

    def toggle_vertical_mirror(self):
        self.isMirroredVertical = not self.isMirroredVertical
        self.apply_transformations(fit=True)
        self.save_current_markers()

    def rotate_video(self):
        self.rotate_video_right()

    def rotate_video_right(self):
        self.rotationAngle = (self.rotationAngle + 90) % 360
        self.apply_transformations(fit=True)
        self.save_current_markers()

    def rotate_video_left(self):
        self.rotationAngle = (self.rotationAngle - 90) % 360
        self.apply_transformations(fit=True)
        self.save_current_markers()

    # ------------------------------------------------------------------ #
    # Core transform application                                           #
    # ------------------------------------------------------------------ #

    def apply_transformations(self, fit=False):
        if not hasattr(self, 'pixmapItem') or self.pixmapItem is None:
            return

        pix = self.pixmapItem.pixmap()
        if pix.isNull():
            return

        cx = pix.width() / 2.0
        cy = pix.height() / 2.0

        transform = QTransform()
        transform.translate(cx, cy)

        if self.isMirrored:
            transform.scale(-1, 1)
        if self.isMirroredVertical:
            transform.scale(1, -1)

        if self.rotationAngle != 0:
            transform.rotate(self.rotationAngle)

        transform.translate(-cx, -cy)

        if not hasattr(self, 'last_applied_transform') or self.last_applied_transform != transform:
            self.pixmapItem.setTransform(transform)
            self.last_applied_transform = transform

        if hasattr(self, 'view') and self.view:
            current_state = (
                pix.width(), pix.height(),
                self.rotationAngle, self.isMirrored, self.isMirroredVertical
            )
            if current_state != self.last_transform_state:
                self.last_transform_state = current_state
                max_dim = max(pix.width(), pix.height()) * 2
                self.view.setSceneRect(-max_dim, -max_dim, max_dim * 4, max_dim * 4)

            if fit:
                self.view.fitInView(self.pixmapItem, Qt.AspectRatioMode.KeepAspectRatio)
                self.view.zoomLevel = 1.0
                self.sync_zoom_ui(1.0)

            self.update_loading_overlay_geometry()

    def update_loading_overlay_geometry(self):
        if not hasattr(self, 'loadingOverlay') or not self.loadingOverlay:
            return
        if not self.loadingOverlay.isVisible():
            return
        if not hasattr(self, 'view') or not self.view:
            return

        from PyQt6.QtCore import QRect
        geom = QRect(0, 0, self.view.width(), self.view.height())

        if hasattr(self, 'pixmapItem') and self.pixmapItem:
            pix = self.pixmapItem.pixmap()
            if pix and not pix.isNull():
                scene_rect = self.pixmapItem.sceneBoundingRect()
                viewport_rect = self.view.mapFromScene(scene_rect).boundingRect()
                if viewport_rect.isValid() and viewport_rect.width() > 0 and viewport_rect.height() > 0:
                    geom = viewport_rect

        self.loadingOverlay.setGeometry(geom)

        text_len = max(len(self.loadingOverlay.text()), 1)
        font = self.loadingOverlay.font()
        font_size = min(24, max(12, int(geom.width() / (text_len * 0.6))))
        font.setPixelSize(font_size)
        self.loadingOverlay.setFont(font)

    # ------------------------------------------------------------------ #
    # Resize event                                                         #
    # ------------------------------------------------------------------ #

    def resizeEvent(self, event):
        super().resizeEvent(event)
        
        if (hasattr(self, 'pixmapItem') and self.view
                and getattr(self, 'zoomLevel', 1.0) == 1.0):
            self.view.fitInView(self.pixmapItem, Qt.AspectRatioMode.KeepAspectRatio)

        self.update_loading_overlay_geometry()
