import os
import json
import tempfile
import shutil
import glob
import subprocess
from PyQt6.QtCore import Qt, QUrl, QTimer, QRectF, QSizeF, QSize, QElapsedTimer, pyqtSignal, QThread
from PyQt6.QtGui import QIcon, QTransform, QPainter, QPen, QColor, QImage, QPixmap
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFileDialog, 
                             QGraphicsView, QGraphicsScene, QSlider, QFrame, QListWidgetItem, QSplitter, QGraphicsPixmapItem, QLabel)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaMetaData, QVideoSink
from PyQt6.QtMultimediaWidgets import QVideoWidget, QGraphicsVideoItem

from qfluentwidgets import (FluentWindow, SubtitleLabel, PushButton, 
                            Slider, FluentIcon, ToolButton, BodyLabel,
                            CardWidget, PrimaryPushButton, CaptionLabel,
                            SwitchButton, ComboBox, ListWidget)

import sys

def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class DropListWidget(ListWidget):
    filesDropped = pyqtSignal(list)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        
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
            files = []
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    files.append(url.toLocalFile())
            if files:
                self.filesDropped.emit(files)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

class FrameExtractionThread(QThread):
    finished_extraction = pyqtSignal(list, str)
    
    def __init__(self, video_path, parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self.temp_dir = tempfile.mkdtemp(prefix="boomerang_frames_")
        self.process = None
        self._is_cancelled = False
        
    def run(self):
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            ffmpeg_path = os.path.join(base_dir, "ffmpeg.exe" if os.name == 'nt' else "ffmpeg")
            if not os.path.exists(ffmpeg_path):
                ffmpeg_path = "ffmpeg"
                
            out_pattern = os.path.join(self.temp_dir, "frame_%04d.jpg")
            
            cmd = [
                ffmpeg_path, "-y",
                "-i", self.video_path,
                "-q:v", "2", 
                out_pattern
            ]
            
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            self.process = subprocess.Popen(cmd, creationflags=creationflags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.process.wait()
            
            if self._is_cancelled:
                self.finished_extraction.emit([], self.temp_dir)
                return
            
            frame_files = sorted(glob.glob(os.path.join(self.temp_dir, "frame_*.jpg")))
            self.finished_extraction.emit(frame_files, self.temp_dir)
        except Exception as e:
            print(f"Extraction error: {e}")
            self.finished_extraction.emit([], self.temp_dir)

    def cancel(self):
        self._is_cancelled = True
        if self.process:
            try:
                self.process.kill()
            except:
                pass

FLUENT_SLIDER_STYLE = """
QSlider::groove:horizontal {
    border: none;
    height: 4px;
    background: #444;
    margin: 2px 0;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #ffffff;
    width: 2px;
    height: 16px;
    margin: -6px 0;
}
QSlider::handle:horizontal:hover {
    background: #ffffff;
}
QSlider::sub-page:horizontal {
    background: #00f2ff;
    border-radius: 2px;
}
"""

class ThumbnailThread(QThread):
    finished = pyqtSignal(str, QPixmap)

    def __init__(self, filePath, parent=None):
        super().__init__(parent)
        self.filePath = filePath

    def run(self):
        try:
            # Create a unique temp name for thumbnail
            import tempfile
            temp_dir = tempfile.gettempdir()
            thumb_name = f"thumb_{hash(self.filePath)}.jpg"
            thumb_path = os.path.join(temp_dir, thumb_name)
            
            # Use helper to find ffmpeg
            ffmpeg_path = get_resource_path("ffmpeg.exe" if os.name == 'nt' else "ffmpeg")
            if not os.path.exists(ffmpeg_path):
                ffmpeg_path = "ffmpeg"

            cmd = [
                ffmpeg_path, "-y",
                "-ss", "0.5",
                "-i", self.filePath,
                "-vframes", "1",
                "-vf", "setsar=1,scale=120:120:force_original_aspect_ratio=decrease,pad=120:120:(ow-iw)/2:(oh-ih)/2",
                thumb_path
            ]
            
            creationflags = 0
            if os.name == 'nt':
                creationflags = subprocess.CREATE_NO_WINDOW
                
            process = subprocess.Popen(cmd, creationflags=creationflags)
            process.wait()
            
            if os.path.exists(thumb_path):
                pixmap = QPixmap(thumb_path)
                self.finished.emit(self.filePath, pixmap)
                # Cleanup temp file
                try: os.remove(thumb_path)
                except: pass
        except Exception as e:
            print(f"Thumbnail error: {e}")

class MarkerSlider(QSlider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.loopStartFrame = 0
        self.loopEndFrame = 0
        
    def update_markers(self, start_frame, end_frame):
        self.loopStartFrame = start_frame
        self.loopEndFrame = end_frame
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.maximum() <= 0:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Calculate positions using frame indices
        w = self.width()
        start_x = int((self.loopStartFrame / self.maximum()) * w)
        end_x = int((self.loopEndFrame / self.maximum()) * w)
        
        # Draw markers
        pen = QPen(QColor(0, 153, 255)) # Fluent blue
        pen.setWidth(2)
        painter.setPen(pen)
        
        if self.loopStartFrame > 0:
            painter.drawLine(start_x, 0, start_x, self.height())
        if self.loopEndFrame > 0 and self.loopEndFrame < self.maximum():
            painter.drawLine(end_x, 0, end_x, self.height())

class ZoomView(QGraphicsView):
    zoomChanged = pyqtSignal(float)

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.zoomLevel = 1.0

    def get_scroll_state(self):
        return (self.horizontalScrollBar().value(), self.verticalScrollBar().value())
    
    def set_scroll_state(self, x, y):
        # We need a small delay to ensure the scene is properly sized before restoring scroll
        QTimer.singleShot(50, lambda: self._apply_scroll(x, y))

    def _apply_scroll(self, x, y):
        self.horizontalScrollBar().setValue(x)
        self.verticalScrollBar().setValue(y)

    def wheelEvent(self, event):
        # Zoom factor
        factor = 1.1 if event.angleDelta().y() > 0 else 1/1.1
        new_zoom = self.zoomLevel * factor
        
        # Limit zoom
        if 1.0 <= new_zoom <= 10.0:
            self.zoomLevel = new_zoom
            self.scale(factor, factor)
            self.zoomChanged.emit(self.zoomLevel)
        elif new_zoom < 1.0:
            # Snap to 1.0
            factor = 1.0 / self.zoomLevel
            self.zoomLevel = 1.0
            self.scale(factor, factor)
            self.zoomChanged.emit(self.zoomLevel)

class PlayerWindow(FluentWindow):
    def __init__(self):
        # Initialize attributes BEFORE super().__init__() because it triggers resize events
        self.videoItem = None
        self.view = None
        
        from qfluentwidgets import setTheme, Theme
        setTheme(Theme.DARK)
        
        super().__init__()
        self.titleBar.setFixedHeight(32) # Compact header
        self.setContentsMargins(0, 0, 0, 0)
        
        # FluentWindow hardcodes widgetLayout top margin to 48px (for its default title bar).
        # Override it to match our 32px title bar so content starts right below it.
        self.widgetLayout.setContentsMargins(0, 32, 0, 0)

        # Center title in FluentTitleBar
        self.titleBar.hBoxLayout.insertStretch(1, 1)
        self.titleBar.hBoxLayout.insertStretch(3, 1)
        self.titleBar.titleLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # State
        self.currentFilePath = None
        self.playlistData = {} # {path: {'start': 0, 'end': 0, 'loopMode': 0}}
        self.isPingPong = True
        self.isForward = True
        self.zoomLevel = 1.0
        self.loopStartFrame = 0
        self.loopEndFrame = 0
        self.fps = 30.0 # Default fallback
        self.userMutedIntent = False
        
        # Initialize Media Player
        self.mediaPlayer = QMediaPlayer()
        self.audioOutput = QAudioOutput()
        self.mediaPlayer.setAudioOutput(self.audioOutput)
        
        # UI Setup
        self.init_ui()
        
        # Connections
        self.mediaPlayer.durationChanged.connect(self.update_duration)
        self.mediaPlayer.playbackStateChanged.connect(self.handle_state_change)
        self.mediaPlayer.mediaStatusChanged.connect(self.handle_status_change)
        self.mediaPlayer.metaDataChanged.connect(self.handle_metadata_change)
        
        # Cache and playback variables
        self.cached_frame_files = []
        self.current_temp_dir = None
        self.extraction_thread = None
        self.cached_file_path = None
        self.current_cache_index = 0
        self.is_playing = False
        self.is_scrubbing = False
        
        # Master playback timer and elapsed time tracking
        self.playbackTimer = QTimer()
        self.playbackTimer.setTimerType(Qt.TimerType.PreciseTimer)
        self.playbackTimer.timeout.connect(self.advance_frame)
        self.elapsedTimer = QElapsedTimer()
        self.last_advance_ms = 0
        
        # Connect to size changes for reliable fitting
        self.videoSink = QVideoSink()
        self.mediaPlayer.setVideoSink(self.videoSink)
        self.videoSink.videoSizeChanged.connect(self.handle_size_change)
            
    def cleanup_cache(self):
        if self.current_temp_dir and os.path.exists(self.current_temp_dir):
            try:
                shutil.rmtree(self.current_temp_dir, ignore_errors=True)
            except:
                pass
        self.current_temp_dir = None
        self.cached_frame_files = []
        if hasattr(self, 'pixmapItem'):
            self.pixmapItem.setPixmap(QPixmap())


    def start_full_extraction(self):
        if not self.currentFilePath:
            return
            
        # Check if already cached for this exact file
        if self.cached_frame_files and getattr(self, 'cached_file_path', None) == self.currentFilePath:
            print(f"Skipping extraction, already cached: {self.currentFilePath}")
            self.loadingOverlay.hide()
            return
            
        if self.extraction_thread and self.extraction_thread.isRunning():
            self.extraction_thread.cancel()
            
        self.cleanup_cache()
        self.loadingOverlay.show()
        
        self.extraction_thread = FrameExtractionThread(self.currentFilePath, self)
        self.extraction_thread.finished_extraction.connect(self.on_extraction_finished)
        self.extraction_thread.start()

    def on_extraction_finished(self, frame_files, temp_dir):
        if not frame_files:
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except:
                pass
            self.loadingOverlay.hide()
            return
            
        self.cached_frame_files = frame_files
        self.cached_file_path = self.currentFilePath
        self.current_temp_dir = temp_dir
        self.loadingOverlay.hide()
        print(f"Full RAM Preview cached {len(frame_files)} frames.")
        
        self.update_pixmap_from_cache()

    def closeEvent(self, event):
        self.cleanup_cache()
        super().closeEvent(event)

    def advance_frame(self):
        if not self.cached_frame_files or self.fps <= 0:
            return
            
        # Calculate how many frames to advance based on real elapsed time
        current_ms = self.elapsedTimer.elapsed()
        delta_ms = current_ms - self.last_advance_ms
        self.last_advance_ms = current_ms
        
        # Don't advance more than 100ms in one tick to avoid huge jumps
        delta_ms = min(delta_ms, 100) 
        
        rate = self.speedSlider.value() / 100.0
        frames_to_advance = (delta_ms * self.fps * rate) / 1000.0
        
        # We accumulate fractional frames
        if not hasattr(self, 'frame_accumulator'):
            self.frame_accumulator = 0.0
        self.frame_accumulator += frames_to_advance
        
        int_delta = int(self.frame_accumulator)
        if int_delta < 1:
            return # Not enough time passed for a new frame
            
        self.frame_accumulator -= int_delta
        
        # Get loop points (frames)
        loop_mode = self.loopCombo.currentIndex()
        if loop_mode == 0: # None
            start_frame = 0
            end_frame = self.progressBar.maximum()
        else:
            start_frame = self.loopStartFrame
            end_frame = self.loopEndFrame if self.loopEndFrame > 0 else self.progressBar.maximum()
            
        if start_frame > end_frame:
            start_frame, end_frame = end_frame, start_frame

        if self.isForward:
            self.current_cache_index += int_delta
            if self.current_cache_index > end_frame:
                if loop_mode in (1, 2): # Standard Loop
                    self.current_cache_index = start_frame + (self.current_cache_index - end_frame - 1)
                    if self.fps > 0:
                        self.mediaPlayer.setPosition(int(self.current_cache_index * 1000 / self.fps))
                    if loop_mode == 2:
                        self.isForward = False
                elif loop_mode == 3: # Ping-pong
                    self.isForward = False
                    self.current_cache_index = end_frame - (self.current_cache_index - end_frame)
                    self.audioOutput.setMuted(True)
                else:
                    self.current_cache_index = end_frame
                    self.stop_playback()
        else:
            self.current_cache_index -= int_delta
            if self.current_cache_index < start_frame:
                if loop_mode == 3: # Ping-pong
                    self.isForward = True
                    self.current_cache_index = start_frame + (start_frame - self.current_cache_index)
                    self.audioOutput.setMuted(self.userMutedIntent)
                    if self.fps > 0:
                        self.mediaPlayer.setPosition(int(self.current_cache_index * 1000 / self.fps))
                elif loop_mode == 2: # Backward loop
                    self.current_cache_index = end_frame - (start_frame - self.current_cache_index - 1)
                else:
                    self.current_cache_index = start_frame
                    self.stop_playback()
                    
        # Clamp final index
        self.current_cache_index = max(0, min(len(self.cached_frame_files) - 1, self.current_cache_index))
        self.update_pixmap_from_cache()

    def update_pixmap_from_cache(self):
        if self.current_cache_index < 0 or self.current_cache_index >= len(self.cached_frame_files):
            return
            
        # Update slider to reflect current frame index
        if not self.is_scrubbing:
            self.progressBar.blockSignals(True)
            self.progressBar.setValue(self.current_cache_index)
            self.progressBar.blockSignals(False)
            
        frame_path = self.cached_frame_files[self.current_cache_index]
        if not os.path.exists(frame_path):
            return # Still extracting or missing
            
        img = QImage(frame_path)
        if not img.isNull():
            self.pixmapItem.setPixmap(QPixmap.fromImage(img))
            
        if self.fps > 0:
            pos = int((self.current_cache_index * 1000) / self.fps)
            self.currentTimeLabel.setText(self.format_time(pos))
            self.frameLabel.setText(f" [F: {self.current_cache_index}]")
            
    def handle_size_change(self):
        sink = self.mediaPlayer.videoSink()
        if sink and self.view:
            size = sink.videoSize()
            if not size.isEmpty():
                self.view.setSceneRect(QRectF(0, 0, size.width(), size.height()))
                if getattr(self.view, 'zoomLevel', 1.0) == 1.0:
                    self.view.fitInView(self.pixmapItem, Qt.AspectRatioMode.KeepAspectRatio)
    def init_ui(self):
        # --- Main Interface ---
        self.playerInterface = QWidget()
        self.playerLayout = QVBoxLayout(self.playerInterface)
        self.playerLayout.setContentsMargins(0, 0, 0, 0)
        self.playerLayout.setSpacing(0)
        
        # Splitter for Video + Playlist
        self.mainSplitter = QSplitter(Qt.Orientation.Horizontal)
        self.mainSplitter.setHandleWidth(1)
        self.mainSplitter.setStyleSheet("QSplitter::handle { background: #333; }")
        
        self.scene = QGraphicsScene()
        self.view = ZoomView(self.scene, self.playerInterface)
        self.view.zoomChanged.connect(self.sync_zoom_ui)
        self.view.setStyleSheet("border: none; background: black;")
        
        # Playlist Sidebar
        self.playlistContainer = QFrame()
        self.playlistContainer.setMinimumWidth(180)
        self.playlistContainer.setStyleSheet("background: #202020; border-left: 1px solid #333;")
        self.playlistLayout = QVBoxLayout(self.playlistContainer)
        self.playlistLayout.setContentsMargins(5, 5, 5, 5)
        
        self.playlistLabel = CaptionLabel("Playlist")
        self.playlistList = DropListWidget()
        self.playlistList.setIconSize(QSize(120, 120))
        self.playlistList.itemDoubleClicked.connect(self.on_playlist_item_clicked)
        self.playlistList.filesDropped.connect(self.add_files_to_playlist)
        self.playlistLayout.addWidget(self.playlistList)
        
        self.thumb_threads = []
        
        self.playlistButtonsLayout = QHBoxLayout()
        self.addFileButton = ToolButton(FluentIcon.ADD)
        self.addFileButton.setToolTip("Add video")
        self.addFileButton.clicked.connect(self.open_file)
        
        self.savePlaylistButton = ToolButton(FluentIcon.SAVE)
        self.savePlaylistButton.setToolTip("Save Playlist")
        self.savePlaylistButton.clicked.connect(self.save_playlist_to_file)
        
        self.loadPlaylistButton = ToolButton(FluentIcon.FOLDER)
        self.loadPlaylistButton.setToolTip("Load Playlist")
        self.loadPlaylistButton.clicked.connect(self.load_playlist_from_file)
        
        self.removeFileButton = ToolButton(FluentIcon.DELETE)
        self.removeFileButton.setToolTip("Remove selected")
        self.removeFileButton.clicked.connect(self.remove_from_playlist)
        
        self.playlistButtonsLayout.addWidget(self.addFileButton)
        self.playlistButtonsLayout.addWidget(self.savePlaylistButton)
        self.playlistButtonsLayout.addWidget(self.loadPlaylistButton)
        self.playlistButtonsLayout.addWidget(self.removeFileButton)
        self.playlistButtonsLayout.addStretch(1)
        
        self.playlistLayout.addWidget(self.playlistLabel)
        self.playlistLayout.addWidget(self.playlistList)
        self.playlistLayout.addLayout(self.playlistButtonsLayout)
        
        self.mainSplitter.addWidget(self.view)
        self.mainSplitter.addWidget(self.playlistContainer)
        self.mainSplitter.setStretchFactor(0, 1)
        
        self.playerLayout.addWidget(self.mainSplitter, stretch=1)
        
        self.pixmapItem = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmapItem)
        
        # Overlay for loading
        self.loadingOverlay = QLabel("Caching RAM Preview...", self.view)
        self.loadingOverlay.setStyleSheet("background: rgba(0,0,0,180); color: white; font-size: 24px; font-weight: bold; border-radius: 10px;")
        self.loadingOverlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loadingOverlay.hide()
        
        # Controls Container
        self.controlsCard = CardWidget()
        self.controlsLayout = QVBoxLayout(self.controlsCard)
        self.controlsLayout.setContentsMargins(12, 12, 12, 12)
        
        # Progress Bar Row
        self.progressLayout = QHBoxLayout()
        self.currentTimeLabel = CaptionLabel("00:00")
        self.frameLabel = CaptionLabel(" [F: 0]")
        self.progressBar = MarkerSlider(Qt.Orientation.Horizontal)
        self.progressBar.setStyleSheet(FLUENT_SLIDER_STYLE)
        self.progressBar.setRange(0, 0)
        self.progressBar.sliderMoved.connect(self.set_position)
        self.progressBar.sliderReleased.connect(self.on_slider_released)
        self.progressBar.sliderPressed.connect(self.on_slider_pressed)
        self.totalTimeLabel = CaptionLabel("00:00")
        
        self.progressLayout.addWidget(self.currentTimeLabel)
        self.progressLayout.addWidget(self.frameLabel)
        self.progressLayout.addWidget(self.progressBar)
        self.progressLayout.addWidget(self.totalTimeLabel)
        self.controlsLayout.addLayout(self.progressLayout)
        
        # Buttons Row
        self.buttonsLayout = QHBoxLayout()
        
        # Left side: File operations
        self.openButton = ToolButton(FluentIcon.FOLDER)
        self.openButton.clicked.connect(self.open_file)
        self.buttonsLayout.addWidget(self.openButton)
        
        self.buttonsLayout.addSpacing(20)
        
        # Center: Playback controls
        self.buttonsLayout.addStretch(1)
        
        self.stepBackButton = ToolButton(FluentIcon.LEFT_ARROW)
        self.stepBackButton.setToolTip("Előző képkocka")
        self.stepBackButton.clicked.connect(lambda: self.step_frame(-1))
        
        self.playButton = ToolButton(FluentIcon.PLAY)
        self.playButton.clicked.connect(self.play_pause)
        
        self.stepForwardButton = ToolButton(FluentIcon.RIGHT_ARROW)
        self.stepForwardButton.setToolTip("Következő képkocka")
        self.stepForwardButton.clicked.connect(lambda: self.step_frame(1))
        
        self.stopButton = ToolButton(FluentIcon.CLOSE)
        self.stopButton.clicked.connect(self.stop_playback)
        
        self.buttonsLayout.addWidget(self.stepBackButton)
        self.buttonsLayout.addWidget(self.playButton)
        self.buttonsLayout.addWidget(self.stepForwardButton)
        self.buttonsLayout.addWidget(self.stopButton)
        self.buttonsLayout.addStretch(1)
        
        # Right side: Settings & Volume
        # Speed Slider
        self.speedLabel = CaptionLabel("Speed")
        self.speedValueLabel = CaptionLabel("100%")
        self.speedValueLabel.setFixedWidth(40)
        self.speedSlider = QSlider(Qt.Orientation.Horizontal)
        self.speedSlider.setRange(5, 200)  # 5% to 200%
        self.speedSlider.setSingleStep(5)   # 5% steps
        self.speedSlider.setPageStep(5)
        self.speedSlider.setValue(100)       # Default: 100% = 1.0x
        self.speedSlider.setFixedWidth(120)
        self.speedSlider.setStyleSheet(FLUENT_SLIDER_STYLE)
        self.speedSlider.valueChanged.connect(self.on_speed_slider_changed)
        self.speedSlider.setToolTip("Playback Speed")
        
        self.buttonsLayout.addWidget(self.speedLabel)
        self.buttonsLayout.addWidget(self.speedSlider)
        self.buttonsLayout.addWidget(self.speedValueLabel)
        
        self.buttonsLayout.addSpacing(10)
        
        # Loop Modes & Markers
        self.loopLabel = CaptionLabel("Loop")
        from PyQt6.QtWidgets import QComboBox
        self.loopCombo = QComboBox()
        self.loopCombo.addItems(["None", "Forward", "Backward", "Ping-Pong"])
        self.loopCombo.setCurrentIndex(3)
        self.loopCombo.currentIndexChanged.connect(self.on_loop_mode_changed)
        self.loopCombo.setFixedWidth(100)
        
        self.globalLoopToggle = SwitchButton()
        self.globalLoopToggle.setChecked(True)
        self.globalLoopToggle.setOnText("Global")
        self.globalLoopToggle.setOffText("Global")
        self.globalLoopToggle.setText("Global")
        self.globalLoopToggle.setToolTip("Apply loop mode to all videos")
        
        self.loopFramesLabel = CaptionLabel("[F: 0 - End]")
        self.loopFramesLabel.setStyleSheet("color: #888;")
        
        self.setStartButton = ToolButton()
        self.setStartButton.setText("[")
        self.setStartButton.setToolTip("Loop kezdete")
        self.setStartButton.clicked.connect(self.set_loop_start)
        
        self.setEndButton = ToolButton()
        self.setEndButton.setText("]")
        self.setEndButton.setToolTip("Loop vége")
        self.setEndButton.clicked.connect(self.set_loop_end)
        
        self.clearMarkersButton = ToolButton(FluentIcon.DELETE)
        self.clearMarkersButton.setToolTip("Loop törlése")
        self.clearMarkersButton.clicked.connect(self.clear_loop_markers)
        
        self.saveLoopButton = ToolButton(FluentIcon.SAVE)
        self.saveLoopButton.setToolTip("Save Loop Segment")
        self.saveLoopButton.clicked.connect(self.save_loop_segment)
        
        self.saveFrameButton = ToolButton(FluentIcon.PHOTO)
        self.saveFrameButton.setToolTip("Save Current Frame")
        self.saveFrameButton.clicked.connect(self.save_current_frame)
        
        self.buttonsLayout.addWidget(self.loopLabel)
        self.buttonsLayout.addWidget(self.loopCombo)
        self.buttonsLayout.addWidget(self.globalLoopToggle)
        self.buttonsLayout.addWidget(self.loopFramesLabel)
        self.buttonsLayout.addWidget(self.setStartButton)
        self.buttonsLayout.addWidget(self.setEndButton)
        self.buttonsLayout.addWidget(self.clearMarkersButton)
        self.buttonsLayout.addWidget(self.saveLoopButton)
        self.buttonsLayout.addWidget(self.saveFrameButton)
        
        self.loopCombo.setStyleSheet("""
            QComboBox {
                background: rgba(255, 255, 255, 0.0605);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-bottom: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 5px;
                padding: 4px 10px;
                min-height: 22px;
                color: white;
                font-size: 13px;
            }
            QComboBox:hover {
                background: rgba(255, 255, 255, 0.09);
            }
            QComboBox::drop-down {
                border: none;
                width: 0px;
            }
            QComboBox::down-arrow {
                image: none;
                border: none;
                background: transparent;
            }
            QComboBox QAbstractItemView {
                background-color: #2c2c2c;
                border: 1px solid rgba(0, 0, 0, 0.4);
                selection-background-color: rgba(255, 255, 255, 0.1);
                color: white;
                outline: none;
            }
        """)
        
        self.buttonsLayout.addSpacing(10)
        
        self.buttonsLayout.addSpacing(20)
        
        # Zoom
        self.zoomLabel = CaptionLabel("Zoom")
        self.zoomValueLabel = CaptionLabel("100%")
        self.zoomValueLabel.setFixedWidth(40)
        self.zoomSlider = QSlider(Qt.Orientation.Horizontal)
        self.zoomSlider.setRange(100, 1000)
        self.zoomSlider.setSingleStep(20)   # 20% steps
        self.zoomSlider.setPageStep(20)
        self.zoomSlider.setValue(100)
        self.zoomSlider.setFixedWidth(120)
        self.zoomSlider.setStyleSheet(FLUENT_SLIDER_STYLE)
        self.zoomSlider.valueChanged.connect(self.update_zoom)
        self.buttonsLayout.addWidget(self.zoomLabel)
        self.buttonsLayout.addWidget(self.zoomSlider)
        self.buttonsLayout.addWidget(self.zoomValueLabel)
        
        self.buttonsLayout.addSpacing(20)
        
        # Volume
        self.volumeButton = ToolButton(FluentIcon.VOLUME)
        self.volumeButton.clicked.connect(self.toggle_mute)
        self.volumeSlider = QSlider(Qt.Orientation.Horizontal)
        self.volumeSlider.setRange(0, 100)
        self.volumeSlider.setValue(70)
        self.volumeSlider.setFixedWidth(120)
        self.volumeSlider.setStyleSheet(FLUENT_SLIDER_STYLE)
        self.audioOutput.setVolume(0.7)
        self.volumeSlider.valueChanged.connect(self.set_volume)
        self.buttonsLayout.addWidget(self.volumeButton)
        self.buttonsLayout.addWidget(self.volumeSlider)
        
        self.buttonsLayout.addSpacing(20)
        self.togglePlaylistButton = ToolButton(FluentIcon.MENU)
        self.togglePlaylistButton.setToolTip("Toggle Playlist")
        self.togglePlaylistButton.clicked.connect(self.toggle_playlist)
        self.buttonsLayout.addWidget(self.togglePlaylistButton)
        
        self.controlsLayout.addLayout(self.buttonsLayout)
        # Margin around the controls card itself for breathing room, but none on top
        self.playerLayout.addWidget(self.controlsCard, stretch=0)
        self.playerLayout.setContentsMargins(0, 0, 0, 0)
        
        # Add to FluentWindow and hide navigation sidebar to maximize video space
        self.playerInterface.setObjectName("playerInterface")
        self.stackedWidget.addWidget(self.playerInterface)
        self.stackedWidget.setCurrentWidget(self.playerInterface)
        self.navigationInterface.hide()
        self.navigationInterface.setFixedWidth(0)
        # Zero out EVERYTHING in the window hierarchy
        self.stackedWidget.setContentsMargins(0, 0, 0, 0)
        self.hBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.hBoxLayout.setSpacing(0)
        self.playerLayout.setContentsMargins(0, 0, 0, 0)
        self.playerLayout.setSpacing(0)
        
    def open_file(self):
        fileNames, _ = QFileDialog.getOpenFileNames(self, "Videók hozzáadása", "", 
                                                   "Videó fájlok (*.mp4 *.mkv *.avi *.mov)")
        if fileNames:
            for fileName in fileNames:
                # Add to playlist if not already there
                exists = False
                for i in range(self.playlistList.count()):
                    if self.playlistList.item(i).data(Qt.ItemDataRole.UserRole) == fileName:
                        exists = True
                        break
                
                if not exists:
                    item = QListWidgetItem(os.path.basename(fileName))
                    item.setData(Qt.ItemDataRole.UserRole, fileName)
                    self.playlistList.addItem(item)
            
            # Auto-play first one if nothing is playing
            if self.mediaPlayer.playbackState() == QMediaPlayer.PlaybackState.StoppedState:
                self.load_video(fileNames[0])

    def load_video(self, filePath):
        # Save markers for current video before switching
        self.save_current_markers()
        
        try:
            self.currentFilePath = filePath
            self.zoomSlider.setValue(100)
            self.view.set_scroll_state(0, 0)
            
            # Get accurate info using ffprobe before loading into player
            fps, duration_ms, total_frames = self.get_video_info(filePath)
            if fps > 0:
                self.fps = fps
                print(f"ffprobe detected FPS: {self.fps}")
            
            self.current_cache_index = 0
            self.update_pixmap_from_cache()
            
            self.mediaPlayer.setSource(QUrl.fromLocalFile(filePath))
            self.setWindowTitle(os.path.basename(filePath))
            
            if duration_ms > 0:
                self.update_duration(duration_ms)
            
            # Load markers if they exist
            self.load_markers_for_current()
            
            self.playButton.setEnabled(True)
            self.mediaPlayer.pause()
            self.playButton.setIcon(FluentIcon.PLAY)
            
            # Start extraction
            self.start_full_extraction()
            
        except Exception as e:
            print(f"Hiba a fájl megnyitásakor: {e}")

    def get_video_info(self, file_path):
        """Get FPS and duration using ffprobe"""
        try:
            ffprobe_path = get_resource_path("ffprobe.exe" if os.name == 'nt' else "ffprobe")
            if not os.path.exists(ffprobe_path):
                ffprobe_path = "ffprobe"
                
            cmd = [
                ffprobe_path, "-v", "error", 
                "-select_streams", "v:0",
                "-show_entries", "stream=avg_frame_rate,duration,nb_frames",
                "-of", "json", filePath
            ]
            
            creationflags = 0
            if os.name == 'nt':
                creationflags = subprocess.CREATE_NO_WINDOW
                
            result = subprocess.check_output(cmd, creationflags=creationflags).decode('utf-8')
            data = json.loads(result)
            if not data.get('streams'):
                return 30.0, 0, 0
                
            stream = data['streams'][0]
            
            # FPS
            avg_fps = stream.get('avg_frame_rate', '30/1')
            if '/' in avg_fps:
                num, den = map(int, avg_fps.split('/'))
                fps = num / den if den != 0 else 30.0
            else:
                fps = float(avg_fps)
                
            # Duration (seconds)
            duration = float(stream.get('duration', 0))
            if duration == 0:
                cmd_fmt = [ffprobe_path, "-v", "error", "-show_entries", "format=duration", "-of", "json", filePath]
                result_fmt = subprocess.check_output(cmd_fmt, creationflags=creationflags).decode('utf-8')
                data_fmt = json.loads(result_fmt)
                duration = float(data_fmt.get('format', {}).get('duration', 0))
            
            # Frame count
            nb_frames = int(stream.get('nb_frames', 0))
            if nb_frames == 0 and duration > 0:
                nb_frames = int(duration * fps)
                
            return fps, duration * 1000, nb_frames
        except Exception as e:
            print(f"ffprobe error: {e}")
            return 30.0, 0, 0

    def save_current_markers(self):
        if self.currentFilePath:
            scroll_x, scroll_y = self.view.get_scroll_state()
            self.playlistData[self.currentFilePath] = {
                'startFrame': self.loopStartFrame,
                'endFrame': self.loopEndFrame,
                'loopMode': self.loopCombo.currentIndex(),
                'speed': self.speedSlider.value(),
                'zoom': self.zoomSlider.value(),
                'scrollX': scroll_x,
                'scrollY': scroll_y
            }

    def load_markers_for_current(self):
        if self.currentFilePath in self.playlistData:
            data = self.playlistData[self.currentFilePath]
            self.loopStartFrame = data.get('startFrame', 0)
            self.loopEndFrame = data.get('endFrame', 0)
                
            self.loopCombo.setCurrentIndex(data.get('loopMode', 0))
            self.isPingPong = (self.loopCombo.currentIndex() == 3)
            
            # Load speed and zoom
            self.speedSlider.setValue(data.get('speed', 100))
            self.zoomSlider.setValue(data.get('zoom', 100))
            self.view.set_scroll_state(data.get('scrollX', 0), data.get('scrollY', 0))
        else:
            self.loopStartFrame = 0
            self.loopEndFrame = 0
            if not self.globalLoopToggle.isChecked():
                self.loopCombo.setCurrentIndex(0) # Default None
            self.speedSlider.setValue(100)
            self.zoomSlider.setValue(100)
            
        # Ensure the UI reflects the loaded/reset markers
        self.progressBar.update_markers(self.loopStartFrame, self.loopEndFrame)
        self.update_loop_frames_label()

    def add_files_to_playlist(self, files):
        for filePath in files:
            if os.path.isfile(filePath):
                # Create item with placeholder icon
                item = QListWidgetItem(os.path.basename(filePath))
                item.setSizeHint(QSize(120, 130))
                item.setData(Qt.ItemDataRole.UserRole, filePath)
                # Set a default grey icon while loading
                placeholder = QPixmap(120, 120)
                placeholder.fill(QColor(60, 60, 60))
                item.setIcon(QIcon(placeholder))
                self.playlistList.addItem(item)
                
                # Start thumbnail extraction
                thread = ThumbnailThread(filePath, self)
                thread.finished.connect(self.on_thumbnail_ready)
                self.thumb_threads.append(thread)
                thread.start()

    def on_thumbnail_ready(self, filePath, pixmap):
        # Find the item in the list and update its icon
        for i in range(self.playlistList.count()):
            item = self.playlistList.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == filePath:
                item.setIcon(QIcon(pixmap))
                break

    def on_playlist_item_clicked(self, item):
        filePath = item.data(Qt.ItemDataRole.UserRole)
        self.load_video(filePath)

    def remove_from_playlist(self):
        item = self.playlistList.currentItem()
        if item:
            path = item.data(Qt.ItemDataRole.UserRole)
            if path in self.playlistData:
                del self.playlistData[path]
            self.playlistList.takeItem(self.playlistList.row(item))

    def toggle_playlist(self):
        is_visible = self.playlistContainer.isVisible()
        self.playlistContainer.setVisible(not is_visible)

    def save_playlist_to_file(self):
        fileName, _ = QFileDialog.getSaveFileName(self, "Save Project", "", "JSON Files (*.json)")
        if fileName:
            data = {
                'files': [],
                'markers': self.playlistData
            }
            for i in range(self.playlistList.count()):
                item = self.playlistList.item(i)
                data['files'].append(item.data(Qt.ItemDataRole.UserRole))
            
            with open(fileName, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)

    def load_playlist_from_file(self):
        fileName, _ = QFileDialog.getOpenFileName(self, "Open Project", "", "JSON Files (*.json)")
        if fileName:
            with open(fileName, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.playlistList.clear()
            self.playlistData = data.get('markers', {})
            
            for filePath in data.get('files', []):
                if os.path.exists(filePath):
                    item = QListWidgetItem(os.path.basename(filePath))
                    item.setData(Qt.ItemDataRole.UserRole, filePath)
                    self.playlistList.addItem(item)
            
            if self.playlistList.count() > 0:
                self.load_video(self.playlistList.item(0).data(Qt.ItemDataRole.UserRole))

    def play_pause(self):
        if self.is_playing:
            self.stop_playback()
        else:
            self.is_playing = True
            self.playButton.setIcon(FluentIcon.PAUSE)
            
            # Reset time tracking
            self.frame_accumulator = 0.0
            self.elapsedTimer.start()
            self.last_advance_ms = 0
            
            # Start timer at a fixed high frequency (e.g. 10ms / 100Hz)
            self.playbackTimer.start(10)
            
            if self.isForward and self.fps > 0:
                audio_pos = int((self.current_cache_index * 1000) / self.fps)
                self.mediaPlayer.setPosition(audio_pos)
                self.audioOutput.setMuted(self.userMutedIntent)
                self.mediaPlayer.play()
            else:
                self.audioOutput.setMuted(True)
            
    def stop_playback(self):
        self.is_playing = False
        self.playbackTimer.stop()
        self.mediaPlayer.pause()
        self.playButton.setIcon(FluentIcon.PLAY)
        
    def set_position(self, index):
        self.current_cache_index = index
        self.update_pixmap_from_cache()
        
        # Update labels (convert frames back to ms for display)
        if self.fps > 0:
            ms = int((index * 1000) / self.fps)
            self.currentTimeLabel.setText(self.format_time(ms))

    def on_slider_pressed(self):
        self.is_scrubbing = True
        
    def on_slider_released(self):
        self.is_scrubbing = False
        # Sync audio to final position
        if self.fps > 0:
            pos = int((self.current_cache_index * 1000) / self.fps)
            self.mediaPlayer.setPosition(pos)
        # Update slider to exact frame position
        self.update_pixmap_from_cache()
        
    def _apply_sync_zoom(self, val):
        self.zoomSlider.blockSignals(True)
        self.zoomSlider.setValue(val)
        self.zoomSlider.setSliderPosition(val)
        self.zoomSlider.blockSignals(False)
        self.zoomValueLabel.setText(f"{val}%")
        self.zoomSlider.update()
        
    def step_frame(self, direction):
        self.current_cache_index += direction
        # Clamp bounds
        if self.cached_frame_files:
            self.current_cache_index = max(0, min(len(self.cached_frame_files) - 1, self.current_cache_index))
        self.update_pixmap_from_cache()

    def handle_state_change(self, state):
        is_paused_or_stopped = not self.is_playing
        if hasattr(self, 'stepBackButton'):
            self.stepBackButton.setEnabled(is_paused_or_stopped)
            self.stepForwardButton.setEnabled(is_paused_or_stopped)
        
        # Sync play button icon
        if self.is_playing:
            self.playButton.setIcon(FluentIcon.PAUSE)
        else:
            self.playButton.setIcon(FluentIcon.PLAY)
        
    def update_duration(self, duration):
        if self.fps > 0:
            total_frames = int((duration / 1000.0) * self.fps)
            self.progressBar.setRange(0, total_frames)
            self.totalTimeLabel.setText(self.format_time(duration))
            
            if self.loopEndFrame == 0 or self.loopEndFrame > total_frames:
                self.loopEndFrame = total_frames
                self.progressBar.update_markers(self.loopStartFrame, self.loopEndFrame)
                self.update_loop_frames_label()
        
    def set_volume(self, volume):
        self.audioOutput.setVolume(volume / 100)
        if volume > 0 and self.audioOutput.isMuted():
            self.toggle_mute() # Auto-unmute if sliding up
        elif volume == 0 and not self.audioOutput.isMuted():
            self.toggle_mute() # Auto-mute if reaching 0
        
    def toggle_mute(self):
        is_muted = not self.audioOutput.isMuted()
        self.userMutedIntent = is_muted
        self.audioOutput.setMuted(is_muted)
        self.volumeButton.setIcon(FluentIcon.MUTE if is_muted else FluentIcon.VOLUME)
        
    def on_speed_slider_changed(self, value):
        snapped = round(value / 5) * 5
        if snapped != value:
            self.speedSlider.setValue(snapped)
            return
        rate = snapped / 100.0
        self.mediaPlayer.setPlaybackRate(rate)
        self.speedValueLabel.setText(f"{snapped}%")
        # No need to update timer interval, advance_frame handles it via rate calculation
        
    def on_loop_mode_changed(self, index):
        # index: 0: None, 1: Forward, 2: Backward, 3: Ping-Pong
        self.isPingPong = (index == 3)
        
    def update_zoom(self, value):
        snapped = round(value / 20) * 20
        if snapped < 100:
            snapped = 100
        if snapped != value:
            self.zoomSlider.setValue(snapped)
            return
        self.zoomLevel = snapped / 100.0
        # Sync view scale
        factor = self.zoomLevel / self.view.zoomLevel
        self.view.scale(factor, factor)
        self.view.zoomLevel = self.zoomLevel
        self.zoomValueLabel.setText(f"{snapped}%")
        
    def sync_zoom_ui(self, zoom_level):
        self.zoomLevel = zoom_level
        val = int(zoom_level * 100)
        # Use singleShot to ensure the UI updates correctly in the next event loop cycle
        QTimer.singleShot(0, lambda: self._apply_sync_zoom(val))
            
    def handle_status_change(self, status):
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            # Metadata is now primarily handled by ffprobe in load_video
            # but we still check handle_metadata_change as a fallback
            self.handle_metadata_change()
            
            # Adjust video item size to fit video aspect ratio
            sink = self.mediaPlayer.videoSink()
            if sink and self.view:
                size = sink.videoSize()
                if not size.isEmpty():
                    self.view.setSceneRect(QRectF(0, 0, size.width(), size.height()))
                    self.view.fitInView(self.pixmapItem, Qt.AspectRatioMode.KeepAspectRatio)
                    self.view.zoomLevel = 1.0
                    self.sync_zoom_ui(1.0)

    def format_time(self, ms):
        seconds = (ms // 1000) % 60
        minutes = (ms // (1000 * 60)) % 60
        hours = (ms // (1000 * 60 * 60))
        if hours > 0:
            return f"{hours:02}:{minutes:02}:{seconds:02}"
        return f"{minutes:02}:{seconds:02}"

    def update_loop_frames_label(self):
        start_f = self.loopStartFrame
        end_f = self.loopEndFrame
        if end_f == 0:
            end_f = self.progressBar.maximum()
            
        self.loopFramesLabel.setText(f"[F: {start_f} - {end_f}]")

    def set_loop_start(self):
        self.loopStartFrame = self.current_cache_index
        if self.loopStartFrame >= self.loopEndFrame and self.loopEndFrame != 0:
            self.loopEndFrame = self.progressBar.maximum()
            
        self.progressBar.update_markers(self.loopStartFrame, self.loopEndFrame)
        self.update_loop_frames_label()
        self.save_current_markers()

    def set_loop_end(self):
        self.loopEndFrame = self.current_cache_index
        if self.loopEndFrame <= self.loopStartFrame:
            self.loopStartFrame = 0
            
        self.progressBar.update_markers(self.loopStartFrame, self.loopEndFrame)
        self.update_loop_frames_label()
        self.save_current_markers()

    def clear_loop_markers(self):
        self.loopStartFrame = 0
        self.loopEndFrame = self.progressBar.maximum()
        self.progressBar.update_markers(0, self.loopEndFrame)
        self.update_loop_frames_label()
        self.save_current_markers()

    def save_current_frame(self):
        if not self.cached_frame_files or self.current_cache_index < 0 or self.current_cache_index >= len(self.cached_frame_files):
            return
            
        fileName, _ = QFileDialog.getSaveFileName(self, "Save Frame", "", "PNG Image (*.png)")
        if fileName:
            img = QImage(self.cached_frame_files[self.current_cache_index])
            img.save(fileName)

    def save_loop_segment(self):
        if not self.currentFilePath:
            return
            
        fileName, _ = QFileDialog.getSaveFileName(self, "Save Loop", "", "Video Files (*.mp4 *.mkv)")
        if fileName:
            import subprocess
            
            base_dir = os.path.dirname(os.path.abspath(__file__))
            ffmpeg_path = os.path.join(base_dir, "ffmpeg.exe" if os.name == 'nt' else "ffmpeg")
            
            if not os.path.exists(ffmpeg_path):
                ffmpeg_path = "ffmpeg" # Fallback to system path
                
            if self.fps > 0:
                start_f = self.loopStartFrame
                start_sec = max(0.0, (start_f / self.fps) - 0.001)
            else:
                start_f = self.loopStartFrame
                start_sec = 0.0 # Unknown timing
            
            # Frame-accurate cutting requires re-encoding
            encode_args = ["-c:v", "libx264", "-crf", "18", "-preset", "fast", "-c:a", "aac", "-b:a", "192k"]
            
            # If no end marker is explicitly set or it's at the very end
            if self.loopEndFrame == 0 or self.loopEndFrame >= self.progressBar.maximum():
                # Extract from start_sec to the end
                cmd = [
                    ffmpeg_path, "-y",
                    "-ss", f"{start_sec:.6f}",
                    "-i", self.currentFilePath
                ] + encode_args + [fileName]
            else:
                if self.fps > 0:
                    end_f = self.loopEndFrame
                    frames_count = max(1, end_f - start_f)
                    duration_sec = (frames_count / self.fps) + 0.005 # Small buffer for audio
                    
                    cmd = [
                        ffmpeg_path, "-y",
                        "-ss", f"{start_sec:.6f}",
                        "-i", self.currentFilePath,
                        "-t", f"{duration_sec:.6f}",
                        "-frames:v", str(frames_count)
                    ] + encode_args + [fileName]
                else:
                    end_f = self.loopEndFrame
                    duration_sec = (end_f - start_f) / 30.0 # Fallback 30fps
                    cmd = [
                        ffmpeg_path, "-y",
                        "-ss", f"{start_sec:.6f}",
                        "-i", self.currentFilePath,
                        "-t", f"{duration_sec:.6f}"
                    ] + encode_args + [fileName]
                
            try:
                # Use CREATE_NO_WINDOW to hide the command prompt on Windows
                creationflags = 0
                if os.name == 'nt':
                    creationflags = subprocess.CREATE_NO_WINDOW
                    
                subprocess.Popen(cmd, creationflags=creationflags)
            except Exception as e:
                print(f"Error saving loop: {e}")

    def handle_metadata_change(self):
        meta = self.mediaPlayer.metaData()
        fps = meta.value(QMediaMetaData.Key.VideoFrameRate)
        if fps and float(fps) > 0:
            self.fps = float(fps)
            print(f"Detected FPS: {self.fps}")
            self.update_loop_frames_label()
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Only fit in view if we are not currently zoomed in
        if hasattr(self, 'pixmapItem') and self.view and getattr(self, 'zoomLevel', 1.0) == 1.0:
            self.view.fitInView(self.pixmapItem, Qt.AspectRatioMode.KeepAspectRatio)

