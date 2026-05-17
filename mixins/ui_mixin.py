"""
UIMixin — top-level init_ui orchestrator, playlist sidebar, drawing sidebar,
          controls bar, keyboard events.
"""

from PyQt6.QtCore import Qt, QSize, QPoint
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFrame,
                              QSplitter, QLabel, QGridLayout,
                              QGraphicsScene, QGraphicsPixmapItem, QGraphicsView)
from qfluentwidgets import (FluentIcon, ToolButton, CardWidget, CaptionLabel,
                             SwitchButton, PushButton)
from components import DropListWidget, MarkerSlider, ZoomView, GPUPixmapItem
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from styles import (FLUENT_SLIDER_STYLE, COMPACT_BTN_STYLE, MENU_STYLE,
                    ACTION_BTN_STYLE, TOOL_BTN_STYLE)
from translations import tr
from PyQt6.QtWidgets import QMenu, QButtonGroup, QSlider
from PyQt6.QtMultimedia import QMediaDevices
import qfluentwidgets
import ctypes
from ctypes import wintypes


class UIMixin:

    def init_ui(self):
        # Main interface widget
        self.playerInterface = QWidget()
        self.playerLayout = QVBoxLayout(self.playerInterface)
        self.playerLayout.setContentsMargins(0, 0, 0, 0)
        self.playerLayout.setSpacing(0)

        self.mainSplitter = QSplitter(Qt.Orientation.Horizontal)
        self.mainSplitter.setHandleWidth(1)
        self.mainSplitter.setStyleSheet("QSplitter::handle { background: transparent; }")

        self.scene = QGraphicsScene()
        self.view = ZoomView(self.scene, self.playerInterface)
        self.view.filesDropped.connect(self.handle_view_drop)
        self.view.zoomChanged.connect(self.on_user_zoom_changed)
        self.view.setStyleSheet("border: none; background: black;")

        # Build all sidebars (mixin methods)
        self.init_global_settings_sidebar()
        self.init_video_settings_sidebar()
        self._init_playlist_sidebar()
        self._init_drawing_sidebar()

        self.mainSplitter.addWidget(self.globalSettingsContainer)
        self.mainSplitter.addWidget(self.settingsContainer)
        self.mainSplitter.addWidget(self.view)
        self.mainSplitter.addWidget(self.playlistContainer)
        self.mainSplitter.addWidget(self.drawingContainer)
        self.mainSplitter.setStretchFactor(2, 1)
        self.mainSplitter.setSizes([0, 0, 10000, 250, 0])

        self.playerLayout.addWidget(self.mainSplitter, stretch=1)

        # Pen preview (needs to happen after drawing sidebar is built)
        self.update_pen_preview()

        self.pixmapItem = GPUPixmapItem()
        self.update_gpu_state()
        self.scene.addItem(self.pixmapItem)

        # Loading overlay
        self.loadingOverlay = QLabel(tr('caching'), self.view)
        self.loadingOverlay.setStyleSheet(
            "background: rgba(0,0,0,180); color: white; font-size: 24px; "
            "font-weight: bold; border-radius: 10px;"
        )
        self.loadingOverlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loadingOverlay.hide()

        # Controls card
        self._init_controls_card()

        self.playerLayout.addWidget(self.controlsCard, stretch=0)
        self.playerLayout.setContentsMargins(0, 0, 0, 0)

        # Register with FluentWindow
        self.playerInterface.setObjectName("playerInterface")
        self.stackedWidget.addWidget(self.playerInterface)
        self.stackedWidget.setCurrentWidget(self.playerInterface)
        self.navigationInterface.hide()
        self.navigationInterface.setFixedWidth(0)
        self.stackedWidget.setContentsMargins(0, 0, 0, 0)
        self.hBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.hBoxLayout.setSpacing(0)
        self.playerLayout.setContentsMargins(0, 0, 0, 0)
        self.playerLayout.setSpacing(0)

        # Startup audio device
        device_id = self.config.get('audio_device', '')
        if device_id:
            for device in QMediaDevices.audioOutputs():
                d_id = (device.id().data().decode()
                        if hasattr(device.id(), 'data') else str(device.id()))
                if d_id == device_id:
                    self.audioOutput.setDevice(device)
                    break

        self.refresh_custom_styles()
        self.update_ui_texts()
        self.is_full_screen = False
        self.sidebar_states_before_fs = {}
        self.setup_shortcuts()

    def update_gpu_state(self):
        if hasattr(self, 'view') and hasattr(self, 'pixmapItem'):
            enabled = self.config.get('gpu_acceleration', False)
            
            # Switch viewport dynamically
            if enabled:
                if not isinstance(self.view.viewport(), QOpenGLWidget):
                    gl_v = QOpenGLWidget()
                    gl_v.setAutoFillBackground(True)
                    # Force full viewport update to prevent "ghosting" / leaving previous frames
                    self.view.setViewport(gl_v)
                    self.scene.setBackgroundBrush(Qt.GlobalColor.black)
                    self.view.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
            else:
                if isinstance(self.view.viewport(), QOpenGLWidget):
                    from PyQt6.QtWidgets import QWidget
                    self.view.setViewport(QWidget())
                    self.view.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.MinimalViewportUpdate)
            
            self.pixmapItem.gpu_enabled = enabled
            self.pixmapItem.update()

    def refresh_custom_styles(self, accent_color=None, bg_color=None):
        """Updates all custom styled components when accent or background color changes."""
        if not accent_color:
            accent_color = self.config.get('accent_color', '#00f2ff')
        if not bg_color:
            bg_color = self.config.get('bg_color', '#202020')

        from styles import get_styles
        s = get_styles(accent_color, bg_color)

        # Update main UI elements
        sliders = ['progressBar', 'penSizeSlider', 'speedSlider', 'zoomSlider', 'cacheSlider', 
                   'brightnessSlider', 'contrastSlider', 'gammaSlider', 'saturationSlider']
        for slider_name in sliders:
            if hasattr(self, slider_name):
                slider = getattr(self, slider_name)
                slider.setStyleSheet(s['FLUENT_SLIDER_STYLE'])
        
        # Tool buttons
        tool_btns = ['penTool', 'lineTool', 'arrowTool', 'textTool', 'rectTool', 
                     'ellipseTool', 'triangleTool', 'objEraserTool', 'areaEraserTool', 'measureTool']
        for btn_name in tool_btns:
            if hasattr(self, btn_name):
                btn = getattr(self, btn_name)
                btn.setStyleSheet(s['TOOL_BTN_STYLE'])
        
        # Action buttons
        action_btns = ['saveScreenshotBtn', 'sidebarUndoBtn', 'sidebarClearBtn', 'gsSaveBtn']
        for btn_name in action_btns:
            if hasattr(self, btn_name):
                btn = getattr(self, btn_name)
                btn.setStyleSheet(s['ACTION_BTN_STYLE'])

        # Menus
        menus = ['addMenu', 'sortMenu', 'removeMenu']
        for menu_name in menus:
            if hasattr(self, menu_name):
                menu = getattr(self, menu_name)
                menu.setStyleSheet(s['MENU_STYLE'])

        # Playback buttons
        pb_btns = ['stepBackButton', 'playBackwardButton', 'playButton', 'stepForwardButton']
        for btn_name in pb_btns:
            if hasattr(self, btn_name):
                btn = getattr(self, btn_name)
                # COMPACT_BTN_STYLE needs specific rounding for ends
                style = s['COMPACT_BTN_STYLE']
                if btn_name == 'stepBackButton':
                    style += "ToolButton { border-top-left-radius: 4px; border-bottom-left-radius: 4px; }"
                elif btn_name == 'stepForwardButton':
                    style += "ToolButton { border-right: 1px solid rgba(255,255,255,0.08); border-top-right-radius: 4px; border-bottom-right-radius: 4px; }"
                btn.setStyleSheet(style)

        # Update palette border in drawing mixin if it exists
        if hasattr(self, 'paletteButtons') and hasattr(self, 'update_palette_ui'):
            self.update_palette_ui()

        # Update ComboBox
        if hasattr(self, 'loopCombo'):
            self.loopCombo.setStyleSheet(s['COMBO_STYLE'])

        # Update SwitchButtons
        switches = ['loopToggle', 'globalLoopToggle', 'navToggle', 'gsGPUToggle', 'thumbToggle', 'laserModeToggle']
        for sw_name in switches:
            if hasattr(self, sw_name):
                sw = getattr(self, sw_name)
                # Apply SWITCH_STYLE
                sw.setStyleSheet(s['SWITCH_STYLE'])

        # Update Global Settings Trigger buttons
        gs_btns = ['gsLangBtn', 'gsAudioBtn', 'gsAccentBtn']
        for btn_name in gs_btns:
            if hasattr(self, btn_name):
                btn = getattr(self, btn_name)
                btn.setStyleSheet(s['TRIGGER_STYLE'])

        # Update pen color label
        if hasattr(self, 'penSizeLabel'):
            self.penSizeLabel.setStyleSheet(
                "color: white; font-size: 13px; font-weight: 500; "
                "background: transparent; border: none !important;"
            )

        # Update Sidebar Titles and Category Labels
        titles = ['settingsTitle', 'globalSettingsTitle', 'drawingSidebarTitle']
        for t_name in titles:
            if hasattr(self, t_name):
                getattr(self, t_name).setStyleSheet(s['TITLE_STYLE'])
        
        captions = ['gsGeneralLabel', 'gsShortcutsLabel']
        for c_name in captions:
            if hasattr(self, c_name):
                getattr(self, c_name).setStyleSheet(s['CAPTION_STYLE'])

        # Update Background Colors
        bg_style = f"background-color: {bg_color}; border: none;"
        
        # Main window (PlayerWindow)
        self.setStyleSheet(f"PlayerWindow {{ background-color: {bg_color}; }}")
        
        # Title bar
        if hasattr(self, 'titleBar'):
            self.titleBar.setStyleSheet(f"background-color: {bg_color}; border: none;")
            
        # Controls card (Footer)
        if hasattr(self, 'controlsCard'):
            self.controlsCard.setStyleSheet(bg_style)
            
        # Sidebars
        sidebar_containers = ['settingsContainer', 'globalSettingsContainer', 
                              'drawingContainer', 'playlistContainer']
        for container_name in sidebar_containers:
            if hasattr(self, container_name):
                getattr(self, container_name).setStyleSheet(bg_style)
                
        # Drawing scroll area and widget
        if hasattr(self, 'drawingScrollWidget'):
            self.drawingScrollWidget.setStyleSheet("background: transparent;")
        if hasattr(self, 'drawingScrollArea'):
            self.drawingScrollArea.setStyleSheet("background: transparent; border: none;")
            
        # Settings scroll widget
        if hasattr(self, 'settingsScrollWidget'):
            self.settingsScrollWidget.setStyleSheet("background: transparent;")
        if hasattr(self, 'gsScrollWidget'):
            self.gsScrollWidget.setStyleSheet("background: transparent;")

    # ------------------------------------------------------------------ #
    # Playlist sidebar                                                     #
    # ------------------------------------------------------------------ #

    def _init_playlist_sidebar(self):
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
        self.playlistList.setStyleSheet(
            "QListWidget { border: none; background: transparent; } "
            "QScrollBar:vertical { width: 0px; }"
        )
        self.playlistList.setIconSize(QSize(120, 120))
        self.playlistList.itemDoubleClicked.connect(self.on_playlist_item_clicked)
        self.playlistList.itemRightClicked.connect(self.show_playlist_context_menu)
        self.playlistList.filesDropped.connect(self.add_files_to_playlist)
        self.playlistLayout.addWidget(self.playlistList)

        self.thumb_threads = []
        self.thumb_queue = []
        self.MAX_THUMB_THREADS = 2

        self.playlistButtonsGrid = QGridLayout()
        self.playlistButtonsGrid.setSpacing(8)

        self.btn_add = PushButton(tr('add'))
        self.btn_add.setToolTip(tr('tip_add'))
        self.addMenu = QMenu(self)
        self.addMenu.setStyleSheet(MENU_STYLE)
        self.addMenu.addAction(tr('add_media'), self.open_file)
        self.addMenu.addAction(tr('add_video_folder'), lambda: self.add_folder_contents(type="video"))
        self.addMenu.addAction(tr('add_image_folder'), lambda: self.add_folder_contents(type="image"))
        self.btn_add.clicked.connect(self.show_add_menu)

        self.btn_sort = PushButton(tr('sort'))
        self.btn_sort.setToolTip(tr('tip_sort'))
        self.sortMenu = QMenu(self)
        self.sortMenu.setStyleSheet(MENU_STYLE)
        self.sortMenu.addAction(tr('sort_name_asc'),    lambda: self.sort_playlist_by("name_asc"))
        self.sortMenu.addAction(tr('sort_name_desc'),   lambda: self.sort_playlist_by("name_desc"))
        self.sortMenu.addAction(tr('sort_date_newest'), lambda: self.sort_playlist_by("date_newest"))
        self.sortMenu.addAction(tr('sort_date_oldest'), lambda: self.sort_playlist_by("date_oldest"))
        self.btn_sort.clicked.connect(self.show_sort_menu)

        self.btn_save = PushButton(tr('save'))
        self.btn_save.setToolTip(tr('tip_save'))
        self.btn_save.clicked.connect(self.save_playlist_to_file)

        self.btn_clear = PushButton(tr('clear'))
        self.btn_clear.setToolTip(tr('tip_clear'))
        self.removeMenu = QMenu(self)
        self.removeMenu.setStyleSheet(MENU_STYLE)
        self.removeMenu.addAction(tr('remove_selected'), self.remove_from_playlist)
        self.removeMenu.addAction(tr('clear_all'),       self.clear_playlist)
        self.btn_clear.clicked.connect(self.show_clear_menu)

        self.playlistButtonsGrid.addWidget(self.btn_add,   0, 0)
        self.playlistButtonsGrid.addWidget(self.btn_sort,  0, 1)
        self.playlistButtonsGrid.addWidget(self.btn_save,  1, 0)
        self.playlistButtonsGrid.addWidget(self.btn_clear, 1, 1)
        self.playlistLayout.addLayout(self.playlistButtonsGrid)
        self.playlistLayout.setContentsMargins(10, 10, 4, 10)

    # ------------------------------------------------------------------ #
    # Drawing sidebar                                                      #
    # ------------------------------------------------------------------ #

    def _init_drawing_sidebar(self):
        self.drawingContainer = QFrame()
        self.drawingContainer.setMinimumWidth(250)
        self.drawingContainer.setStyleSheet(
            "background: #202020; border: none; QScrollBar { width: 0px; height: 0px; }"
        )
        self.drawingSidebarLayout = QVBoxLayout(self.drawingContainer)
        self.drawingSidebarLayout.setContentsMargins(10, 10, 4, 10)
        self.drawingSidebarLayout.setSpacing(6)

        self.drawingSidebarTitle = CaptionLabel(tr('drawing_settings'))
        self.drawingSidebarTitle.setStyleSheet("font-size: 16px; font-weight: bold; color: white;")
        self.drawingSidebarLayout.addWidget(self.drawingSidebarTitle)

        drawModeToggleLayout = QHBoxLayout()
        self.drawModeToggleLabel = QLabel(tr('drawing_mode'))
        self.drawModeToggleLabel.setStyleSheet("color: white; font-size: 13px;")
        self.drawModeToggle = SwitchButton()
        self.drawModeToggle.checkedChanged.connect(self.toggle_drawing_mode)
        drawModeToggleLayout.addWidget(self.drawModeToggleLabel)
        drawModeToggleLayout.addStretch(1)
        drawModeToggleLayout.addWidget(self.drawModeToggle)
        self.drawingSidebarLayout.addLayout(drawModeToggleLayout)

        laserModeToggleLayout = QHBoxLayout()
        self.laserModeToggleLabel = QLabel(tr('laser_mode'))
        self.laserModeToggleLabel.setStyleSheet("color: white; font-size: 13px;")
        self.laserModeToggle = SwitchButton()
        self.laserModeToggle.checkedChanged.connect(self.toggle_laser_mode)
        laserModeToggleLayout.addWidget(self.laserModeToggleLabel)
        laserModeToggleLayout.addStretch(1)
        laserModeToggleLayout.addWidget(self.laserModeToggle)
        self.drawingSidebarLayout.addLayout(laserModeToggleLayout)

        toolsLayout = QGridLayout()
        toolsLayout.setSpacing(8)
        self.toolGroup = QButtonGroup(self)
        self.toolGroup.setExclusive(True)

        all_tools = [
            (tr('pen'),          'pen',          tr('tip_pen')),
            (tr('line'),         'line',         tr('tip_line')),
            (tr('arrow'),        'arrow',        tr('tip_arrow')),
            (tr('text'),         'text',         tr('tip_text')),
            (tr('rect'),         'rect',         tr('tip_rect')),
            (tr('ellipse'),      'ellipse',      tr('tip_ellipse')),
            (tr('triangle'),     'triangle',     tr('tip_triangle')),
            (tr('measure'),      'measure',      tr('tip_measure')),
            (tr('obj_eraser'),   'obj_eraser',   tr('tip_obj_eraser')),
            (tr('area_eraser'),  'area_eraser',  tr('tip_area_eraser')),
        ]

        for i, (label, tool_id, tip) in enumerate(all_tools):
            btn = PushButton(label)
            btn.setFixedSize(115, 38)
            btn.setToolTip(tip)
            btn.setStyleSheet(TOOL_BTN_STYLE)
            btn.setCheckable(True)

            if tool_id == 'pen':
                btn.setChecked(True)
                self.penTool = btn
            elif tool_id == 'line':          self.lineTool = btn
            elif tool_id == 'arrow':         self.arrowTool = btn
            elif tool_id == 'text':          self.textTool = btn
            elif tool_id == 'rect':          self.rectTool = btn
            elif tool_id == 'ellipse':       self.ellipseTool = btn
            elif tool_id == 'triangle':      self.triangleTool = btn
            elif tool_id == 'obj_eraser':    self.objEraserTool = btn
            elif tool_id == 'area_eraser':   self.areaEraserTool = btn
            elif tool_id == 'measure':       self.measureTool = btn

            self.toolGroup.addButton(btn)
            btn.clicked.connect(lambda checked, t=tool_id: self.set_active_tool(t))
            toolsLayout.addWidget(btn, i // 2, i % 2)

        self.drawingSidebarLayout.addLayout(toolsLayout)
        self.drawingSidebarLayout.addSpacing(15)

        # ---- Quick Palette ----
        self.paletteTitle = CaptionLabel(tr('color_palette'))
        self.drawingSidebarLayout.addWidget(self.paletteTitle)
        
        paletteLayout = QHBoxLayout()
        paletteLayout.setSpacing(8)
        self.paletteButtons = []
        palette = self.config.get('palette', ['#000000', '#FFFFFF', '#FF0000', '#FFFF00', '#00FF00', '#0000FF'])
        active_idx = self.config.get('active_color_index', 2)
        
        for i, color_hex in enumerate(palette):
            p_btn = ToolButton()
            p_btn.setFixedSize(28, 28)
            p_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            p_btn.setProperty('color_idx', i)
            p_btn.clicked.connect(self.select_palette_color)
            self.paletteButtons.append(p_btn)
            paletteLayout.addWidget(p_btn)
            
        self.drawingSidebarLayout.addLayout(paletteLayout)
        self.update_palette_ui()
        self.drawingSidebarLayout.addSpacing(15)

        # Thickness row
        thicknessRow = QHBoxLayout()
        self.penPreview = QLabel()
        self.penPreview.setFixedSize(30, 30)
        self.penPreview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.penPreview.setStyleSheet("background: transparent; border: none !important;")
        thicknessRow.addWidget(self.penPreview)

        self.penSizeLabel = QLabel("3 px")
        self.penSizeLabel.setStyleSheet(
            "color: white; font-size: 13px; font-weight: 500; "
            "background: transparent; border: none !important;"
        )
        thicknessRow.addWidget(self.penSizeLabel)
        thicknessRow.addStretch(1)

        self.penColorBtn = PushButton(tr('color'))
        self.penColorBtn.setFixedSize(70, 32)
        self.penColorBtn.setStyleSheet("""
            PushButton {
                font-size: 14px; font-weight: 500;
                background: rgba(255,255,255,0.08);
                border: 1px solid rgba(255,255,255,0.15);
                border-radius: 4px;
            }
            PushButton:hover { background: rgba(255,255,255,0.15); }
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

        # Action grid
        drawingActionsGrid = QGridLayout()
        drawingActionsGrid.setSpacing(8)

        self.saveScreenshotBtn = PushButton(tr('save_screenshot'))
        self.saveScreenshotBtn.clicked.connect(self.save_drawing_screenshot)
        self.saveScreenshotBtn.setToolTip(tr('tip_screenshot'))

        self.sidebarUndoBtn = PushButton(tr('undo'))
        self.sidebarUndoBtn.setToolTip(tr('tip_undo'))
        self.sidebarUndoBtn.clicked.connect(self.undo_last_stroke)

        self.sidebarClearBtn = PushButton(tr('clear'))
        self.sidebarClearBtn.setToolTip(tr('tip_clear_draw'))
        self.sidebarClearBtn.clicked.connect(self.clear_all_strokes)

        for btn in [self.saveScreenshotBtn, self.sidebarUndoBtn, self.sidebarClearBtn]:
            btn.setStyleSheet(ACTION_BTN_STYLE)
            btn.setMinimumHeight(38)

        drawingActionsGrid.addWidget(self.saveScreenshotBtn, 0, 0, 1, 2)
        drawingActionsGrid.addWidget(self.sidebarUndoBtn,    1, 0)
        drawingActionsGrid.addWidget(self.sidebarClearBtn,   1, 1)
        self.drawingSidebarLayout.addLayout(drawingActionsGrid)
        self.drawingSidebarLayout.addStretch(1)
        self.drawingContainer.hide()

    # ------------------------------------------------------------------ #
    # Controls card                                                        #
    # ------------------------------------------------------------------ #

    def _init_controls_card(self):
        self.controlsCard = QFrame()
        self.controlsCard.setStyleSheet("background-color: #202020; border: none;")
        self.controlsLayout = QVBoxLayout(self.controlsCard)
        self.controlsLayout.setContentsMargins(12, 12, 12, 12)

        # Progress bar row
        progressLayout = QHBoxLayout()
        self.currentTimeLabel = CaptionLabel("00:00")
        self.frameLabel = CaptionLabel(" [F: 0]")
        self.progressBar = MarkerSlider(Qt.Orientation.Horizontal)
        self.progressBar.setStyleSheet(FLUENT_SLIDER_STYLE)
        self.progressBar.setRange(0, 0)
        self.progressBar.sliderMoved.connect(self.set_position)
        self.progressBar.sliderReleased.connect(self.on_slider_released)
        self.progressBar.sliderPressed.connect(self.on_slider_pressed)
        self.totalTimeLabel = CaptionLabel("00:00")

        initial_vol = 50
        if self.volume_ctrl:
            try:
                initial_vol = int(self.volume_ctrl.GetMasterVolumeLevelScalar() * 100)
                self.userMutedIntent = self.volume_ctrl.GetMute()
            except:
                pass
        self.audioOutput.setVolume(initial_vol / 100.0)

        progressLayout.addWidget(self.currentTimeLabel)
        progressLayout.addWidget(self.frameLabel)
        progressLayout.addWidget(self.progressBar)
        progressLayout.addWidget(self.totalTimeLabel)
        self.controlsLayout.addLayout(progressLayout)

        # Buttons row
        buttonsLayout = QHBoxLayout()

        self.toggleSettingsButton = ToolButton(FluentIcon.VIDEO)
        self.toggleSettingsButton.setToolTip(tr('video_settings'))
        self.toggleSettingsButton.clicked.connect(self.toggle_settings)
        buttonsLayout.addWidget(self.toggleSettingsButton)

        self.globalSettingsButton = ToolButton(FluentIcon.SETTING)
        self.globalSettingsButton.setToolTip(tr('tip_settings'))
        self.globalSettingsButton.clicked.connect(self.show_global_settings)
        buttonsLayout.addWidget(self.globalSettingsButton)

        buttonsLayout.addSpacing(20)
        buttonsLayout.addSpacing(10)
        buttonsLayout.addSpacing(10)

        # Playback buttons (center)
        playbackButtonsLayout = QHBoxLayout()
        playbackButtonsLayout.setSpacing(0)

        self.stepBackButton = ToolButton(FluentIcon.LEFT_ARROW)
        self.stepBackButton.setToolTip(tr('tip_prev_frame'))
        self.stepBackButton.clicked.connect(lambda: self.step_frame(-1))
        self.stepBackButton.setFixedSize(32, 32)
        self.stepBackButton.setStyleSheet(
            COMPACT_BTN_STYLE + "ToolButton { border-top-left-radius: 4px; border-bottom-left-radius: 4px; }"
        )

        # Create flipped Play icon for backward button
        play_pixmap = FluentIcon.PLAY.icon().pixmap(QSize(24, 24))
        flipped_play_pixmap = QPixmap.fromImage(play_pixmap.toImage().mirrored(True, False))
        self.flippedPlayIcon = QIcon(flipped_play_pixmap)
        self.normalPlayIcon = FluentIcon.PLAY.icon()
        self.pauseIcon = FluentIcon.PAUSE.icon()

        self.playBackwardButton = ToolButton(self.flippedPlayIcon)
        self.playBackwardButton.setToolTip(tr('tip_play_backward'))
        self.playBackwardButton.setIconSize(QSize(24, 24))
        self.playBackwardButton.setFixedSize(32, 32)
        self.playBackwardButton.setStyleSheet(
            COMPACT_BTN_STYLE + "ToolButton { border-radius: 0px; border-right: none; }"
        )
        self.playBackwardButton.clicked.connect(self.play_pause_backward)

        self.playButton = ToolButton(FluentIcon.PLAY)
        self.playButton.setToolTip(tr('tip_play_pause'))
        self.playButton.setIconSize(QSize(24, 24))
        self.playButton.setFixedSize(32, 32)
        self.playButton.setStyleSheet(
            COMPACT_BTN_STYLE + "ToolButton { border-radius: 0px; border-right: none; }"
        )
        self.playButton.clicked.connect(self.play_pause)

        self.stepForwardButton = ToolButton(FluentIcon.RIGHT_ARROW)
        self.stepForwardButton.setToolTip(tr('tip_next_frame'))
        self.stepForwardButton.clicked.connect(lambda: self.step_frame(1))
        self.stepForwardButton.setFixedSize(32, 32)
        self.stepForwardButton.setStyleSheet(
            COMPACT_BTN_STYLE
            + "ToolButton { border-right: 1px solid rgba(255,255,255,0.08); "
              "border-top-right-radius: 4px; border-bottom-right-radius: 4px; }"
        )

        playbackButtonsLayout.addWidget(self.stepBackButton)
        playbackButtonsLayout.addWidget(self.playBackwardButton)
        playbackButtonsLayout.addWidget(self.playButton)
        playbackButtonsLayout.addWidget(self.stepForwardButton)

        buttonsLayout.addStretch(1)
        buttonsLayout.addLayout(playbackButtonsLayout)
        buttonsLayout.addStretch(1)

        self.fullScreenButton = ToolButton(FluentIcon.FULL_SCREEN)
        self.fullScreenButton.setToolTip(tr('tip_full_screen'))
        self.fullScreenButton.clicked.connect(self.toggle_full_screen)
        buttonsLayout.addWidget(self.fullScreenButton)

        # Volume
        volumeContainer = QWidget()
        volumeContainerLayout = QHBoxLayout(volumeContainer)
        volumeContainerLayout.setContentsMargins(0, 0, 0, 0)
        volumeContainerLayout.setSpacing(5)

        self.volumeButton = ToolButton(FluentIcon.VOLUME)
        if self.userMutedIntent:
            self.volumeButton.setIcon(FluentIcon.MUTE)
        self.volumeButton.clicked.connect(self.toggle_mute)

        self.volumeValueLabel = CaptionLabel(f"{initial_vol}%")
        if self.userMutedIntent:
            self.volumeValueLabel.setText("0%")
        self.volumeValueLabel.setFixedWidth(40)
        self.volumeValueLabel.setStyleSheet(
            "border: none; background: transparent; color: #ccc; font-size: 12px;"
        )
        self.volumeValueLabel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.volumeValueLabel.mousePressEvent = lambda e: self.show_volume_flyout()

        volumeContainerLayout.addWidget(self.volumeButton)
        volumeContainerLayout.addWidget(self.volumeValueLabel)
        buttonsLayout.addWidget(volumeContainer)

        buttonsLayout.addSpacing(20)

        self.togglePlaylistButton = ToolButton(FluentIcon.MENU)
        self.togglePlaylistButton.setToolTip(tr('tip_playlist'))
        self.togglePlaylistButton.clicked.connect(self.toggle_playlist)
        buttonsLayout.addWidget(self.togglePlaylistButton)

        self.toggleDrawingButton = ToolButton(FluentIcon.EDIT)
        self.toggleDrawingButton.setToolTip(tr('tip_drawing'))
        self.toggleDrawingButton.clicked.connect(self.toggle_drawing_panel)
        buttonsLayout.addWidget(self.toggleDrawingButton)

        self.controlsLayout.addLayout(buttonsLayout)

    # ------------------------------------------------------------------ #
    # Full Screen                                                          #
    # ------------------------------------------------------------------ #

    def toggle_full_screen(self):
        self.is_full_screen = not self.is_full_screen
        
        if self.is_full_screen:
            # Entering Full Screen
            # Save sidebar states
            self.sidebar_states_before_fs = {
                'playlist': self.playlistContainer.isVisible(),
                'drawing': self.drawingContainer.isVisible(),
                'settings': self.settingsContainer.isVisible(),
                'global_settings': self.globalSettingsContainer.isVisible()
            }
            
            # Hide everything extra
            self.playlistContainer.hide()
            self.drawingContainer.hide()
            self.settingsContainer.hide()
            self.globalSettingsContainer.hide()
            
            if hasattr(self, 'titleBar'):
                self.titleBar.hide()
            
            # Remove header margin
            if hasattr(self, 'widgetLayout'):
                self.widgetLayout.setContentsMargins(0, 0, 0, 0)
            
            # Disable rounded corners and ensure black background to prevent leaks
            self.setStyleSheet("PlayerWindow { border-radius: 0px; border: none; background: black; }")
            if hasattr(self, 'stackedWidget'):
                self.stackedWidget.setStyleSheet("border-radius: 0px; margin: 0px; padding: 0px;")
            if hasattr(self, 'playerInterface'):
                self.playerInterface.setStyleSheet("border-radius: 0px; margin: 0px; padding: 0px;")
            
            # Windows 11: Disable rounded corners via DWM
            try:
                DWMWA_WINDOW_CORNER_PREFERENCE = 33
                DWMWCP_DONOTROUND = 1
                hwnd = int(self.winId())
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
                    ctypes.byref(ctypes.c_int(DWMWCP_DONOTROUND)), 
                    ctypes.sizeof(ctypes.c_int)
                )
            except:
                pass
            
            self.showFullScreen()
        else:
            # Exiting Full Screen
            self.showNormal()
            
            # Windows 11: Restore rounded corners (default behavior)
            try:
                DWMWA_WINDOW_CORNER_PREFERENCE = 33
                DWMWCP_DEFAULT = 0
                hwnd = int(self.winId())
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
                    ctypes.byref(ctypes.c_int(DWMWCP_DEFAULT)), 
                    ctypes.sizeof(ctypes.c_int)
                )
            except:
                pass
            
            # Restore styles (default for FluentWindow)
            self.setStyleSheet("")
            if hasattr(self, 'stackedWidget'):
                self.stackedWidget.setStyleSheet("")
            if hasattr(self, 'playerInterface'):
                self.playerInterface.setStyleSheet("")
            
            if hasattr(self, 'titleBar'):
                self.titleBar.show()
                
            # Restore header margin
            if hasattr(self, 'widgetLayout'):
                self.widgetLayout.setContentsMargins(0, 32, 0, 0)
                
            # Restore sidebars
            if self.sidebar_states_before_fs.get('playlist'):
                self.playlistContainer.show()
            if self.sidebar_states_before_fs.get('drawing'):
                self.drawingContainer.show()
            if self.sidebar_states_before_fs.get('settings'):
                self.settingsContainer.show()
            if self.sidebar_states_before_fs.get('global_settings'):
                self.globalSettingsContainer.show()

    # ------------------------------------------------------------------ #
    # Keyboard events & Shortcuts                                          #
    # ------------------------------------------------------------------ #

    def setup_shortcuts(self):
        from PyQt6.QtGui import QKeySequence, QShortcut
        from PyQt6.QtWidgets import QLineEdit, QTextEdit
        
        # Clean up existing shortcuts if any
        if hasattr(self, '_shortcut_objects'):
            for sc in self._shortcut_objects:
                sc.setEnabled(False)
                sc.setParent(None)
        
        self._shortcut_objects = []
        
        handled_actions = {
            'play_pause': self.play_pause,
            'smart_mark': self.add_smart_marker,
            'toggle_loop': self.toggle_shortcut_loop,
            'next_frame': lambda: self.step_frame(1),
            'prev_frame': lambda: self.step_frame(-1),
            'toggle_mute': self.toggle_mute,
            'act_full_screen': self.toggle_full_screen
        }
        
        for act, slot in handled_actions.items():
            key_val = self.shortcuts.get(act)
            if key_val is not None:
                try:
                    key_code = int(key_val)
                    shortcut = QShortcut(QKeySequence(key_code), self)
                    shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
                    shortcut.activated.connect(lambda s=slot: self.trigger_shortcut_action(s))
                    self._shortcut_objects.append(shortcut)
                except (ValueError, TypeError) as e:
                    print(f"Error setting up shortcut for {act}: {e}")

    def trigger_shortcut_action(self, slot):
        from PyQt6.QtWidgets import QLineEdit, QTextEdit
        import qfluentwidgets
        focused = self.focusWidget()
        if isinstance(focused, (QLineEdit, QTextEdit, qfluentwidgets.LineEdit, qfluentwidgets.TextEdit)):
            return
        slot()

    def toggle_shortcut_loop(self):
        current = self.loopCombo.currentIndex()
        self.loopCombo.setCurrentIndex(0 if current != 0 else 3)

    def keyPressEvent(self, event):
        super().keyPressEvent(event)
