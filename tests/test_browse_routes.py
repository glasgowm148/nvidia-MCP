"""H4: kodi_browse checks path segments and every query parameter for action verbs."""

import pytest

from nvidia_mcp.config import ShieldError
from nvidia_mcp.operations import unsafe_plugin_route

BLOCKED = [
    "plugin://plugin.video.youtube/play/?video_id=abc123",
    "plugin://plugin.video.youtube/sign/out/",
    "plugin://plugin.video.youtube/sign/in/",
    "plugin://plugin.video.youtube/maintenance/delete/?target=history",
    "plugin://plugin.video.youtube/settings/",
    "plugin://plugin.video.youtube/kodion/search/input/",
    "plugin://plugin.video.youtube/config/youtube/?item=refresh",
    "plugin://plugin.video.fen/?mode=playback.media&tmdb_id=603",
    "plugin://plugin.video.fen/?mode=trakt_manager_choice&tmdb_id=603",
    "plugin://plugin.video.fen/?mode=build_movie_list&next=1&cmd=clear_cache",
    "plugin://plugin.video.example/?route=x&foo=resolveUrl",
    "plugin://plugin.video.example/?toggle_watched=1",
    "plugin://plugin.video.example/?action=delete",
    "plugin://plugin.video.example/?mode=navigator&do=uninstall",
    "plugin://plugin.video.example/?mode=keyboard_search",
    "plugin://plugin.video.example/?mode=authorize_rd",
    "plugin://plugin.video.example/?mode=logout",
    "plugin://plugin.video.example/?mode=rescan_library",
    "plugin://plugin.video.example/?mode=reset_all",
    "plugin://plugin.video.example/?mode=update_widgets",
    "plugin://plugin.video.example/?mode=open_dialog",
    "plugin://plugin.video.example/?mode=context_menu",
    "plugin://plugin.video.example/?mode=install_addon",
    "plugin://plugin.video.example/?url=%7B%22mode%22%3A%22play_media%22%7D",
    "plugin://plugin.video.themoviedb.helper/?info=play&tmdb_type=movie&tmdb_id=603",
]
ALLOWED = [
    "plugin://plugin.video.youtube/",
    "plugin://plugin.video.youtube/special/popular_right_now/",
    "plugin://plugin.video.youtube/channel/UCabc/playlists/",
    "plugin://plugin.video.youtube/kodion/search/query/?q=documentaries",
    "plugin://plugin.video.fen/?mode=build_movie_list&action=tmdb_movies_popular",
    "plugin://plugin.video.fen/?mode=navigator.main&action=MovieList&name=Child%27s%20Play",
    "plugin://plugin.video.themoviedb.helper/?info=trakt_trending&tmdb_type=movie",
    "plugin://plugin.video.themoviedb.helper/?info=details&tmdb_type=tv&tmdb_id=1399",
    "plugin://plugin.video.example/?mode=recently_updated&page=2",
]


@pytest.mark.parametrize("path", BLOCKED)
def test_blocked_routes(ops, path):
    assert unsafe_plugin_route(path)
    with pytest.raises(ShieldError, match="cannot be previewed") as exc:
        ops.directory(path)
    assert exc.value.kind == "unsafe_route"
    assert not any(c[0] == "Files.GetDirectory" for c in ops.t.calls)


@pytest.mark.parametrize("path", ALLOWED)
def test_allowed_listing_routes(ops, path):
    ops.t.running = True
    assert not unsafe_plugin_route(path)
    ops.directory(path)
    assert any(c[0] == "Files.GetDirectory" for c in ops.t.calls)


def test_browse_needs_running_idle_kodi(ops):
    path = "plugin://plugin.video.youtube/"
    with pytest.raises(ShieldError, match="not running"):
        ops.directory(path)
    ops.t.running = True
    ops.t.players = [{"playerid": 1}]
    with pytest.raises(ShieldError, match="playing"):
        ops.directory(path)
