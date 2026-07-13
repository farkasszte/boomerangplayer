import pytest
from utils import DEFAULT_CONFIG, validate_config

def test_validate_config_empty():
    validated = validate_config({})
    assert validated == DEFAULT_CONFIG

def test_validate_config_valid():
    custom = {
        'language': 'hu',
        'accent_color': '#ff0000',
        'panel_opacity': 85,
        'speed_locked': True,
        'subtitle_outline_width': 3
    }
    validated = validate_config(custom)
    assert validated['language'] == 'hu'
    assert validated['accent_color'] == '#FF0000'
    assert validated['panel_opacity'] == 85
    assert validated['speed_locked'] is True
    assert validated['subtitle_outline_width'] == 3

def test_validate_config_invalid_types():
    custom = {
        'language': 123,
        'accent_color': 'blue',
        'panel_opacity': 150,
        'subtitle_outline_width': 'abc'
    }
    validated = validate_config(custom)
    assert validated['language'] == DEFAULT_CONFIG['language']
    assert validated['accent_color'] == DEFAULT_CONFIG['accent_color']
    assert validated['panel_opacity'] == 100
    assert validated['subtitle_outline_width'] == DEFAULT_CONFIG['subtitle_outline_width']
