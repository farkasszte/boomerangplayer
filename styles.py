# Styles for Boomerang Player

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

COMPACT_BTN_STYLE = """
ToolButton {
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-right: none;
    border-radius: 0px;
    background: rgba(255, 255, 255, 0.05);
    padding: 0px;
    min-width: 32px;
    min-height: 32px;
    max-height: 32px;
    margin: 0px;
}
ToolButton:hover {
    background: rgba(255, 255, 255, 0.1);
}
ToolButton:pressed {
    background: rgba(255, 255, 255, 0.03);
}
"""

MENU_STYLE = """
    QMenu {
        background-color: #202020;
        color: white;
        border: 1px solid #333;
        border-radius: 5px;
        padding: 5px;
    }
    QMenu::item {
        padding: 5px 25px 5px 20px;
        border-radius: 3px;
    }
    QMenu::item:selected {
        background-color: #333;
    }
"""

ACTION_BTN_STYLE = """
    PushButton {
        border: none;
        border-radius: 4px;
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        color: white;
        font-size: 13px;
        font-weight: 500;
        padding: 8px;
    }
    PushButton:hover {
        background: rgba(255, 255, 255, 0.1);
    }
"""

TOOL_BTN_STYLE = """
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
    PushButton[checked=true] {
        background: rgba(0, 242, 255, 0.15);
        border: 1px solid #00f2ff;
        color: #00f2ff;
    }
    PushButton:checked {
        background: rgba(0, 242, 255, 0.15);
        border: 1px solid #00f2ff;
        color: #00f2ff;
    }
"""
