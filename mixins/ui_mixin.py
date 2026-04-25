"""
UIMixin — top-level init_ui orchestrator, playlist sidebar, drawing sidebar,
          controls bar, keyboard events.
"""

from PyQt6.QtCore import Qt, QSize, QPoint
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFrame,
                              QSplitter, QLabel, QGridLayout,
                              QGraphicsScene, QGraphicsPixmapItem)
from qfluentwidgets import (FluentIcon, ToolButton, CardWidget, CaptionLabel,
                             SwitchButton, PushButton)
from components import DropListWidget, MarkerSlider, ZoomView
from styles import (FLUENT_SLIDER_STYLE, COMPACT_BTN_STYLE, MENU_STYLE,
                    DRAWING_ACTION_STYLE, TOOL_BTN_STYLE)
from translations import tr
from PyQt6.QtWidgets import QMenu, QButtonGroup, QSlider
from PyQt6.QtMultimedia import QMediaDevices
import qfluentwidgets


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
        self.view.zoomChanged.connect(self.sync_zoom_ui)
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

        self.pixmapItem = QGraphicsPixmapItem()
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

        self.update_ui_texts()

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

        self.playlistButtonsGrid = QGridLayout()
        self.playlistButtonsGrid.setSpacing(8)

        self.btn_add = PushButton(tr('add'))
        self.btn_add.setToolTip(tr('tip_add'))
        self.addMenu = QMenu(self)
        self.addMenu.setStyleSheet(MENU_STYLE)
        self.addMenu.addAction(tr('add_media'), self.open_file)
        self.addMenu.addAction(tr('add_video_folder'), lambda: self.add_folder_contents(type="video"))
        self.addMenu.addAction(tr('add_image_folder'), lambda: self.add_folder_contents(type="image"))
        self.addMenu.addSeparator()
        self.addMenu.addAction(tr('load_playlist'), self.load_playlist_from_file)
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
        self.drawingSidebarLayout.setContentsMargins(10, 10, 10, 10)
        self.drawingSidebarLayout.setSpacing(15)

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
            (tr('obj_eraser'),   'obj_eraser',   tr('tip_obj_eraser')),
            (tr('area_eraser'),  'area_eraser',  tr('tip_area_eraser')),
            (tr('stroke_eraser'),'stroke_eraser',tr('tip_stroke_eraser')),
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
            elif tool_id == 'stroke_eraser': self.strokeEraserTool = btn

            self.toolGroup.addButton(btn)
            btn.clicked.connect(lambda checked, t=tool_id: self.set_active_tool(t))
            toolsLayout.addWidget(btn, i // 2, i % 2)

        self.drawingSidebarLayout.addLayout(toolsLayout)
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
            "color: #00f2ff; font-size: 13px; font-weight: 500; "
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
            btn.setStyleSheet(DRAWING_ACTION_STYLE)
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
        self.controlsCard = CardWidget()
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
        playbackButtonsLayout.addWidget(self.playButton)
        playbackButtonsLayout.addWidget(self.stepForwardButton)

        buttonsLayout.addStretch(1)
        buttonsLayout.addLayout(playbackButtonsLayout)
        buttonsLayout.addStretch(1)

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

        self.audioOutput.setVolume(0.7)

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
    # Keyboard events                                                      #
    # ------------------------------------------------------------------ #

    def keyPressEvent(self, event):
        key = event.key()

        if isinstance(self.focusWidget(), (qfluentwidgets.LineEdit, qfluentwidgets.TextEdit)):
            super().keyPressEvent(event)
            return

        action = None
        for act, k in self.shortcuts.items():
            if k == key:
                action = act
                break

        if action == 'play_pause':
            self.play_pause()
        elif action == 'smart_mark':
            self.add_smart_marker()
        elif action == 'toggle_loop':
            current = self.loopCombo.currentIndex()
            self.loopCombo.setCurrentIndex(0 if current != 0 else 3)
        elif action == 'next_frame':
            self.step_frame(1)
        elif action == 'prev_frame':
            self.step_frame(-1)
        elif action == 'toggle_mute':
            self.toggle_mute()
        else:
            super().keyPressEvent(event)
