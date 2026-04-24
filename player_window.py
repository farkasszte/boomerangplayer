import os
import sys
import subprocess
import tempfile
import shutil
import glob
import json
import time
import math
import numpy as np

# System volume control
try:
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from comtypes import CLSCTX_ALL
    HAS_PYCAW = True
except Exception:
    HAS_PYCAW = False

from PyQt6.QtCore import Qt, QUrl, QTimer, QSize, QElapsedTimer, QPoint, QPointF, QRectF
from PyQt6.QtGui import QIcon, QPainter, QPen, QColor, QImage, QPixmap, QTransform, QPainterPath
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFileDialog, 
                             QGraphicsView, QGraphicsScene, QSlider, QFrame, QListWidgetItem, 
                             QSplitter, QGraphicsPixmapItem, QLabel, QComboBox, QMenu,
                             QColorDialog, QButtonGroup, QGridLayout)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaMetaData

# Brute force silence qfluentwidgets during import
_temp_stdout = sys.stdout
sys.stdout = open(os.devnull, 'w')
try:
    import qfluentwidgets
    from qfluentwidgets import (FluentWindow, 
                                FluentIcon, ToolButton, 
                                CardWidget, CaptionLabel,
                                SwitchButton, ListWidget, PushButton, MessageBox, 
                                SingleDirectionScrollArea)
    qfluentwidgets.HELP_MESSAGE = False
finally:
    sys.stdout.close()
    sys.stdout = _temp_stdout

from PyQt6.QtCore import qInstallMessageHandler

# Import extracted modules
from utils import get_resource_path, format_time, qt_message_handler, load_config, save_config
from styles import (FLUENT_SLIDER_STYLE, COMPACT_BTN_STYLE, MENU_STYLE, 
                    DRAWING_ACTION_STYLE, TOOL_BTN_STYLE, ACTION_BTN_STYLE, 
                    LOOP_COMBO_STYLE, VOLUME_POPUP_STYLE, PEN_COLOR_BTN_STYLE_TEMPLATE)
from components import DropListWidget, MarkerSlider, ZoomView
from threads import FrameExtractionThread, ThumbnailThread
from translations import set_lang, tr, get_lang
from settings_page import SettingsDialog
from PyQt6.QtMultimedia import QMediaDevices

qInstallMessageHandler(qt_message_handler)





class PlayerWindow(FluentWindow):
    def __init__(self):
        # Load Config
        self.config = load_config()
        set_lang(self.config.get('language', 'en'))
        
        # Initialize attributes BEFORE super().__init__() because it triggers resize events
        self.videoItem = None
        self.view = None
        
        from qfluentwidgets import setTheme, Theme
        setTheme(Theme.DARK)
        
        super().__init__()
        self.setWindowIcon(QIcon(get_resource_path("app_icon.ico")))
        self.setWindowTitle("Boomerang Player")
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
        self.playlistData = {} # {path: {'markers': [], 'loopMode': 0}}
        self.isPingPong = True
        self.isForward = True
        self.zoomLevel = 1.0
        self.markers = []
        self.active_loop_start = 0
        self.active_loop_end = 0
        self.needs_range_update = True
        self.fps = 30.0 # Default fallback
        self.userMutedIntent = False
        self.isMirrored = False
        self.isMirroredVertical = False
        self.rotationAngle = 0
        self.last_transform_state = None # (width, height, rotation, mirrored, mirrored_v)
        
        # Initialize Media Player
        self.mediaPlayer = QMediaPlayer()
        self.audioOutput = QAudioOutput()
        self.mediaPlayer.setAudioOutput(self.audioOutput)
        
        # System Volume Initialization
        self.volume_ctrl = None
        if HAS_PYCAW:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                try:
                    import comtypes
                    from comtypes import CLSCTX_ALL, GUID
                    try: comtypes.CoInitialize()
                    except: pass 
                    
                    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
                    
                    # Hardcoded GUIDs for fallback
                    IID_IAudioEndpointVolume = "{5CDF2C82-841E-4546-9722-0CF74078229A}"
                    
                    def try_link_flexible(device_obj):
                        if not device_obj: return None
                        potential_targets = [device_obj]
                        try:
                            for attr in dir(device_obj):
                                try:
                                    val = getattr(device_obj, attr)
                                    if hasattr(val, 'Activate'):
                                        potential_targets.append(val)
                                except: continue
                        except: pass
                        
                        for target in potential_targets:
                            try:
                                iid = getattr(IAudioEndpointVolume, '_iid_', IID_IAudioEndpointVolume)
                                try:
                                    interface = target.Activate(GUID(iid), CLSCTX_ALL, None)
                                    if interface:
                                        return interface.QueryInterface(IAudioEndpointVolume)
                                except: continue
                            except: continue
                        return None

                    # Main linkage attempt
                    try:
                        test_dev = AudioUtilities.GetSpeakers()
                        self.volume_ctrl = try_link_flexible(test_dev)
                    except: pass
                    
                    if self.volume_ctrl is None:
                        try:
                            for d in AudioUtilities.GetAllDevices():
                                self.volume_ctrl = try_link_flexible(d)
                                if self.volume_ctrl: break
                        except: pass
                except: pass
        
        # Cache and playback variables
        self.cached_frame_dict = {}
        self.current_temp_dir = None
        self.extraction_thread = None
        self.cached_file_path = None
        self.current_cache_index = 0
        self.last_extracted_center = -1
        self.cache_window_half = 600 # Adjustable via UI
        self.is_zoomed_nav = False
        self.total_frames = 0
        self.is_playing = False
        self.is_scrubbing = False
        self.was_playing_before_cache_miss = False
        
        # UI Setup
        self.init_ui()
        
        # Connections
        self.mediaPlayer.durationChanged.connect(self.update_duration)
        self.mediaPlayer.playbackStateChanged.connect(self.handle_state_change)
        self.mediaPlayer.mediaStatusChanged.connect(self.handle_status_change)
        self.mediaPlayer.metaDataChanged.connect(self.handle_metadata_change)
        
        # Master playback timer and elapsed time tracking
        self.playbackTimer = QTimer()
        self.playbackTimer.setTimerType(Qt.TimerType.PreciseTimer)
        self.playbackTimer.timeout.connect(self.advance_frame)
        self.elapsedTimer = QElapsedTimer()
        self.last_advance_ms = 0
        
        # Shortcuts mapping (from config)
        self.shortcuts = self.config.get('shortcuts', {})
        

            
    def cleanup_cache(self):
        if self.current_temp_dir and os.path.exists(self.current_temp_dir):
            try:
                shutil.rmtree(self.current_temp_dir, ignore_errors=True)
            except:
                pass
        self.current_temp_dir = None
        self.cached_frame_dict = {}
        self.last_extracted_center = -1
        if hasattr(self, 'pixmapItem'):
            self.pixmapItem.setPixmap(QPixmap())


    def request_frame_extraction(self, center_frame, force=False):
        if not self.currentFilePath:
            return
            
        if self.extraction_thread and self.extraction_thread.isRunning():
            return # Already extracting
            
        start_frame = max(0, center_frame - self.cache_window_half)
        num_frames = self.cache_window_half * 2
        
        # Don't extract if we already have this exact range (optimization)
        threshold = self.cache_window_half // 2
        if not force and self.last_extracted_center != -1 and abs(self.last_extracted_center - center_frame) < threshold:
            return
            
        self.last_extracted_center = center_frame
        
        if not self.current_temp_dir:
            self.current_temp_dir = tempfile.mkdtemp(prefix="boomerang_frames_")
            
        self.extraction_thread = FrameExtractionThread(
            self.currentFilePath, 
            start_frame, 
            num_frames, 
            self.fps, 
            self.current_temp_dir, 
            self
        )
        self.extraction_thread.finished_extraction.connect(self.on_extraction_finished)
        self.extraction_thread.start()

    def start_full_extraction(self):
        if not self.currentFilePath:
            return
            
        self.cleanup_cache()
        self.loadingOverlay.show()
        
        # Start caching from the beginning or wherever the playlist data says
        data = self.playlistData.get(self.currentFilePath, {})
        start_pos = data.get('startFrame', 0)
        self.current_cache_index = start_pos
        self.request_frame_extraction(start_pos)

    def check_sliding_window(self):
        # Trigger background extraction if approaching the edge
        if self.last_extracted_center == -1:
            return
            
        dist = abs(self.current_cache_index - self.last_extracted_center)
        threshold = self.cache_window_half // 2
        if dist > threshold: # We moved enough from the center to trigger a new chunk
            self.request_frame_extraction(self.current_cache_index)

    def on_extraction_finished(self, frame_dict, temp_dir, start_frame, num_frames):
        if not frame_dict:
            self.loadingOverlay.hide()
            return
            
        self.cached_frame_dict.update(frame_dict)
        self.cached_file_path = self.currentFilePath
        
        # Prune old frames to save disk/RAM
        keys_to_delete = []
        center = self.last_extracted_center
        prune_threshold = self.cache_window_half * 1.5 # Keep a bit more for buffer
        for frame_idx, fpath in self.cached_frame_dict.items():
            if abs(frame_idx - center) > prune_threshold:
                keys_to_delete.append(frame_idx)
                
        for k in keys_to_delete:
            try:
                os.remove(self.cached_frame_dict[k])
            except:
                pass
            del self.cached_frame_dict[k]
            
        self.loadingOverlay.hide()
        print(f"Sliding Window Cache: Extracted frames {start_frame} to {start_frame + num_frames}. Cache size: {len(self.cached_frame_dict)}")
        
        # Only fit transform if it's the first time
        fit_needed = not hasattr(self, 'initial_fit_done')
        if fit_needed:
            self.initial_fit_done = True
        
        self.update_pixmap_from_cache()
        if fit_needed:
            self.apply_transformations(fit=True)
            
        self.sync_progress_bar()
        
        # Auto-resume if we were playing before the cache miss
        if getattr(self, 'was_playing_before_cache_miss', False):
            self.was_playing_before_cache_miss = False
            self.play_pause()

    def sync_progress_bar(self):
        if not self.currentFilePath:
            return
            
        self.progressBar.blockSignals(True)
        
        if getattr(self, 'is_zoomed_nav', False):
            s = getattr(self, 'cache_start', 0)
            e = getattr(self, 'cache_end', self.total_frames - 1)
            self.progressBar.setRange(s, e)
        else:
            self.progressBar.setRange(0, max(0, self.total_frames - 1))
            
        self.progressBar.setValue(self.current_cache_index)
        self.progressBar.blockSignals(False)
        self.progressBar.update()

    def closeEvent(self, event):
        self.cleanup_cache()
        super().closeEvent(event)

    def advance_frame(self):
        if not getattr(self, 'cached_frame_dict', None) or self.fps <= 0:
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
        
        # Update loop range only if needed (e.g. after seek or jump)
        loop_mode = self.loopCombo.currentIndex()
        if loop_mode == 0:
            start_frame = 0
            end_frame = max(0, self.total_frames - 1)
        else:
            if getattr(self, 'needs_range_update', True):
                self.active_loop_start, self.active_loop_end = self.get_active_loop_range()
                self.needs_range_update = False
                self.update_loop_frames_label()
            
            start_frame = self.active_loop_start
            end_frame = self.active_loop_end

        if self.isForward:
            self.current_cache_index += int_delta
            if self.current_cache_index > end_frame:
                if loop_mode in (1, 2, 3): # Looping
                    if loop_mode == 3: # Ping-pong
                        self.isForward = False
                        self.current_cache_index = end_frame - (self.current_cache_index - end_frame)
                    else: # Forward/Backward
                        self.current_cache_index = start_frame + (self.current_cache_index - end_frame - 1)
                    
                    if self.fps > 0:
                        self.mediaPlayer.setPosition(int(self.current_cache_index * 1000 / self.fps))
                        self.set_volume(self.audioOutput.volume() * 100)
                else:
                    self.current_cache_index = end_frame
                    self.stop_playback()
        else:
            self.current_cache_index -= int_delta
            if self.current_cache_index < start_frame:
                if loop_mode == 3: # Ping-pong
                    self.isForward = True
                    self.current_cache_index = start_frame + (start_frame - self.current_cache_index)
                    self.set_volume(self.audioOutput.volume() * 100)
                    if self.fps > 0:
                        self.mediaPlayer.setPosition(int(self.current_cache_index * 1000 / self.fps))
                elif loop_mode == 2: # Backward loop
                    self.current_cache_index = end_frame - (start_frame - self.current_cache_index - 1)
                else:
                    self.current_cache_index = start_frame
                    self.stop_playback()
                    
        # Clamp final index to total frames
        self.current_cache_index = max(0, min(max(0, self.total_frames - 1), self.current_cache_index))
        
        # Check cache boundaries and trigger if needed
        if self.current_cache_index not in self.cached_frame_dict:
            self.was_playing_before_cache_miss = self.is_playing
            self.stop_playback()
            self.loadingOverlay.show()
            self.request_frame_extraction(self.current_cache_index, force=True)
            return
            
        self.update_pixmap_from_cache()
        self.check_sliding_window()
        self.sync_progress_bar()

    def reset_adjustments(self):
        self.brightnessSlider.setValue(0)
        self.contrastSlider.setValue(100)
        self.gammaSlider.setValue(100)
        self.saturationSlider.setValue(100)
        self.update_pixmap_from_cache()

    def update_pixmap_from_cache(self):
        if self.current_cache_index in getattr(self, 'cached_frame_dict', {}):
            file_path = self.cached_frame_dict[self.current_cache_index]
            pixmap = QPixmap(file_path)
            
            # Apply image adjustments
            b = self.brightnessSlider.value()
            c = self.contrastSlider.value() / 100.0
            g = self.gammaSlider.value() / 100.0
            s = self.saturationSlider.value() / 100.0
            
            if b != 0 or c != 1.0 or g != 1.0 or s != 1.0:
                img = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
                width, height = img.width(), img.height()
                
                ptr = img.bits()
                ptr.setsize(img.sizeInBytes())
                arr = np.frombuffer(ptr, np.uint8).reshape((height, width, 4))
                
                # RGB processing
                rgb = arr[:, :, :3].astype(np.float32)
                
                if c != 1.0 or b != 0:
                    rgb = rgb * c + b
                    
                if g != 1.0:
                    rgb = 255.0 * (np.power(rgb / 255.0, 1.0 / g))
                    
                if s != 1.0:
                    # Luma weights (ITU-R 601-2)
                    gray = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
                    gray = np.stack([gray] * 3, axis=-1)
                    rgb = gray + s * (rgb - gray)
                
                arr[:, :, :3] = np.clip(rgb, 0, 255).astype(np.uint8)
                pixmap = QPixmap.fromImage(img)
            
            if self.pixmapItem:
                self.pixmapItem.setPixmap(pixmap)
                self.apply_transformations(fit=False)
            
            # Update position label
            if hasattr(self, 'frameLabel'):
                self.frameLabel.setText(f" [F: {self.current_cache_index + 1} / {self.total_frames}]")

        # Update slider to reflect current frame index
        if not self.is_scrubbing:
            self.sync_progress_bar()
            
        if self.fps > 0:
            pos = int((self.current_cache_index * 1000) / self.fps)
            self.currentTimeLabel.setText(format_time(pos))
            
    def init_ui(self):
        # --- Main Interface ---
        self.playerInterface = QWidget()
        self.playerLayout = QVBoxLayout(self.playerInterface)
        self.playerLayout.setContentsMargins(0, 0, 0, 0)
        self.playerLayout.setSpacing(0)
        
        # Splitter for Video + Playlist
        self.mainSplitter = QSplitter(Qt.Orientation.Horizontal)
        self.mainSplitter.setHandleWidth(1)
        self.mainSplitter.setStyleSheet("QSplitter::handle { background: transparent; }")
        
        self.scene = QGraphicsScene()
        self.view = ZoomView(self.scene, self.playerInterface)
        self.view.filesDropped.connect(self.handle_view_drop)
        self.view.zoomChanged.connect(self.sync_zoom_ui)
        self.view.setStyleSheet("border: none; background: black;")
        
        # Playlist Sidebar
        self.playlistContainer = QFrame()
        self.playlistContainer.setMinimumWidth(250)
        self.playlistContainer.setStyleSheet("background: #202020; border: none;")
        self.playlistLayout = QVBoxLayout(self.playlistContainer)
        self.playlistLayout.setContentsMargins(5, 5, 5, 5)
        
        self.playlistLabel = CaptionLabel(tr('playlist'))
        self.playlistLabel.setStyleSheet("font-size: 16px; font-weight: bold; color: white;")
        self.playlistLayout.addWidget(self.playlistLabel)
        
        self.thumbToggleRow = QHBoxLayout()
        self.thumbLabel = CaptionLabel(tr('show_thumbnails'))
        self.thumbToggle = SwitchButton()
        self.thumbToggle.setChecked(True)
        self.thumbToggle.setToolTip(tr('tip_thumbnails'))
        self.thumbToggle.checkedChanged.connect(self.on_thumb_toggle_changed)
        
        self.thumbToggleRow.addWidget(self.thumbLabel)
        self.thumbToggleRow.addStretch(1)
        self.thumbToggleRow.addWidget(self.thumbToggle)
        self.playlistLayout.addLayout(self.thumbToggleRow)
        self.playlistList = DropListWidget()
        self.playlistList.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.playlistList.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.playlistList.setStyleSheet("QListWidget { border: none; background: transparent; } QScrollBar:vertical { width: 0px; }")
        self.playlistList.setIconSize(QSize(120, 120))
        self.playlistList.itemDoubleClicked.connect(self.on_playlist_item_clicked)
        self.playlistList.filesDropped.connect(self.add_files_to_playlist)
        self.playlistLayout.addWidget(self.playlistList)
        
        self.thumb_threads = []
        
        self.playlistButtonsGrid = QGridLayout()
        self.playlistButtonsGrid.setSpacing(8)
        
        # --- Add Button ---
        self.btn_add = PushButton(tr('add'))
        self.btn_add.setToolTip(tr('tip_add'))
        self.addMenu = QMenu(self)
        self.addMenu.setStyleSheet(MENU_STYLE)
        self.addMenu.addAction(tr('add'), self.open_file) # Using tr('add') for "Add media" too or create new key
        self.addMenu.addAction("Add video folder", lambda: self.add_folder_contents(type="video"))
        self.addMenu.addAction("Add image folder", lambda: self.add_folder_contents(type="image"))
        self.addMenu.addSeparator()
        self.addMenu.addAction("Load playlist", self.load_playlist_from_file)
        self.btn_add.clicked.connect(self.show_add_menu)
        
        # --- Sort Button ---
        self.btn_sort = PushButton(tr('sort'))
        self.btn_sort.setToolTip(tr('tip_sort'))
        self.sortMenu = QMenu(self)
        self.sortMenu.setStyleSheet(MENU_STYLE)
        self.sortMenu.addAction("Name (A-Z)", lambda: self.sort_playlist_by("name_asc"))
        self.sortMenu.addAction("Name (Z-A)", lambda: self.sort_playlist_by("name_desc"))
        self.sortMenu.addAction("Date (Newest)", lambda: self.sort_playlist_by("date_newest"))
        self.sortMenu.addAction("Date (Oldest)", lambda: self.sort_playlist_by("date_oldest"))
        self.btn_sort.clicked.connect(self.show_sort_menu)
        
        # --- Save Button ---
        self.btn_save = PushButton(tr('save'))
        self.btn_save.setToolTip(tr('tip_save'))
        self.btn_save.clicked.connect(self.save_playlist_to_file)
        
        # --- Clear Button ---
        self.btn_clear = PushButton(tr('clear'))
        self.btn_clear.setToolTip(tr('tip_clear'))
        self.removeMenu = QMenu(self)
        self.removeMenu.setStyleSheet(MENU_STYLE)
        self.removeMenu.addAction("Remove selected", self.remove_from_playlist)
        self.removeMenu.addAction("Clear all", self.clear_playlist)
        self.btn_clear.clicked.connect(self.show_clear_menu)
        
        # Add to Grid
        self.playlistButtonsGrid.addWidget(self.btn_add, 0, 0)
        self.playlistButtonsGrid.addWidget(self.btn_sort, 0, 1)
        self.playlistButtonsGrid.addWidget(self.btn_save, 1, 0)
        self.playlistButtonsGrid.addWidget(self.btn_clear, 1, 1)
        
        self.playlistLayout.addLayout(self.playlistButtonsGrid)
        
        # Drawing Sidebar (Right - Alternative to Playlist)
        self.drawingContainer = QFrame()
        self.drawingContainer.setMinimumWidth(250)
        self.drawingContainer.setStyleSheet("background: #202020; border: none; QScrollBar { width: 0px; height: 0px; }")
        self.drawingSidebarLayout = QVBoxLayout(self.drawingContainer)
        self.drawingSidebarLayout.setContentsMargins(10, 10, 10, 10)
        self.drawingSidebarLayout.setSpacing(15)
        
        self.drawingSidebarTitle = CaptionLabel(tr('drawing_settings'))
        self.drawingSidebarTitle.setStyleSheet("font-size: 16px; font-weight: bold; color: white;")
        self.drawingSidebarLayout.addWidget(self.drawingSidebarTitle)
        
        # Drawing Toggle
        self.drawModeToggleLayout = QHBoxLayout()
        self.drawModeToggleLabel = QLabel(tr('drawing_mode'))
        self.drawModeToggleLabel.setStyleSheet("color: white; font-size: 13px;")
        self.drawModeToggle = SwitchButton()
        self.drawModeToggle.checkedChanged.connect(self.toggle_drawing_mode)
        self.drawModeToggleLayout.addWidget(self.drawModeToggleLabel)
        self.drawModeToggleLayout.addStretch(1)
        self.drawModeToggleLayout.addWidget(self.drawModeToggle)
        self.drawingSidebarLayout.addLayout(self.drawModeToggleLayout)
        
        # Laser Mode Toggle
        self.laserModeToggleLayout = QHBoxLayout()
        self.laserModeToggleLabel = QLabel(tr('laser_mode'))
        self.laserModeToggleLabel.setStyleSheet("color: white; font-size: 13px;")
        self.laserModeToggle = SwitchButton()
        self.laserModeToggle.checkedChanged.connect(self.toggle_laser_mode)
        self.laserModeToggleLayout.addWidget(self.laserModeToggleLabel)
        self.laserModeToggleLayout.addStretch(1)
        self.laserModeToggleLayout.addWidget(self.laserModeToggle)
        self.drawingSidebarLayout.addLayout(self.laserModeToggleLayout)
        
        self.toolsLayout = QGridLayout()
        self.toolsLayout.setSpacing(8)
        self.toolGroup = QButtonGroup(self)
        self.toolGroup.setExclusive(True)
        
        # 10 Tools for grid
        all_tools = [
            (tr('pen'), 'pen', tr('tip_pen')),
            (tr('line'), 'line', tr('tip_line')),
            (tr('arrow'), 'arrow', tr('tip_arrow')),
            (tr('text'), 'text', tr('tip_text')),
            (tr('rect'), 'rect', tr('tip_rect')),
            (tr('ellipse'), 'ellipse', tr('tip_ellipse')),
            (tr('triangle'), 'triangle', tr('tip_triangle')),
            (tr('obj_eraser'), 'obj_eraser', tr('tip_obj_eraser')),
            (tr('area_eraser'), 'area_eraser', tr('tip_area_eraser')),
            (tr('stroke_eraser'), 'stroke_eraser', tr('tip_stroke_eraser'))
        ]
        
        
        for i, (label, tool_id, tip) in enumerate(all_tools):
            btn = PushButton(label)
            btn.setFixedSize(115, 38)
            btn.setToolTip(tip)
            btn.setStyleSheet(TOOL_BTN_STYLE)
            
            btn.setCheckable(True)
            if tool_id == 'pen': btn.setChecked(True)
            self.toolGroup.addButton(btn)
            btn.clicked.connect(lambda checked, t=tool_id: self.set_active_tool(t))
                
            self.toolsLayout.addWidget(btn, i // 2, i % 2)
            
        self.drawingSidebarLayout.addLayout(self.toolsLayout)
        
        self.drawingSidebarLayout.addSpacing(15)
        
        # Thickness Row (Label + Preview + Color + Slider)
        thicknessRow = QHBoxLayout()
        self.penPreview = QLabel()
        self.penPreview.setFixedSize(30, 30)
        self.penPreview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.penPreview.setStyleSheet("background: transparent; border: none !important;")
        thicknessRow.addWidget(self.penPreview)
        
        self.penSizeLabel = QLabel("3 px")
        self.penSizeLabel.setStyleSheet("color: #00f2ff; font-size: 13px; font-weight: 500; background: transparent; border: none !important;")
        thicknessRow.addWidget(self.penSizeLabel)
        
        thicknessRow.addStretch(1)
        
        self.penColorBtn = PushButton(tr('color'))
        self.penColorBtn.setFixedSize(70, 32)
        self.penColorBtn.setToolTip(tr('color')) # No specific tooltip for color in translations yet
        self.penColorBtn.setStyleSheet("""
            PushButton {
                font-size: 14px;
                font-weight: 500;
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 4px;
            }
            PushButton:hover {
                background: rgba(255, 255, 255, 0.15);
            }
        """)
        self.penColorBtn.clicked.connect(self.choose_pen_color)
        thicknessRow.addWidget(self.penColorBtn)
        
        self.drawingSidebarLayout.addLayout(thicknessRow)
        
        self.penSizeSlider = QSlider(Qt.Orientation.Horizontal)
        self.penSizeSlider.setRange(1, 60)
        self.penSizeSlider.setValue(3)
        self.penSizeSlider.setStyleSheet(FLUENT_SLIDER_STYLE)
        self.penSizeSlider.valueChanged.connect(self.update_pen_width)
        self.drawingSidebarLayout.addWidget(self.penSizeSlider)
        
        self.drawingSidebarLayout.addSpacing(15)
        
        # Action Grid for Drawing (Save Screenshot, Undo, Clear)
        self.drawingActionsGrid = QGridLayout()
        self.drawingActionsGrid.setSpacing(8)
        
        self.saveScreenshotBtn = PushButton(tr('save_screenshot'))
        self.saveScreenshotBtn.clicked.connect(self.save_drawing_screenshot)
        self.saveScreenshotBtn.setToolTip(tr('tip_screenshot'))
        
        self.sidebarUndoBtn = PushButton(tr('undo'))
        self.sidebarUndoBtn.setToolTip(tr('tip_undo'))
        self.sidebarUndoBtn.clicked.connect(self.undo_last_stroke)
        
        self.sidebarClearBtn = PushButton(tr('clear'))
        self.sidebarClearBtn.setToolTip(tr('tip_clear_draw'))
        self.sidebarClearBtn.clicked.connect(self.clear_all_strokes)
        
        # Apply design style to all
        for btn in [self.saveScreenshotBtn, self.sidebarUndoBtn, self.sidebarClearBtn]:
            btn.setStyleSheet(DRAWING_ACTION_STYLE)
            btn.setMinimumHeight(38)
            
        self.drawingActionsGrid.addWidget(self.saveScreenshotBtn, 0, 0, 1, 2) # Top wide
        self.drawingActionsGrid.addWidget(self.sidebarUndoBtn, 1, 0)
        self.drawingActionsGrid.addWidget(self.sidebarClearBtn, 1, 1)
        
        self.drawingSidebarLayout.addLayout(self.drawingActionsGrid)
        
        self.drawingSidebarLayout.addStretch(1)
        self.drawingContainer.hide()
        
        # Settings Sidebar (Left)
        self.settingsContainer = QFrame()
        self.settingsContainer.setMinimumWidth(250)
        self.settingsContainer.setStyleSheet("background: #202020; border: none;")
        self.settingsLayout = QVBoxLayout(self.settingsContainer)
        self.settingsLayout.setContentsMargins(10, 10, 10, 10)
        self.settingsLayout.setSpacing(10)
        
        self.settingsTitle = CaptionLabel(tr('video_settings'))
        self.settingsTitle.setStyleSheet("font-size: 16px; font-weight: bold; color: white;")
        self.settingsLayout.addWidget(self.settingsTitle)
        
        self.scrollArea = SingleDirectionScrollArea(self.settingsContainer, Qt.Orientation.Vertical)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setStyleSheet("background: transparent; border: none;")
        self.scrollArea.setFrameShape(QFrame.Shape.NoFrame)
        self.scrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.settingsScrollWidget = QWidget()
        self.settingsScrollWidget.setStyleSheet("background: transparent;")
        self.settingsInnerLayout = QVBoxLayout(self.settingsScrollWidget)
        self.settingsInnerLayout.setContentsMargins(0, 0, 0, 0)
        self.settingsInnerLayout.setSpacing(10)
        
        self.scrollArea.setWidget(self.settingsScrollWidget)
        self.settingsLayout.addWidget(self.scrollArea)

        self.mainSplitter.addWidget(self.settingsContainer)
        self.mainSplitter.addWidget(self.view)
        self.mainSplitter.addWidget(self.playlistContainer)
        self.mainSplitter.addWidget(self.drawingContainer)
        self.mainSplitter.setStretchFactor(1, 1)
        
        # Force initial sizes: 0 for hidden sidebars, large for view, 250 for playlist
        self.mainSplitter.setSizes([0, 10000, 250, 0])
        
        self.settingsContainer.hide() # Hidden by default
        
        self.playerLayout.addWidget(self.mainSplitter, stretch=1)
        
        # Initial pen preview
        self.update_pen_preview()
        
        self.pixmapItem = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmapItem)
        
        # Overlay for loading
        self.loadingOverlay = QLabel(tr('caching_ram'), self.view)
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
        
        # Set initial volume from system if possible
        initial_vol = 50
        if self.volume_ctrl:
            try:
                initial_vol = int(self.volume_ctrl.GetMasterVolumeLevelScalar() * 100)
                self.userMutedIntent = self.volume_ctrl.GetMute()
            except:
                pass
        self.audioOutput.setVolume(initial_vol / 100.0)
        
        self.progressLayout.addWidget(self.currentTimeLabel)
        self.progressLayout.addWidget(self.frameLabel)
        self.progressLayout.addWidget(self.progressBar)
        self.progressLayout.addWidget(self.totalTimeLabel)
        self.controlsLayout.addLayout(self.progressLayout)
        
        # Buttons Row
        self.buttonsLayout = QHBoxLayout()
        
        # Left side: Settings & File Info
        self.toggleSettingsButton = ToolButton(FluentIcon.SETTING)
        self.toggleSettingsButton.setToolTip("Toggle settings")
        self.toggleSettingsButton.clicked.connect(self.toggle_settings)
        self.buttonsLayout.addWidget(self.toggleSettingsButton)
        
        self.buttonsLayout.addSpacing(10)
        
        # Center: Playback controls
        self.playbackButtonsLayout = QHBoxLayout()
        self.playbackButtonsLayout.setSpacing(0)
        
        # Center: Playback controls
        self.playbackButtonsLayout = QHBoxLayout()
        self.playbackButtonsLayout.setSpacing(0)
        
        self.stepBackButton = ToolButton(FluentIcon.LEFT_ARROW)
        self.stepBackButton.setToolTip(tr('tip_prev_frame'))
        self.stepBackButton.clicked.connect(lambda: self.step_frame(-1))
        self.stepBackButton.setFixedSize(32, 32)
        self.stepBackButton.setStyleSheet(COMPACT_BTN_STYLE + "ToolButton { border-top-left-radius: 4px; border-bottom-left-radius: 4px; }")
        
        self.playButton = ToolButton(FluentIcon.PLAY)
        self.playButton.setToolTip(tr('tip_play_pause'))
        self.playButton.setIconSize(QSize(24, 24))
        self.playButton.setFixedSize(32, 32)
        self.playButton.setStyleSheet(COMPACT_BTN_STYLE + "ToolButton { border-radius: 0px; border-right: none; }")
        self.playButton.clicked.connect(self.play_pause)
        
        self.stepForwardButton = ToolButton(FluentIcon.RIGHT_ARROW)
        self.stepForwardButton.setToolTip(tr('tip_next_frame'))
        self.stepForwardButton.clicked.connect(lambda: self.step_frame(1))
        self.stepForwardButton.setFixedSize(32, 32)
        self.stepForwardButton.setStyleSheet(COMPACT_BTN_STYLE + "ToolButton { border-right: 1px solid rgba(255, 255, 255, 0.08); border-top-right-radius: 4px; border-bottom-right-radius: 4px; }")

        self.playbackButtonsLayout.addWidget(self.stepBackButton)
        self.playbackButtonsLayout.addWidget(self.playButton)
        self.playbackButtonsLayout.addWidget(self.stepForwardButton)
        
        self.buttonsLayout.addStretch(1)
        self.buttonsLayout.addLayout(self.playbackButtonsLayout)
        self.buttonsLayout.addStretch(1)
        
        # --- Speed ---
        speedHeader = QHBoxLayout()
        self.speedLabel = CaptionLabel(tr('playback_speed'))
        self.speedValueLabel = CaptionLabel("1.0x")
        speedHeader.addWidget(self.speedLabel)
        speedHeader.addStretch(1)
        speedHeader.addWidget(self.speedValueLabel)
        
        self.speedSlider = QSlider(Qt.Orientation.Horizontal)
        self.speedSlider.setRange(10, 500)
        self.speedSlider.setValue(100)
        self.speedSlider.setStyleSheet(FLUENT_SLIDER_STYLE)
        self.speedSlider.valueChanged.connect(lambda v: self.speedValueLabel.setText(f"{v/100:.1f}x"))
        
        self.settingsInnerLayout.addLayout(speedHeader)
        self.settingsInnerLayout.addWidget(self.speedSlider)
        
        # --- Zoom Controls (Moved here) ---
        zoomGroup = QVBoxLayout()
        zoomGroup.setSpacing(5)
        zoomHeader = QHBoxLayout()
        self.zoomLabel = CaptionLabel(tr('zoom'))
        self.zoomValueLabel = CaptionLabel("100%")
        zoomHeader.addWidget(self.zoomLabel)
        zoomHeader.addStretch(1)
        zoomHeader.addWidget(self.zoomValueLabel)
        zoomGroup.addLayout(zoomHeader)
        
        self.zoomSlider = QSlider(Qt.Orientation.Horizontal)
        self.zoomSlider.setRange(100, 1000)
        self.zoomSlider.setValue(100)
        self.zoomSlider.setStyleSheet(FLUENT_SLIDER_STYLE)
        self.zoomSlider.valueChanged.connect(self.update_zoom)
        zoomGroup.addWidget(self.zoomSlider)
        
        self.settingsInnerLayout.addLayout(zoomGroup)
        self.settingsInnerLayout.addWidget(QFrame(frameShape=QFrame.Shape.HLine, frameShadow=QFrame.Shadow.Sunken))

        # --- Cache Window Settings ---
        cacheGroup = QVBoxLayout()
        cacheGroup.setSpacing(5)
        cacheHeader = QHBoxLayout()
        cacheLabel = CaptionLabel(tr('cache_window'))
        self.cacheValueLabel = CaptionLabel(str(self.cache_window_half))
        cacheHeader.addWidget(cacheLabel)
        cacheHeader.addStretch(1)
        cacheHeader.addWidget(self.cacheValueLabel)
        cacheGroup.addLayout(cacheHeader)
        
        self.cacheSlider = QSlider(Qt.Orientation.Horizontal)
        self.cacheSlider.setRange(100, 1500)
        self.cacheSlider.setSingleStep(10)
        self.cacheSlider.setPageStep(50)
        self.cacheSlider.setValue(self.cache_window_half)
        self.cacheSlider.setStyleSheet(FLUENT_SLIDER_STYLE)
        def update_cache_size(val):
            rounded_val = (val // 10) * 10
            self.cache_window_half = rounded_val
            self.cacheValueLabel.setText(str(rounded_val))
            # Sync slider position to rounded value if needed
            if val != rounded_val:
                self.cacheSlider.blockSignals(True)
                self.cacheSlider.setValue(rounded_val)
                self.cacheSlider.blockSignals(False)
        self.cacheSlider.valueChanged.connect(update_cache_size)
        cacheGroup.addWidget(self.cacheSlider)
        self.settingsInnerLayout.addLayout(cacheGroup)
        self.settingsInnerLayout.addWidget(QFrame(frameShape=QFrame.Shape.HLine, frameShadow=QFrame.Shadow.Sunken))

        # Image Adjustments
        self.adjLabel = CaptionLabel(tr('image_adjustments'))
        self.adjLabel.setStyleSheet("font-weight: bold; margin-top: 5px;")
        self.settingsInnerLayout.addWidget(self.adjLabel)

        def create_adj_slider(label_text, min_val, max_val, default):
            layout = QVBoxLayout()
            header = QHBoxLayout()
            lbl = CaptionLabel(label_text)
            val_lbl = CaptionLabel(str(default))
            header.addWidget(lbl)
            header.addStretch(1)
            header.addWidget(val_lbl)
            
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(min_val, max_val)
            slider.setValue(default)
            slider.setStyleSheet(FLUENT_SLIDER_STYLE)
            slider.valueChanged.connect(lambda v: (val_lbl.setText(str(v)), self.update_pixmap_from_cache()))
            
            layout.addLayout(header)
            layout.addWidget(slider)
            return slider, layout

        self.brightnessSlider, l1 = create_adj_slider("Brightness", -100, 100, 0)
        self.contrastSlider, l2 = create_adj_slider("Contrast", 0, 200, 100)
        self.gammaSlider, l3 = create_adj_slider("Gamma", 10, 300, 100)
        self.saturationSlider, l4 = create_adj_slider("Saturation", 0, 200, 100)

        self.settingsInnerLayout.addLayout(l1)
        self.settingsInnerLayout.addLayout(l2)
        self.settingsInnerLayout.addLayout(l3)
        self.settingsInnerLayout.addLayout(l4)

        footerButtonsLayout = QHBoxLayout()
        self.resetAdjButton = PushButton(tr('reset_image'))
        self.resetAdjButton.setMinimumWidth(100)
        self.resetAdjButton.clicked.connect(self.reset_adjustments)
        
        self.infoButton = PushButton(tr('file_info'))
        self.infoButton.setMinimumWidth(100)
        self.infoButton.clicked.connect(self.show_file_info)
        
        # Apply the unified style
        action_btn_style = """
            PushButton {
                font-size: 13px;
                font-weight: 500;
                padding: 6px;
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
            }
            PushButton:hover {
                background: rgba(255, 255, 255, 0.1);
            }
        """
        for btn in [self.resetAdjButton, self.infoButton]:
            btn.setStyleSheet(ACTION_BTN_STYLE)
            
        footerButtonsLayout.addWidget(self.resetAdjButton)
        footerButtonsLayout.addWidget(self.infoButton)
        self.settingsInnerLayout.addLayout(footerButtonsLayout)
        self.settingsInnerLayout.addWidget(QFrame(frameShape=QFrame.Shape.HLine, frameShadow=QFrame.Shadow.Sunken))
        
        # --- Loop Controls (Moved to Sidebar) ---
        loopGroup = QVBoxLayout()
        loopGroup.setSpacing(10)
        
        loopHeader = QHBoxLayout()
        self.loopLabel = CaptionLabel(tr('global_loop_mode'))
        self.globalLoopToggle = SwitchButton()
        self.globalLoopToggle.setChecked(True)
        self.globalLoopToggle.setOnText("On")
        self.globalLoopToggle.setOffText("Off")
        self.globalLoopToggle.setToolTip("Apply loop mode to all videos")
        loopHeader.addWidget(self.loopLabel)
        loopHeader.addStretch(1)
        loopHeader.addWidget(self.globalLoopToggle)
        loopGroup.addLayout(loopHeader)
        
        # --- Navigation Mode ---
        navGroup = QHBoxLayout()
        self.navLabel = CaptionLabel(tr('zoom_nav_bar'))
        self.navToggle = SwitchButton()
        self.navToggle.setChecked(False)
        self.navToggle.setOnText("On")
        self.navToggle.setOffText("Off")
        def toggle_nav_mode(checked):
            self.is_zoomed_nav = checked
            self.sync_progress_bar()
        self.navToggle.checkedChanged.connect(toggle_nav_mode)
        navGroup.addWidget(self.navLabel)
        navGroup.addStretch(1)
        navGroup.addWidget(self.navToggle)
        loopGroup.addLayout(navGroup)
        
        self.loopCombo = QComboBox()
        self.loopCombo.addItems([tr('loop_none'), tr('loop_forward'), tr('loop_backward'), tr('loop_pingpong')])
        self.loopCombo.setCurrentIndex(3)
        self.loopCombo.currentIndexChanged.connect(self.on_loop_mode_changed)
        self.loopCombo.setStyleSheet(LOOP_COMBO_STYLE)
        loopGroup.addWidget(self.loopCombo)
        
        markerLayout = QHBoxLayout()
        markerLayout = QHBoxLayout()
        self.smartMarkButton = PushButton(tr('mark'))
        self.smartMarkButton.setStyleSheet(TOOL_BTN_STYLE)
        self.smartMarkButton.clicked.connect(self.add_smart_marker)
        
        self.deleteMarkerButton = PushButton(tr('delete'))
        self.deleteMarkerButton.setStyleSheet(TOOL_BTN_STYLE)
        self.deleteMarkerButton.clicked.connect(self.delete_nearest_marker)
        
        self.clearMarkersButton = PushButton(tr('reset'))
        self.clearMarkersButton.setStyleSheet(TOOL_BTN_STYLE)
        self.clearMarkersButton.clicked.connect(self.clear_loop_markers)
        
        markerLayout.addWidget(self.smartMarkButton)
        markerLayout.addWidget(self.deleteMarkerButton)
        markerLayout.addWidget(self.clearMarkersButton)
        loopGroup.addLayout(markerLayout)
        
        self.loopFramesLabel = CaptionLabel("[F: 0 - End]")
        self.loopFramesLabel.setStyleSheet("color: #aaa; font-size: 11px; margin-top: 2px;")
        loopGroup.addWidget(self.loopFramesLabel)
        
        self.actionsGrid = QGridLayout()
        self.actionsGrid.setSpacing(8)
        
        self.saveLoopButton = PushButton(tr('save_loop'))
        self.saveLoopButton.setToolTip(tr('save_loop'))
        self.saveLoopButton.clicked.connect(self.save_loop_segment)
        
        self.saveFrameButton = PushButton(tr('save_frame'))
        self.saveFrameButton.setToolTip(tr('save_frame'))
        self.saveFrameButton.clicked.connect(self.save_current_frame)
        
        self.mirrorButton = PushButton(tr('mirror_h'))
        self.mirrorButton.setToolTip(tr('mirror_h'))
        self.mirrorButton.clicked.connect(self.toggle_mirror)
        
        self.mirrorVerticalButton = PushButton(tr('mirror_v'))
        self.mirrorVerticalButton.setToolTip(tr('mirror_v'))
        self.mirrorVerticalButton.clicked.connect(self.toggle_vertical_mirror)
        
        self.rotateButton = PushButton(tr('rotate'))
        self.rotateButton.setToolTip(tr('rotate'))
        self.rotateButton.clicked.connect(self.rotate_video)
        
        # Apply uniform styling and min-width to match drawing tools
        action_btn_style = """
            PushButton {
                font-size: 13px;
                font-weight: 500;
                padding: 6px;
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
            }
            PushButton:hover {
                background: rgba(255, 255, 255, 0.1);
            }
        """
        for btn in [self.saveLoopButton, self.saveFrameButton, self.mirrorButton, 
                    self.mirrorVerticalButton, self.rotateButton]:
            btn.setMinimumWidth(100)
            btn.setStyleSheet(ACTION_BTN_STYLE)
            
        self.actionsGrid.addWidget(self.saveLoopButton, 0, 0)
        self.actionsGrid.addWidget(self.saveFrameButton, 0, 1)
        self.actionsGrid.addWidget(self.mirrorButton, 1, 0)
        self.actionsGrid.addWidget(self.mirrorVerticalButton, 1, 1)
        self.actionsGrid.addWidget(self.rotateButton, 2, 0, 1, 2) # Span across 2 columns
        
        loopGroup.addLayout(self.actionsGrid)
        
        self.settingsInnerLayout.addLayout(loopGroup)
        self.settingsInnerLayout.addWidget(QFrame(frameShape=QFrame.Shape.HLine, frameShadow=QFrame.Shadow.Sunken))
        
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
        
        self.settingsInnerLayout.addStretch(1)
        
        self.globalSettingsButton = PushButton(tr('settings'))
        self.globalSettingsButton.setIcon(FluentIcon.SETTING)
        self.globalSettingsButton.clicked.connect(self.show_global_settings)
        self.globalSettingsButton.setStyleSheet(ACTION_BTN_STYLE)
        self.settingsInnerLayout.addWidget(self.globalSettingsButton)
        
        # Volume (Modified to Flyout)
        self.volumeContainer = QWidget()
        self.volumeContainerLayout = QHBoxLayout(self.volumeContainer)
        self.volumeContainerLayout.setContentsMargins(0, 0, 0, 0)
        self.volumeContainerLayout.setSpacing(5)
        
        self.volumeButton = ToolButton(FluentIcon.VOLUME)
        if self.userMutedIntent:
            self.volumeButton.setIcon(FluentIcon.MUTE)
        self.volumeButton.clicked.connect(self.toggle_mute)
        
        self.volumeValueLabel = CaptionLabel(f"{initial_vol}%")
        if self.userMutedIntent:
            self.volumeValueLabel.setText("0%")
        self.volumeValueLabel.setFixedWidth(40)
        self.volumeValueLabel.setStyleSheet("border: none; background: transparent; color: #ccc; font-size: 12px; hover { color: white; }")
        self.volumeValueLabel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.volumeValueLabel.mousePressEvent = lambda e: self.show_volume_flyout()
        
        self.volumeContainerLayout.addWidget(self.volumeButton)
        self.volumeContainerLayout.addWidget(self.volumeValueLabel)
        self.buttonsLayout.addWidget(self.volumeContainer)
        
        # We still need the internal logic for volume
        self.audioOutput.setVolume(0.7)
        
        self.buttonsLayout.addSpacing(20)
        self.togglePlaylistButton = ToolButton(FluentIcon.MENU)
        self.togglePlaylistButton.setToolTip("Toggle Playlist")
        self.togglePlaylistButton.clicked.connect(self.toggle_playlist)
        self.buttonsLayout.addWidget(self.togglePlaylistButton)
        
        self.toggleDrawingButton = ToolButton(FluentIcon.EDIT)
        self.toggleDrawingButton.setToolTip("Toggle Drawing Panel")
        self.toggleDrawingButton.clicked.connect(self.toggle_drawing_panel)
        self.buttonsLayout.addWidget(self.toggleDrawingButton)
        
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
        
        # Startup Audio Device
        device_id = self.config.get('audio_device', '')
        if device_id:
            for device in QMediaDevices.audioOutputs():
                d_id = device.id().data().decode() if hasattr(device.id(), 'data') else str(device.id())
                if d_id == device_id:
                    self.audioOutput.setDevice(device)
                    break
        
        # Final Text Sync
        self.update_ui_texts()
        
    def open_file(self):
        fileNames, _ = QFileDialog.getOpenFileNames(self, "Add Files", "", 
                                                   "Media Files (*.mp4 *.mkv *.avi *.mov *.jpg *.jpeg *.png *.bmp *.webp *.tiff)")
        if fileNames:
            self.add_files_to_playlist(fileNames)
            if self.mediaPlayer.playbackState() == QMediaPlayer.PlaybackState.StoppedState:
                self.load_video(fileNames[0])

    def add_folder_contents(self, type="video"):
        folder = QFileDialog.getExistingDirectory(self, f"Select {type.capitalize()} Folder")
        if not folder:
            return
            
        if type == "video":
            exts = ('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.m4v')
        else:
            exts = ('.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff')
            
        files = []
        for f in os.listdir(folder):
            if f.lower().endswith(exts):
                files.append(os.path.join(folder, f))
        
        if files:
            self.add_files_to_playlist(sorted(files))
            if self.mediaPlayer.playbackState() == QMediaPlayer.PlaybackState.StoppedState:
                self.load_video(files[0])

    def load_video(self, filePath):
        # Save markers for current video before switching
        self.save_current_markers()
        
        try:
            self.currentFilePath = filePath
            self.zoomSlider.setValue(100)
            self.view.set_scroll_state(0, 0)
            self.last_transform_state = None
            if hasattr(self, 'initial_fit_done'):
                delattr(self, 'initial_fit_done')
            
            # Check if it's an image
            is_image = filePath.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff'))
            
            if is_image:
                self.cleanup_cache()
                self.cached_frame_dict = {0: filePath}
                self.cached_file_path = filePath
                self.current_cache_index = 0
                self.fps = 1.0 
                self.total_frames = 0
                self.sync_progress_bar()
                self.update_pixmap_from_cache()
                self.apply_transformations(fit=True)
                self.mediaPlayer.stop()
                self.setWindowTitle(os.path.basename(filePath))
            else:
                # Video logic
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
                
                self.mediaPlayer.pause()
                self.playButton.setIcon(FluentIcon.PLAY)
                self.playButton.setEnabled(True)
                
                # Start extraction
                self.start_full_extraction()
            
            # Load markers if they exist
            self.load_markers_for_current()
            
        except Exception as e:
            print(f"Error opening file: {e}")

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
                "-of", "json", file_path
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
                cmd_fmt = [ffprobe_path, "-v", "error", "-show_entries", "format=duration", "-of", "json", file_path]
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
                'markers': self.markers,
                'loopMode': self.loopCombo.currentIndex(),
                'speed': self.speedSlider.value(),
                'zoom': self.zoomSlider.value(),
                'scrollX': scroll_x,
                'scrollY': scroll_y,
                'isMirrored': self.isMirrored,
                'rotationAngle': self.rotationAngle,
                'brightness': self.brightnessSlider.value(),
                'contrast': self.contrastSlider.value(),
                'gamma': self.gammaSlider.value(),
                'saturation': self.saturationSlider.value()
            }

    def load_markers_for_current(self):
        if self.currentFilePath in self.playlistData:
            data = self.playlistData[self.currentFilePath]
            self.markers = data.get('markers', [])
            self.markers.sort()
            self.progressBar.update_markers(self.markers)
            
            loop_mode = data.get('loopMode', 3)
            self.loopCombo.setCurrentIndex(loop_mode)
            self.isPingPong = (loop_mode == 3)
            
            # Load speed and zoom
            self.speedSlider.setValue(data.get('speed', 100))
            self.zoomSlider.setValue(data.get('zoom', 100))
            self.view.set_scroll_state(data.get('scrollX', 0), data.get('scrollY', 0))
            self.isMirrored = data.get('isMirrored', False)
            self.rotationAngle = data.get('rotationAngle', 0)
            
            # Load image adjustments
            self.brightnessSlider.setValue(data.get('brightness', 0))
            self.contrastSlider.setValue(data.get('contrast', 100))
            self.gammaSlider.setValue(data.get('gamma', 100))
            self.saturationSlider.setValue(data.get('saturation', 100))
            
            self.apply_transformations(fit=True)
        else:
            self.markers = []
            self.progressBar.update_markers(self.markers)
            if not self.globalLoopToggle.isChecked():
                self.loopCombo.setCurrentIndex(0) # Default None
            self.speedSlider.setValue(100)
            self.reset_adjustments()
            self.apply_transformations(fit=True)
            
        self.update_loop_frames_label()

    def handle_view_drop(self, files):
        if files:
            # Filter for video and image files
            valid_exts = ('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.m4v', '.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff')
            valid_files = [f for f in files if f.lower().endswith(valid_exts)]
            if valid_files:
                self.add_files_to_playlist(valid_files)
                # Load the first one if nothing is playing
                if not self.currentFilePath:
                    self.load_video(valid_files[0])
            
    def add_files_to_playlist(self, file_paths):
        for filePath in file_paths:
            if os.path.isfile(filePath):
                # Create item with placeholder icon
                item = QListWidgetItem(os.path.basename(filePath))
                if self.thumbToggle.isChecked():
                    item.setSizeHint(QSize(120, 130))
                else:
                    item.setSizeHint(QSize(0, 28))
                item.setData(Qt.ItemDataRole.UserRole, filePath)
                # Set a default grey icon while loading
                placeholder = QPixmap(120, 120)
                placeholder.fill(QColor(60, 60, 60))
                item.setIcon(QIcon(placeholder))
                self.playlistList.addItem(item)
                
                # Start thumbnail extraction only if enabled
                if self.thumbToggle.isChecked():
                    thread = ThumbnailThread(filePath, self)
                    thread.finished.connect(self.on_thumbnail_ready)
                    self.thumb_threads.append(thread)
                    thread.start()

    def toggle_drawing_mode(self, checked):
        self.view.set_drawing_mode(checked)

    def toggle_laser_mode(self, checked):
        self.view.laser_mode = checked

    def choose_pen_color(self):
        color = QColorDialog.getColor(self.view.pen_color, self, "Select Color")
        if color.isValid():
            self.view.pen_color = color
            # Just update the background of the tool button subtly or the preview
            self.update_pen_preview()
            # Update cursor color too
            self.set_active_tool(self.view.drawing_tool)

    def update_pen_width(self, val):
        self.view.pen_width = val
        self.penSizeLabel.setText(f"{val} px")
        self.view.update_cursor_size()
        self.update_pen_preview()

    def on_thumbnail_ready(self, filePath, pixmap):
        if not self.thumbToggle.isChecked():
            return
            
        # Find the item in the list and update its icon
        for i in range(self.playlistList.count()):
            item = self.playlistList.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == filePath:
                item.setIcon(QIcon(pixmap))
                break

    def on_thumb_toggle_changed(self, checked):
        # Update current view
        if checked:
            self.playlistList.setIconSize(QSize(120, 120))
            self.playlistList.setSpacing(5)
            # Update all items size and re-generate missing thumbnails
            for i in range(self.playlistList.count()):
                item = self.playlistList.item(i)
                item.setSizeHint(QSize(120, 130))
                filePath = item.data(Qt.ItemDataRole.UserRole)
                # Set placeholder back if needed
                placeholder = QPixmap(120, 120)
                placeholder.fill(QColor(60, 60, 60))
                item.setIcon(QIcon(placeholder))
                
                thread = ThumbnailThread(filePath, self)
                thread.finished.connect(self.on_thumbnail_ready)
                self.thumb_threads.append(thread)
                thread.start()
        else:
            self.playlistList.setIconSize(QSize(0, 0))
            self.playlistList.setSpacing(1)
            # Reset icons to empty and update size hints for compact view
            for i in range(self.playlistList.count()):
                item = self.playlistList.item(i)
                item.setIcon(QIcon())
                item.setSizeHint(QSize(0, 28))

    def create_shape_icon(self, shape_type):
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(Qt.GlobalColor.white, 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        
        if shape_type == 'rect':
            painter.drawRect(5, 5, 22, 22)
        elif shape_type == 'ellipse':
            painter.drawEllipse(5, 5, 22, 22)
        elif shape_type == 'triangle':
            path = QPainterPath()
            path.moveTo(16, 5)
            path.lineTo(27, 27)
            path.lineTo(5, 27)
            path.closeSubpath()
            painter.drawPath(path)
        elif shape_type == 'arrow':
            painter.drawLine(6, 26, 26, 6)
            painter.drawLine(26, 6, 15, 6)
            painter.drawLine(26, 6, 26, 17)
            
        painter.end()
        return QIcon(pixmap)

    def set_active_tool(self, tool_id):
        self.view.drawing_tool = tool_id
        # Explicitly update button highlights because QButtonGroup exclusivity 
        # might not trigger QSS :checked refresh automatically on some platforms
        for btn in self.toolGroup.buttons():
            btn.setProperty('checked', btn.isChecked())
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            
        # Update cursor color based on tool (optional logic)
        if tool_id in ['obj_eraser', 'area_eraser', 'stroke_eraser']:
            self.view.cursor_circle.setBrush(QColor(255, 255, 255, 30))
        else:
            c = self.view.pen_color
            self.view.cursor_circle.setBrush(QColor(c.red(), c.green(), c.blue(), 50))

    def undo_last_stroke(self):
        if self.view.strokes:
            item = self.view.strokes.pop()
            if item.scene():
                self.view.scene().removeItem(item)

    def clear_all_strokes(self):
        for item in self.view.strokes:
            if item.scene():
                self.view.scene().removeItem(item)
        self.view.strokes.clear()

    def save_drawing_screenshot(self):
        if not self.view.pixmapItem.pixmap():
            return
            
        # Get video source rect
        rect = self.view.pixmapItem.pixmap().rect()
        
        # Create a high quality output pixmap
        out_pixmap = QPixmap(rect.size())
        out_pixmap.fill(Qt.GlobalColor.black)
        
        painter = QPainter(out_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        # Render ONLY the scene part that matches the video
        # (This avoids black bars and UI elements)
        self.view.scene().render(painter, QRectF(rect), QRectF(rect))
        painter.end()
        
        filePath, _ = QFileDialog.getSaveFileName(
            self, "Save Screenshot", "boomerang_analysis.png", "PNG file (*.png);;JPG file (*.jpg)"
        )
        if filePath:
            out_pixmap.save(filePath)

    def update_pen_preview(self):
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        color = self.view.pen_color
        # Limit preview radius for display
        r = min(14, self.view.pen_width / 2.0)
        
        # Subtle ring background
        painter.setPen(QPen(QColor(255, 255, 255, 20), 1))
        painter.setBrush(QColor(255, 255, 255, 5))
        painter.drawEllipse(QPointF(16, 16), 15, 15)
        
        # The actual pen thickness
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(16, 16), r, r)
        painter.end()
        
        self.penPreview.setPixmap(pixmap)

    def on_playlist_item_clicked(self, item):
        filePath = item.data(Qt.ItemDataRole.UserRole)
        self.load_video(filePath)

    def show_add_menu(self):
        menu_hint = self.addMenu.sizeHint()
        # Popup above the button
        pos = self.btn_add.mapToGlobal(QPoint(0, -menu_hint.height()))
        self.addMenu.exec(pos)

    def show_sort_menu(self):
        if self.playlistList.count() == 0:
            return
        menu_hint = self.sortMenu.sizeHint()
        pos = self.btn_sort.mapToGlobal(QPoint(0, -menu_hint.height()))
        self.sortMenu.exec(pos)

    def sort_playlist_by(self, criteria):
        items_info = []
        for i in range(self.playlistList.count()):
            item = self.playlistList.item(i)
            path = item.data(Qt.ItemDataRole.UserRole)
            items_info.append({
                'item': item,
                'name': item.text().lower(),
                'date': os.path.getmtime(path) if os.path.exists(path) else 0
            })
            
        if criteria == "name_asc":
            items_info.sort(key=lambda x: x['name'])
        elif criteria == "name_desc":
            items_info.sort(key=lambda x: x['name'], reverse=True)
        elif criteria == "date_newest":
            items_info.sort(key=lambda x: x['date'], reverse=True)
        elif criteria == "date_oldest":
            items_info.sort(key=lambda x: x['date'])
            
        # Take all items out first to avoid deletion on clear
        taken_items = []
        for _ in range(self.playlistList.count()):
            taken_items.append(self.playlistList.takeItem(0))
            
        # Re-add in sorted order
        for info in items_info:
            self.playlistList.addItem(info['item'])

    def remove_from_playlist(self):
        item = self.playlistList.currentItem()
        if item:
            path = item.data(Qt.ItemDataRole.UserRole)
            if path in self.playlistData:
                del self.playlistData[path]
            self.playlistList.takeItem(self.playlistList.row(item))

    def clear_playlist(self):
        self.playlistList.clear()
        self.playlistData = {}
        self.stop_playback()
        self.cleanup_cache()
        self.currentFilePath = None
        self.setWindowTitle("Boomerang Player")
        if hasattr(self, 'pixmapItem'):
            self.pixmapItem.setPixmap(QPixmap())
        self.progressBar.setRange(0, 0)
        self.progressBar.setValue(0)
        self.frameLabel.setText(" [F: 0]")
        self.currentTimeLabel.setText("00:00")
        self.totalTimeLabel.setText("00:00")

    def show_clear_menu(self):
        if self.playlistList.count() == 0:
            return
        menu_hint = self.removeMenu.sizeHint()
        pos = self.btn_clear.mapToGlobal(QPoint(0, -menu_hint.height()))
        self.removeMenu.exec(pos)

    def show_remove_menu(self):
        self.show_clear_menu()

    def toggle_playlist(self):
        is_visible = self.playlistContainer.isVisible()
        if not is_visible:
            self.drawingContainer.hide()
        self.playlistContainer.setVisible(not is_visible)
        
        if not is_visible:
            sizes = self.mainSplitter.sizes()
            if sizes[2] < 250:
                sizes[2] = 250
                self.mainSplitter.setSizes(sizes)

    def toggle_drawing_panel(self):
        is_visible = self.drawingContainer.isVisible()
        if not is_visible:
            self.playlistContainer.hide()
        self.drawingContainer.setVisible(not is_visible)
        
        if not is_visible:
            sizes = self.mainSplitter.sizes()
            if sizes[3] < 250:
                sizes[3] = 250
                self.mainSplitter.setSizes(sizes)

    def toggle_settings(self):
        is_visible = self.settingsContainer.isVisible()
        self.settingsContainer.setVisible(not is_visible)
        
        if not is_visible:
            sizes = self.mainSplitter.sizes()
            if sizes[0] < 250:
                sizes[0] = 250
                self.mainSplitter.setSizes(sizes)

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

    def show_file_info(self):
        if not self.currentFilePath or not os.path.exists(self.currentFilePath):
            return
            
        try:
            ffprobe_path = get_resource_path("ffprobe.exe" if os.name == 'nt' else "ffprobe")
            if not os.path.exists(ffprobe_path):
                ffprobe_path = "ffprobe"
                
            cmd = [
                ffprobe_path, "-v", "error", 
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height,avg_frame_rate,codec_name,pix_fmt",
                "-show_entries", "format=size,duration,format_name",
                "-of", "json", self.currentFilePath
            ]
            
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            result = subprocess.check_output(cmd, creationflags=creationflags).decode('utf-8')
            data = json.loads(result)
            
            stream = data.get('streams', [{}])[0]
            fmt = data.get('format', {})
            
            size_mb = float(fmt.get('size', 0)) / (1024 * 1024)
            res = f"{stream.get('width', '?')}x{stream.get('height', '?')}"
            codec = stream.get('codec_name', 'unknown')
            pix_fmt = stream.get('pix_fmt', 'unknown')
            container = fmt.get('format_name', 'unknown').split(',')[0]
            
            info_text = (
                f"File: {os.path.basename(self.currentFilePath)}\n\n"
                f"Resolution: {res}\n"
                f"Codec: {codec} ({pix_fmt})\n"
                f"Container: {container}\n"
                f"FPS: {float(self.fps):.2f}\n"
                f"Size: {size_mb:.2f} MB\n\n"
                f"Path: {self.currentFilePath}"
            )
            
            w = MessageBox("File Information", info_text, self)
            w.yesButton.setText("OK")
            w.cancelButton.hide()
            w.exec()
            
        except Exception as e:
            print(f"Error getting file info: {e}")

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
        self.needs_range_update = True
        
        # Trigger extraction if frame is missing
        if index not in getattr(self, 'cached_frame_dict', {}):
            self.loadingOverlay.show()
            self.request_frame_extraction(index, force=True)
        else:
            self.update_pixmap_from_cache()
            self.check_sliding_window()
        
        # Update labels (convert frames back to ms for display)
        if self.fps > 0:
            ms = int((index * 1000) / self.fps)
            self.currentTimeLabel.setText(format_time(ms))

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
        max_frame = self.progressBar.maximum() if self.progressBar.maximum() > 0 else 0
        self.current_cache_index = max(0, min(max_frame, self.current_cache_index))
        
        if self.current_cache_index not in getattr(self, 'cached_frame_dict', {}):
            self.loadingOverlay.show()
            self.request_frame_extraction(self.current_cache_index, force=True)
            return
            
        self.update_pixmap_from_cache()
        self.check_sliding_window()

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
            self.total_frames = int((duration / 1000.0) * self.fps)
            self.totalTimeLabel.setText(format_time(duration))
            self.sync_progress_bar()
            
            # Re-validate existing markers against new duration
            last_valid_frame = max(0, self.total_frames - 1)
            self.markers = [m for m in self.markers if m <= last_valid_frame]
            self.progressBar.update_markers(self.markers)
            self.update_loop_frames_label()
        
    def set_volume(self, volume):
        self.audioOutput.setVolume(volume / 100.0)
        if self.volume_ctrl:
            try:
                self.volume_ctrl.SetMasterVolumeLevelScalar(volume / 100.0, None)
            except Exception as e:
                print(f"Runtime volume sync error: {e}")
                
        self.volumeValueLabel.setText(f"{volume}%")
        is_muted = volume == 0
        self.userMutedIntent = is_muted
        if self.volume_ctrl:
            try:
                self.volume_ctrl.SetMute(is_muted, None)
            except:
                pass
        self.volumeButton.setIcon(FluentIcon.MUTE if is_muted else FluentIcon.VOLUME)
        
    def show_volume_flyout(self):
        # Create a custom popup frame to avoid the default Flyout border
        self.volumePopup = QFrame(None, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.volumePopup.setObjectName("volumePopup")
        self.volumePopup.setStyleSheet("""
            #volumePopup { 
                background: #1e1e1e; 
                border: 1px solid #333; 
                border-radius: 8px;
            }
        """)
        layout = QVBoxLayout(self.volumePopup)
        layout.setContentsMargins(10, 15, 10, 15)
        
        slider = QSlider(Qt.Orientation.Vertical)
        slider.setRange(0, 100)
        
        current_vol = 50
        if self.volume_ctrl:
            try:
                current_vol = int(self.volume_ctrl.GetMasterVolumeLevelScalar() * 100)
            except:
                pass
        else:
            current_vol = int(self.audioOutput.volume() * 100)
            
        slider.setValue(current_vol)
        slider.setFixedHeight(150)
        slider.setStyleSheet(FLUENT_SLIDER_STYLE)
        slider.valueChanged.connect(self.set_volume)
        
        layout.addWidget(slider, 0, Qt.AlignmentFlag.AlignCenter)
        
        # Position accurately above the value label
        self.volumePopup.adjustSize()
        global_pos = self.volumeValueLabel.mapToGlobal(QPoint(0, 0))
        x = global_pos.x() + (self.volumeValueLabel.width() - self.volumePopup.width()) // 2
        y = global_pos.y() - self.volumePopup.height() - 8
        
        self.volumePopup.move(x, y)
        self.volumePopup.show()
        
    def toggle_mute(self):
        # Mute logic now handled by slider reaching 0, 
        # but if we want a separate mute toggle:
        is_muted = not self.audioOutput.isMuted()
        self.audioOutput.setMuted(is_muted)
        self.userMutedIntent = is_muted
        
        if self.volume_ctrl:
            try:
                self.volume_ctrl.SetMute(is_muted, None)
            except:
                pass
                
        self.volumeButton.setIcon(FluentIcon.MUTE if is_muted else FluentIcon.VOLUME)
        if is_muted:
            self.volumeValueLabel.setText("0%")
        else:
            vol = int(self.audioOutput.volume() * 100)
            self.volumeValueLabel.setText(f"{vol}%")
        
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
        if index == 2: # Backward
            self.isForward = False
        else:
            # Default to forward for None (0) and Forward (1)
            self.isForward = True
        
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
        
        # Anchor slider zoom to center to avoid jumping towards the mouse on the sidebar
        self.view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.view.scale(factor, factor)
        self.view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        
        self.view.zoomLevel = self.zoomLevel
        self.zoomValueLabel.setText(f"{snapped}%")
        
    def sync_zoom_ui(self, zoom_level):
        self.zoomLevel = zoom_level
        val = int(zoom_level * 100)
        # Use singleShot to ensure the UI updates correctly in the next event loop cycle
        QTimer.singleShot(0, lambda: self._apply_sync_zoom(val))

    def toggle_mirror(self):
        self.isMirrored = not self.isMirrored
        self.apply_transformations(fit=True)
        self.save_current_markers()

    def toggle_vertical_mirror(self):
        self.isMirroredVertical = not self.isMirroredVertical
        self.apply_transformations(fit=True)
        self.save_current_markers()

    def rotate_video(self):
        self.rotationAngle = (self.rotationAngle + 90) % 360
        self.apply_transformations(fit=True)
        self.save_current_markers()

    def apply_transformations(self, fit=False):
        if not hasattr(self, 'pixmapItem') or self.pixmapItem is None:
            return
            
        pix = self.pixmapItem.pixmap()
        if pix.isNull():
            return
            
        # We will apply all transformations (mirror, rotate) around the center of the pixmap
        cx = pix.width() / 2.0
        cy = pix.height() / 2.0
        
        transform = QTransform()
        
        # 1. Translate center to origin
        transform.translate(cx, cy)
        
        # 2. Apply mirroring
        if self.isMirrored:
            transform.scale(-1, 1)
        if self.isMirroredVertical:
            transform.scale(1, -1)
            
        # 3. Apply rotation
        if self.rotationAngle != 0:
            transform.rotate(self.rotationAngle)
            
        # 4. Translate back
        transform.translate(-cx, -cy)
        
        if not hasattr(self, 'last_applied_transform') or self.last_applied_transform != transform:
            self.pixmapItem.setTransform(transform)
            self.last_applied_transform = transform
        
        # Update scene rect and center if requested
        if hasattr(self, 'view') and self.view:
            # Only update scene rect if dimensions or rotation changed to prevent jumping
            current_state = (pix.width(), pix.height(), self.rotationAngle, self.isMirrored, self.isMirroredVertical)
            if current_state != self.last_transform_state:
                self.last_transform_state = current_state
                # Ensure scene rect is large enough for rotated item
                max_dim = max(pix.width(), pix.height()) * 2
                self.view.setSceneRect(-max_dim, -max_dim, max_dim * 4, max_dim * 4)
            
            if fit:
                self.view.fitInView(self.pixmapItem, Qt.AspectRatioMode.KeepAspectRatio)
                self.view.zoomLevel = 1.0
                self.sync_zoom_ui(1.0)
            
    def handle_status_change(self, status):
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            # Metadata is now primarily handled by ffprobe in load_video
            # but we still check handle_metadata_change as a fallback
            self.handle_metadata_change()
            
            # Adjust video item size and center it
            # ONLY fit if we don't have a transform state yet (i.e. first load)
            if self.view and self.pixmapItem and self.last_transform_state is None:
                self.apply_transformations(fit=True)


    def update_loop_frames_label(self):
        if not self.currentFilePath:
            return
            
        start_f, end_f = self.get_active_loop_range()
        self.loopFramesLabel.setText(f"[F: {start_f} - {end_f}]")

    def get_active_loop_range(self):
        if not self.currentFilePath or self.total_frames <= 0:
            return 0, 0
            
        f = int(self.current_cache_index)
        last_frame = max(0, self.total_frames - 1)
        valid_markers = [int(m) for m in self.markers if 0 < m < last_frame]
        full_markers = sorted(list(set([0, last_frame] + valid_markers)))
        
        import bisect
        # Use different bisect logic based on direction to prevent "leaking" through markers
        # When moving forward, we stay in the left segment until f > marker.
        # When moving backward, we stay in the right segment until f < marker.
        if getattr(self, 'isForward', True):
            idx = bisect.bisect_left(full_markers, f)
        else:
            idx = bisect.bisect_right(full_markers, f)
        
        if idx == 0:
            start_frame = full_markers[0]
            end_frame = full_markers[1] if len(full_markers) > 1 else full_markers[0]
        elif idx >= len(full_markers):
            start_frame = full_markers[-2] if len(full_markers) > 1 else 0
            end_frame = full_markers[-1]
        else:
            start_frame = full_markers[idx-1]
            end_frame = full_markers[idx]
                
        return start_frame, end_frame

    def add_smart_marker(self):
        f = self.current_cache_index
        if f not in self.markers:
            self.markers.append(f)
            self.markers.sort()
            
        self.needs_range_update = True
        self.progressBar.update_markers(self.markers)
        self.update_loop_frames_label()
        self.save_current_markers()

    def delete_nearest_marker(self):
        if not self.markers:
            return
            
        f = self.current_cache_index
        # Find closest marker
        closest = min(self.markers, key=lambda m: abs(m - f))
        # Only delete if it's reasonably close? No, user said "delete nearest"
        self.markers.remove(closest)
        
        self.needs_range_update = True
        self.progressBar.update_markers(self.markers)
        self.update_loop_frames_label()
        self.save_current_markers()

    def clear_loop_markers(self):
        self.markers = []
        self.progressBar.update_markers(self.markers)
        self.update_loop_frames_label()
        self.save_current_markers()

    def save_current_frame(self):
        if self.current_cache_index not in getattr(self, 'cached_frame_dict', {}):
            return
            
        fileName, _ = QFileDialog.getSaveFileName(self, "Save Frame", "", "PNG Image (*.png)")
        if fileName:
            img = QImage(self.cached_frame_dict[self.current_cache_index])
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

    def keyPressEvent(self, event):
        key = event.key()
        
        # Ignore if we are typing in a text item (if any)
        if isinstance(self.focusWidget(), (qfluentwidgets.LineEdit, qfluentwidgets.TextEdit)):
            super().keyPressEvent(event)
            return

        # Find action for this key
        action = None
        for act, k in self.shortcuts.items():
            if k == key:
                action = act
                break
        
        if action == 'play_pause':
            self.play_pause()
        elif action == 'set_loop_start':
            self.add_smart_marker() # Actually set_loop_start logic? The current player uses markers.
            # Wait, the player uses a MarkerSlider and markers list.
            # In get_active_loop_range it finds the segment containing current_cache_index.
            # Adding a marker effectively splits a segment.
            self.add_smart_marker()
        elif action == 'set_loop_end':
            # Similar to set_loop_start in this marker-based system
            self.add_smart_marker()
        elif action == 'toggle_loop':
            current = self.loopCombo.currentIndex()
            new_idx = 0 if current != 0 else 3 # Toggle between None and Ping-pong
            self.loopCombo.setCurrentIndex(new_idx)
        elif action == 'next_frame':
            self.step_frame(1)
        elif action == 'prev_frame':
            self.step_frame(-1)
        elif action == 'toggle_mute':
            self.toggle_mute()
        else:
            super().keyPressEvent(event)

    def show_global_settings(self):
        dialog = SettingsDialog(self.config, self)
        if dialog.exec():
            # Reload config and update UI
            self.config = load_config()
            set_lang(self.config.get('language', 'en'))
            self.shortcuts = self.config.get('shortcuts', {})
            
            # Update audio device
            device_id = self.config.get('audio_device', '')
            if device_id:
                for device in QMediaDevices.audioOutputs():
                    d_id = device.id().data().decode() if hasattr(device.id(), 'data') else str(device.id())
                    if d_id == device_id:
                        self.audioOutput.setDevice(device)
                        break
            
            # Restart the app or update all strings?
            # Since the app is complex, I'll update the strings manually or tell the user to restart.
            # But I should try to update the main ones.
            self.update_ui_texts()

    def update_ui_texts(self):
        self.playlistLabel.setText(tr('playlist'))
        self.thumbLabel.setText(tr('show_thumbnails'))
        self.btn_add.setText(tr('add'))
        self.btn_sort.setText(tr('sort'))
        self.btn_save.setText(tr('save'))
        self.btn_clear.setText(tr('clear'))
        self.drawingSidebarTitle.setText(tr('drawing_settings'))
        self.drawModeToggleLabel.setText(tr('drawing_mode'))
        self.laserModeToggleLabel.setText(tr('laser_mode'))
        self.penSizeLabel.setText(f"{self.penSizeSlider.value()} px")
        self.penColorBtn.setText(tr('color'))
        self.saveScreenshotBtn.setText(tr('save_screenshot'))
        self.sidebarUndoBtn.setText(tr('undo'))
        self.sidebarClearBtn.setText(tr('clear'))
        self.settingsTitle.setText(tr('video_settings'))
        self.speedLabel.setText(tr('playback_speed'))
        self.zoomLabel.setText(tr('zoom'))
        self.adjLabel.setText(tr('image_adjustments'))
        self.resetAdjButton.setText(tr('reset_image'))
        self.infoButton.setText(tr('file_info'))
        self.loopLabel.setText(tr('global_loop_mode'))
        self.navLabel.setText(tr('zoom_nav_bar'))
        self.smartMarkButton.setText(tr('mark'))
        self.deleteMarkerButton.setText(tr('delete'))
        self.clearMarkersButton.setText(tr('reset'))
        self.saveLoopButton.setText(tr('save_loop'))
        self.saveFrameButton.setText(tr('save_frame'))
        self.mirrorButton.setText(tr('mirror_h'))
        self.mirrorVerticalButton.setText(tr('mirror_v'))
        self.rotateButton.setText(tr('rotate'))
        self.globalSettingsButton.setText(tr('settings'))
        self.loadingOverlay.setText(tr('caching_ram'))
        
        # Tooltips
        self.btn_add.setToolTip(tr('tip_add'))
        self.btn_sort.setToolTip(tr('tip_sort'))
        self.btn_save.setToolTip(tr('tip_save'))
        self.btn_clear.setToolTip(tr('tip_clear'))
        self.thumbToggle.setToolTip(tr('tip_thumbnails'))
        self.saveScreenshotBtn.setToolTip(tr('tip_screenshot'))
        self.sidebarUndoBtn.setToolTip(tr('tip_undo'))
        self.sidebarClearBtn.setToolTip(tr('tip_clear_draw'))
        self.toggleSettingsButton.setToolTip(tr('tip_settings'))
        self.stepBackButton.setToolTip(tr('tip_prev_frame'))
        self.playButton.setToolTip(tr('tip_play_pause'))
        self.stepForwardButton.setToolTip(tr('tip_next_frame'))
        self.volumeButton.setToolTip(tr('tip_mute'))
        
        # Loop combo items (need to clear and re-add or just update)
        self.loopCombo.blockSignals(True)
        current_idx = self.loopCombo.currentIndex()
        self.loopCombo.clear()
        self.loopCombo.addItems([tr('loop_none'), tr('loop_forward'), tr('loop_backward'), tr('loop_pingpong')])
        self.loopCombo.setCurrentIndex(current_idx)
        self.loopCombo.blockSignals(False)
        
        # Menu actions (re-creating or re-setting text)
        self.addMenu.clear()
        self.addMenu.addAction(tr('add'), self.open_file)
        self.addMenu.addAction("Add video folder", lambda: self.add_folder_contents(type="video"))
        self.addMenu.addAction("Add image folder", lambda: self.add_folder_contents(type="image"))
        self.addMenu.addSeparator()
        self.addMenu.addAction("Load playlist", self.load_playlist_from_file)
        
        self.sortMenu.clear()
        self.sortMenu.addAction("Name (A-Z)", lambda: self.sort_playlist_by("name_asc"))
        self.sortMenu.addAction("Name (Z-A)", lambda: self.sort_playlist_by("name_desc"))
        self.sortMenu.addAction("Date (Newest)", lambda: self.sort_playlist_by("date_newest"))
        self.sortMenu.addAction("Date (Oldest)", lambda: self.sort_playlist_by("date_oldest"))
        
        self.removeMenu.clear()
        self.removeMenu.addAction("Remove selected", self.remove_from_playlist)
        self.removeMenu.addAction(tr('clear') + " all", self.clear_playlist)

