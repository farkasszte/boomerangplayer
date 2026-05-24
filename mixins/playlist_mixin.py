"""
PlaylistMixin — playlist sidebar logic, CRUD, thumbnails, file info.
"""

from mixins.playlist.core_mixin import PlaylistCoreMixin
from mixins.playlist.thumbnail_mixin import PlaylistThumbnailMixin
from mixins.playlist.crud_mixin import PlaylistCrudMixin
from mixins.playlist.menu_mixin import PlaylistMenuMixin
from mixins.playlist.sort_mixin import PlaylistSortMixin
from mixins.playlist.persistence_mixin import PlaylistPersistenceMixin
from mixins.playlist.info_mixin import PlaylistInfoMixin

class PlaylistMixin(
    PlaylistCoreMixin,
    PlaylistThumbnailMixin,
    PlaylistCrudMixin,
    PlaylistMenuMixin,
    PlaylistSortMixin,
    PlaylistPersistenceMixin,
    PlaylistInfoMixin
):
    pass
