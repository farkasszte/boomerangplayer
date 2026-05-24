"""
GlobalSettingsMixin — global settings sidebar builder + language/audio/shortcuts handlers.
"""

from mixins.global_settings.ui_builder import GlobalSettingsUiBuilderMixin
from mixins.global_settings.audio_manager import GlobalSettingsAudioManagerMixin
from mixins.global_settings.locale_manager import GlobalSettingsLocaleManagerMixin
from mixins.global_settings.color_manager import GlobalSettingsColorManagerMixin
from mixins.global_settings.shortcut_manager import GlobalSettingsShortcutManagerMixin
from mixins.global_settings.gpu_manager import GlobalSettingsGpuManagerMixin

class GlobalSettingsMixin(
    GlobalSettingsUiBuilderMixin,
    GlobalSettingsAudioManagerMixin,
    GlobalSettingsLocaleManagerMixin,
    GlobalSettingsColorManagerMixin,
    GlobalSettingsShortcutManagerMixin,
    GlobalSettingsGpuManagerMixin
):
    """Builds self.globalSettingsContainer and handles all global settings logic."""
    pass
