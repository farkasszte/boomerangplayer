from .en import TRANSLATIONS_EN
from .hu import TRANSLATIONS_HU

TRANSLATIONS = {
    'en': TRANSLATIONS_EN,
    'hu': TRANSLATIONS_HU
}

_current_lang = 'en'

def set_lang(lang):
    global _current_lang
    if lang in TRANSLATIONS:
        _current_lang = lang

def get_lang():
    return _current_lang

def tr(key):
    return TRANSLATIONS.get(_current_lang, TRANSLATIONS['en']).get(key, key)
