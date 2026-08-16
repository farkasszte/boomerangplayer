import os
import re
import pytest
from translations.en import TRANSLATIONS_EN
from translations.hu import TRANSLATIONS_HU

def test_translation_dictionaries_match():
    """Ensure EN and HU translation dictionaries have the exact same set of keys."""
    en_keys = set(TRANSLATIONS_EN.keys())
    hu_keys = set(TRANSLATIONS_HU.keys())
    
    missing_in_hu = en_keys - hu_keys
    missing_in_en = hu_keys - en_keys
    
    assert not missing_in_hu, f"Keys present in EN but missing in HU: {missing_in_hu}"
    assert not missing_in_en, f"Keys present in HU but missing in EN: {missing_in_en}"

def test_no_missing_tr_calls_in_codebase():
    """Ensure all tr('...') calls in source code exist in translation dictionaries."""
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tr_pattern = re.compile(r"tr\(['\"]([^'\"]+)['\"]\)")
    
    missing_keys = set()
    for root, dirs, files in os.walk(root_dir):
        if any(ignore in root for ignore in ['.git', '.venv', '__pycache__', 'build', 'dist', 'graphify-out', 'tests']):
            continue
        for f in files:
            if f.endswith(".py"):
                path = os.path.join(root, f)
                with open(path, "r", encoding="utf-8", errors="ignore") as fp:
                    content = fp.read()
                    for match in tr_pattern.finditer(content):
                        key = match.group(1)
                        if key not in TRANSLATIONS_EN:
                            missing_keys.add((key, os.path.relpath(path, root_dir)))
                            
    assert not missing_keys, f"Found missing translation keys in code: {missing_keys}"
