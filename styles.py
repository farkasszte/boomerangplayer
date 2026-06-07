# Styles for Boomerang Player

def get_styles(accent_color="#00f2ff", bg_color="#202020", inverse_text=False):
    styles = {}
    
    fg_color = "#1c1c1c" if inverse_text else "#ffffff"
    sec_fg_color = "#555555" if inverse_text else "#aaaaaa"
    
    # Dynamic borders and translucent backgrounds
    border_color = "rgba(0, 0, 0, 0.35)" if inverse_text else "rgba(255, 255, 255, 0.1)"
    border_bottom_color = "rgba(0, 0, 0, 0.45)" if inverse_text else "rgba(255, 255, 255, 0.2)"
    bg_translucent = "rgba(0, 0, 0, 0.04)" if inverse_text else "rgba(255, 255, 255, 0.05)"
    bg_hover = "rgba(0, 0, 0, 0.08)" if inverse_text else "rgba(255, 255, 255, 0.1)"
    bg_pressed = "rgba(0, 0, 0, 0.02)" if inverse_text else "rgba(255, 255, 255, 0.03)"
    menu_selected_bg = "rgba(0, 0, 0, 0.12)" if inverse_text else "rgba(255, 255, 255, 0.15)"
    
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

    styles['COMPACT_BTN_STYLE'] = f"""
    ToolButton {{
        border: 1px solid {border_color};
        border-right: none;
        border-radius: 0px;
        background: {bg_translucent};
        padding: 0px;
        min-width: 32px;
        min-height: 32px;
        max-height: 32px;
        margin: 0px;
    }}
    ToolButton:hover {{
        background: {bg_hover};
    }}
    ToolButton:pressed {{
        background: {bg_pressed};
    }}
    """

    styles['MENU_STYLE'] = f"""
        QMenu {{
            background-color: {bg_color};
            color: {fg_color};
            border: 1px solid {border_color};
            border-radius: 5px;
            padding: 5px;
        }}
        QMenu::item {{
            padding: 5px 25px 5px 20px;
            border-radius: 3px;
            color: {fg_color};
        }}
        QMenu::item:selected {{
            background-color: {menu_selected_bg};
            color: {fg_color};
        }}
    """

    styles['COMBO_STYLE'] = f"""
        QComboBox {{
            background: {bg_translucent};
            border: 1px solid {border_color};
            border-bottom: 1px solid {border_bottom_color};
            border-radius: 5px; padding: 4px 10px;
            min-height: 22px; color: {fg_color}; font-size: 13px;
        }}
        QComboBox:hover {{ background: {bg_hover}; }}
        QComboBox::drop-down {{ border: none; width: 0px; }}
        QComboBox::down-arrow {{ image: none; border: none; background: transparent; }}
        QComboBox QAbstractItemView {{
            background-color: {bg_color};
            border: 1px solid rgba(0,0,0,0.4);
            selection-background-color: {accent_color};
            selection-color: {fg_color};
            color: {fg_color}; outline: none;
        }}
    """

    styles['SWITCH_STYLE'] = f"""
        SwitchButton[checked=true] > .Indicator {{
            background-color: {accent_color};
        }}
    """

    styles['SPINBOX_STYLE'] = f"""
        QSpinBox {{
            background: {bg_translucent};
            border: 1px solid {border_color};
            border-bottom: 1px solid {border_bottom_color};
            border-radius: 5px;
            padding: 4px 6px;
            color: {fg_color};
            font-size: 13px;
        }}
        QSpinBox:hover {{
            background: {bg_hover};
        }}
        QSpinBox:focus {{
            border: 1px solid {accent_color};
            background: {bg_translucent};
        }}
    """

    styles['ACTION_BTN_STYLE'] = f"""
        PushButton {{
            border: none;
            border-radius: 4px;
            background: {bg_translucent};
            border: 1px solid {border_color};
            color: {fg_color};
            font-size: 13px;
            font-weight: 500;
            padding: 8px;
            min-width: 60px;
        }}
        PushButton:hover {{
            background: {bg_hover};
        }}
    """

    styles['TOOL_BTN_STYLE'] = f"""
        PushButton, ToolButton {{
            font-size: 13px;
            font-weight: 500;
            padding: 6px;
            background: {bg_translucent};
            border: 1px solid {border_color};
            border-radius: 4px;
            color: {fg_color};
        }}
        PushButton:hover, ToolButton:hover {{
            background: {bg_hover};
        }}
        PushButton[checked=true], ToolButton[checked=true] {{
            background: rgba({_hex_to_rgb(accent_color)}, 0.15);
            border: 1px solid {accent_color};
            color: {accent_color};
        }}
        PushButton:checked, ToolButton:checked {{
            background: rgba({_hex_to_rgb(accent_color)}, 0.15);
            border: 1px solid {accent_color};
            color: {accent_color};
        }}
    """

    styles['TRIGGER_STYLE'] = f"""
        PushButton {{
            background: {bg_translucent};
            border: 1px solid {border_color};
            border-bottom: 1px solid {border_bottom_color};
            border-radius: 4px; color: {fg_color};
            padding: 8px 12px; text-align: left; font-size: 13px;
        }}
        PushButton:hover {{ background: {bg_hover}; }}
    """

    styles['TITLE_STYLE'] = f"font-size: 16px; font-weight: bold; color: {fg_color}; background: transparent;"
    styles['CAPTION_STYLE'] = f"font-weight: bold; color: {sec_fg_color}; background: transparent;"
    
    # Borderless/Accent colored menu popup style
    styles['MENU_POPUP_STYLE'] = f"""
        QMenu {{
            background-color: {bg_color};
            border: none;
            padding: 4px 0px;
        }}
        QMenu::item {{
            padding: 8px 25px;
            color: {fg_color};
            background-color: transparent;
        }}
        QMenu::item:selected {{
            background-color: {menu_selected_bg};
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
    styles['CHRONO_OVERLAY_STYLE'] = f"""
        QFrame {{
            background-color: rgba(15, 15, 15, 0.85);
            border: 1px solid {border_color};
            border-radius: 8px;
        }}
        QLabel {{
            color: {fg_color};
            background: transparent;
            border: none;
        }}
    """

    # Caching / Loading mask overlay style
    styles['LOADING_OVERLAY_STYLE'] = f"""
        background: rgba(0,0,0,180);
        color: {fg_color};
        font-weight: bold;
        border-radius: 0px;
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
