# Styles for Boomerang Player

def get_styles(accent_color="#00f2ff", bg_color="#202020"):
    styles = {}
    
    styles['FLUENT_SLIDER_STYLE'] = f"""
    QSlider::groove:horizontal {{
        border: none;
        height: 4px;
        background: #444;
        margin: 2px 0;
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        background: #ffffff;
        width: 2px;
        height: 16px;
        margin: -6px 0;
    }}
    QSlider::handle:horizontal:hover {{
        background: #ffffff;
    }}
    QSlider::sub-page:horizontal {{
        background: {accent_color};
        border-radius: 2px;
    }}
    """

    styles['COMPACT_BTN_STYLE'] = """
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

    styles['MENU_STYLE'] = f"""
        QMenu {{
            background-color: {bg_color};
            color: white;
            border: 1px solid #333;
            border-radius: 5px;
            padding: 5px;
        }}
        QMenu::item {{
            padding: 5px 25px 5px 20px;
            border-radius: 3px;
        }}
        QMenu::item:selected {{
            background-color: #333;
        }}
    """

    styles['COMBO_STYLE'] = f"""
        QComboBox {{
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.1);
            border-bottom: 1px solid rgba(255,255,255,0.2);
            border-radius: 5px; padding: 4px 10px;
            min-height: 22px; color: white; font-size: 13px;
        }}
        QComboBox:hover {{ background: rgba(255,255,255,0.1); }}
        QComboBox::drop-down {{ border: none; width: 0px; }}
        QComboBox::down-arrow {{ image: none; border: none; background: transparent; }}
        QComboBox QAbstractItemView {{
            background-color: {bg_color};
            border: 1px solid rgba(0,0,0,0.4);
            selection-background-color: {accent_color};
            selection-color: white;
            color: white; outline: none;
        }}
    """

    styles['SWITCH_STYLE'] = f"""
        SwitchButton[checked=true] > .Indicator {{
            background-color: {accent_color};
        }}
    """

    styles['ACTION_BTN_STYLE'] = """
        PushButton {
            border: none;
            border-radius: 4px;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: white;
            font-size: 13px;
            font-weight: 500;
            padding: 8px;
            min-width: 60px;
        }
        PushButton:hover {
            background: rgba(255, 255, 255, 0.1);
        }
    """

    styles['TOOL_BTN_STYLE'] = f"""
        PushButton {{
            font-size: 13px;
            font-weight: 500;
            padding: 6px;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 4px;
        }}
        PushButton:hover {{
            background: rgba(255, 255, 255, 0.1);
        }}
        PushButton[checked=true] {{
            background: rgba({_hex_to_rgb(accent_color)}, 0.15);
            border: 1px solid {accent_color};
            color: {accent_color};
        }}
        PushButton:checked {{
            background: rgba({_hex_to_rgb(accent_color)}, 0.15);
            border: 1px solid {accent_color};
            color: {accent_color};
        }}
    """

    styles['TRIGGER_STYLE'] = """
        PushButton {
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.08);
            border-bottom: 1px solid rgba(255,255,255,0.2);
            border-radius: 4px; color: white;
            padding: 8px 12px; text-align: left; font-size: 13px;
        }
        PushButton:hover { background: rgba(255,255,255,0.1); }
    """

    styles['TITLE_STYLE'] = "font-size: 16px; font-weight: bold; color: white; background: transparent;"
    styles['CAPTION_STYLE'] = "font-weight: bold; color: #aaaaaa; background: transparent;"
    
    # Borderless/Accent colored menu popup style
    styles['MENU_POPUP_STYLE'] = f"""
        QMenu {{
            background-color: {bg_color};
            border: none;
            padding: 4px 0px;
        }}
        QMenu::item {{
            padding: 8px 25px;
            color: white;
            background-color: transparent;
        }}
        QMenu::item:selected {{
            background-color: rgba(255,255,255,0.1);
        }}
        QMenu::item:checked {{
            color: {accent_color};
            font-weight: bold;
        }}
        QMenu::indicator {{
            width: 0px;
        }}
    """

    # Chronometer Overlay dark translucent card style
    styles['CHRONO_OVERLAY_STYLE'] = """
        QFrame {
            background-color: rgba(15, 15, 15, 0.85);
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 8px;
        }
        QLabel {
            color: #e3e3e3;
            background: transparent;
            border: none;
        }
    """

    # Caching / Loading mask overlay style
    styles['LOADING_OVERLAY_STYLE'] = """
        background: rgba(0,0,0,180);
        color: white;
        font-weight: bold;
        border-radius: 10px;
    """
    
    return styles

def _hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return ",".join([str(int(hex_color[i:i+2], 16)) for i in (0, 2, 4)])

# Default styles for backward compatibility during initialization
_default_styles = get_styles()
FLUENT_SLIDER_STYLE = _default_styles['FLUENT_SLIDER_STYLE']
COMPACT_BTN_STYLE = _default_styles['COMPACT_BTN_STYLE']
MENU_STYLE = _default_styles['MENU_STYLE']
ACTION_BTN_STYLE = _default_styles['ACTION_BTN_STYLE']
TOOL_BTN_STYLE = _default_styles['TOOL_BTN_STYLE']
