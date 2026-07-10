from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout, QButtonGroup, QWidget
from components import SafeSpinBox as QSpinBox, NoWheelSlider
from qfluentwidgets import CaptionLabel, SwitchButton, PushButton, ToolButton, SingleDirectionScrollArea
from styles import TOOL_BTN_STYLE, FLUENT_SLIDER_STYLE, ACTION_BTN_STYLE, get_color_tokens
from translations import tr

class DrawingSidebarUIMixin:
    def _init_drawing_sidebar(self):
        t = get_color_tokens(
            self.config.get('accent_color', '#00f2ff'),
            self.config.get('bg_color', '#202020'),
            self.config.get('inverse_text', False)
        )
        self.drawingContainer = QFrame()
        self.drawingContainer.setMinimumWidth(250)
        self.drawingContainer.setStyleSheet(
            f"background: {t['bg']}; border: none; QScrollBar {{ width: 0px; height: 0px; }}"
        )
        self.drawingSidebarLayout = QVBoxLayout(self.drawingContainer)
        self.drawingSidebarLayout.setContentsMargins(10, 10, 4, 10)
        self.drawingSidebarLayout.setSpacing(6)

        self.drawingSidebarTitle = CaptionLabel(tr('drawing_settings'))
        self.drawingSidebarTitle.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {t['fg']};")
        self.drawingSidebarLayout.addWidget(self.drawingSidebarTitle)

        self.drawingScrollArea = SingleDirectionScrollArea(self.drawingContainer, Qt.Orientation.Vertical)
        self.drawingScrollArea.setWidgetResizable(True)
        self.drawingScrollArea.setStyleSheet("background: transparent; border: none;")
        self.drawingScrollArea.setFrameShape(QFrame.Shape.NoFrame)
        self.drawingScrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.drawingScrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.drawingScrollWidget = QWidget()
        self.drawingScrollWidget.setStyleSheet("background: transparent;")
        self.drawingInnerLayout = QVBoxLayout(self.drawingScrollWidget)
        self.drawingInnerLayout.setContentsMargins(0, 0, 0, 0)
        self.drawingInnerLayout.setSpacing(10)

        self.drawingScrollArea.setWidget(self.drawingScrollWidget)
        self.drawingSidebarLayout.addWidget(self.drawingScrollArea)

        drawModeToggleLayout = QHBoxLayout()
        self.drawModeToggleLabel = QLabel(tr('drawing_mode'))
        self.drawModeToggleLabel.setStyleSheet(f"color: {t['fg']}; font-size: 13px;")
        self.drawModeToggle = SwitchButton()
        self.drawModeToggle.setOnText(tr('on'))
        self.drawModeToggle.setOffText(tr('off'))
        
        self.drawModeToggle.checkedChanged.connect(self.toggle_drawing_mode)
        drawModeToggleLayout.addWidget(self.drawModeToggleLabel)
        drawModeToggleLayout.addStretch(1)
        drawModeToggleLayout.addWidget(self.drawModeToggle)
        self.drawingInnerLayout.addLayout(drawModeToggleLayout)

        laserModeToggleLayout = QHBoxLayout()
        self.laserModeToggleLabel = QLabel(tr('laser_mode'))
        self.laserModeToggleLabel.setStyleSheet(f"color: {t['fg']}; font-size: 13px;")
        self.laserModeToggle = SwitchButton()
        self.laserModeToggle.setOnText(tr('on'))
        self.laserModeToggle.setOffText(tr('off'))
        
        self.laserModeToggle.checkedChanged.connect(self.toggle_laser_mode)
        laserModeToggleLayout.addWidget(self.laserModeToggleLabel)
        laserModeToggleLayout.addStretch(1)
        laserModeToggleLayout.addWidget(self.laserModeToggle)
        self.drawingInnerLayout.addLayout(laserModeToggleLayout)

        chronometerToggleLayout = QHBoxLayout()
        self.chronometerToggleLabel = QLabel(tr('chronometer_overlay'))
        self.chronometerToggleLabel.setStyleSheet(f"color: {t['fg']}; font-size: 13px;")
        self.chronometerToggle = SwitchButton()
        self.chronometerToggle.setOnText(tr('on'))
        self.chronometerToggle.setOffText(tr('off'))
        
        self.chronometerToggle.checkedChanged.connect(self.toggle_chronometer)
        chronometerToggleLayout.addWidget(self.chronometerToggleLabel)
        chronometerToggleLayout.addStretch(1)
        chronometerToggleLayout.addWidget(self.chronometerToggle)
        self.drawingInnerLayout.addLayout(chronometerToggleLayout)

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
            (tr('watermark'),    'watermark',    tr('tip_watermark')),
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
            elif tool_id == 'watermark':     self.watermarkTool = btn

            self.toolGroup.addButton(btn)
            
            btn.clicked.connect(lambda checked, t=tool_id: self.set_active_tool(t))
            toolsLayout.addWidget(btn, i // 2, i % 2)

        self.drawingInnerLayout.addLayout(toolsLayout)
        self.drawingInnerLayout.addSpacing(15)

        # ---- Quick Palette ----
        self.paletteTitle = CaptionLabel(tr('color_palette'))
        self.paletteTitle.setStyleSheet(f"font-weight: bold; margin-top: 10px; color: {t['sec_fg']};")
        self.drawingInnerLayout.addWidget(self.paletteTitle)
        
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
            
        self.drawingInnerLayout.addLayout(paletteLayout)
        
        self.update_palette_ui()
        self.drawingInnerLayout.addSpacing(15)

        # Thickness row
        thicknessRow = QHBoxLayout()
        self.penPreview = QLabel()
        self.penPreview.setFixedSize(30, 30)
        self.penPreview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.penPreview.setStyleSheet("background: transparent; border: none !important;")
        thicknessRow.addWidget(self.penPreview)

        self.penSizeLabel = QSpinBox()
        self.penSizeLabel.setRange(1, 60)
        self.penSizeLabel.setValue(3)
        self.penSizeLabel.setSuffix(" px")
        self.penSizeLabel.setFixedWidth(80)
        self.penSizeLabel.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        thicknessRow.addWidget(self.penSizeLabel)
        thicknessRow.addStretch(1)

        self.penColorBtn = PushButton(tr('color'))
        self.penColorBtn.setToolTip(tr('tip_color'))
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
        self.drawingInnerLayout.addLayout(thicknessRow)

        self.penSizeSlider = NoWheelSlider(Qt.Orientation.Horizontal)
        self.penSizeSlider.setRange(1, 60)
        self.penSizeSlider.setValue(3)
        self.penSizeSlider.setStyleSheet(FLUENT_SLIDER_STYLE)
        
        # Bidirectional sync
        self.penSizeLabel.valueChanged.connect(self.penSizeSlider.setValue)
        self.penSizeSlider.valueChanged.connect(self.penSizeLabel.setValue)
        
        
        self.penSizeSlider.valueChanged.connect(self.update_pen_width)
        self.drawingInnerLayout.addWidget(self.penSizeSlider)
        self.drawingInnerLayout.addSpacing(15)

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
        self.drawingInnerLayout.addLayout(drawingActionsGrid)
        self.drawingInnerLayout.addStretch(1)
        self.drawingContainer.hide()
