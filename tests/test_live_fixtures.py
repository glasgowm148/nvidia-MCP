"""Guard decisions on `dumpsys` lines captured from the household Shield (Android 11,
Kodi 22.0 RC1, Projectivy launcher) on 2026-10-11. Only the lines the guard reads are kept;
everything here is the device's own text, not a synthetic approximation."""

import pytest

from nvidia_mcp.config import ShieldError
from nvidia_mcp.operations import foreground_state, media_playing, media_sessions

MEDIA_HEADER = "MEDIA SESSION SERVICE (dumpsys media_session)\n"
# Kodi with a film paused (14:0x).
KODI_PAUSED = (
    "    org.xbmc.kodi/XBMC (userId=0)\n"
    "      package=org.xbmc.kodi\n"
    "      active=true\n"
    "      state=PlaybackState {state=2, position=2971175, buffered position=0, speed=0.0, "
    "updated=331821495, actions=-1, custom actions=[], active item id=-1, error=null}\n"
)
# The session Kodi leaves behind after playback stopped: still active, state STOPPED.
KODI_LINGERING_STOPPED = (
    "    org.xbmc.kodi/XBMC (userId=0)\n"
    "      package=org.xbmc.kodi\n"
    "      active=true\n"
    "      state=PlaybackState {state=1, position=2971175, buffered position=0, speed=0.0, "
    "updated=331821495, actions=-1, custom actions=[], active item id=-1, error=null}\n"
)
PROJECTIVY_IN_FRONT = "    mResumedActivity: ActivityRecord{357b962 u0 com.spocky.projengmenu/.ui.home.MainActivity t3246}\n"
KODI_IN_FRONT = "    mResumedActivity: ActivityRecord{8e28264 u0 org.xbmc.kodi/.Main t3423}\n"


def device(ops, activities, media):
    original = ops.t.shell

    def shell(*args, **kwargs):
        if args == ("dumpsys", "activity", "activities"):
            ops.t.calls.append(("shell", args))
            return activities
        if args == ("dumpsys", "media_session"):
            ops.t.calls.append(("shell", args))
            return MEDIA_HEADER + media
        return original(*args, **kwargs)

    ops.t.shell = shell


def sent(ops, *prefix):
    return [c for c in ops.t.calls if c[0] == "shell" and c[1][: len(prefix)] == prefix]


def test_parsers_read_the_real_lines(ops):
    device(ops, PROJECTIVY_IN_FRONT, KODI_PAUSED)
    assert foreground_state(ops.t) == ("app", "com.spocky.projengmenu")
    assert media_sessions(ops.t) == [("org.xbmc.kodi", 2)]
    assert media_playing(ops.t) == ["org.xbmc.kodi"]
    device(ops, KODI_IN_FRONT, KODI_LINGERING_STOPPED)
    assert foreground_state(ops.t) == ("app", "org.xbmc.kodi")
    assert media_sessions(ops.t) == [("org.xbmc.kodi", 1)]
    assert media_playing(ops.t) == []


def test_projectivy_with_a_lingering_stopped_session_is_nobody_watching(ops):
    # Kodi stopped, Projectivy home in front, Kodi's state=1 session still listed as active.
    ops.t.offline = True
    device(ops, PROJECTIVY_IN_FRONT, KODI_LINGERING_STOPPED)
    assert ops.remote("select") == {"sent": "select"}
    assert ops.lifecycle("start")["requested"] == "start"
    assert sent(ops, "am", "start")


@pytest.mark.parametrize("activities", [PROJECTIVY_IN_FRONT, KODI_IN_FRONT])
def test_real_paused_kodi_session_blocks_every_guarded_action(ops, activities):
    # Kodi's HTTP answers "no players" (or is down) but Android still holds the paused film.
    ops.t.running = True
    device(ops, activities, KODI_PAUSED)
    with pytest.raises(ShieldError, match="playing or paused"):
        ops.remote("select")
    with pytest.raises(ShieldError, match="playing or paused"):
        ops.lifecycle("restart")
    with pytest.raises(ShieldError, match="playing or paused"):
        ops.set_core_setting("audiooutput.passthrough", True)
    assert not sent(ops, "input") and not sent(ops, "am")


def test_kodi_in_front_idle_with_lingering_session_allows_settings(ops):
    ops.t.running = True
    device(ops, KODI_IN_FRONT, KODI_LINGERING_STOPPED)
    assert ops.set_core_setting("audiooutput.passthrough", True)["current"] is True
