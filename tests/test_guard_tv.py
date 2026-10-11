"""H2: one guard (Kodi idle + foreground app + running state) for every disruptive tool."""

from dataclasses import replace
from pathlib import Path

import pytest
from conftest import media_session

from nvidia_mcp.config import Config, ShieldError
from nvidia_mcp.operations import LAUNCHERS


def foreground(ops, package):
    original = ops.t.shell

    def shell(*args, **kwargs):
        if args == ("dumpsys", "activity", "activities"):
            ops.t.calls.append(("shell", args))
            return f"mResumedActivity: ActivityRecord{{1 u0 {package}/.Main t1}}"
        return original(*args, **kwargs)

    ops.t.shell = shell


def keyevents(ops):
    return [c for c in ops.t.calls if c[0] == "shell" and c[1][:2] == ("input", "keyevent")]


@pytest.mark.parametrize(
    "app", ["com.netflix.ninja", "com.teamsmart.videomanager.tv", "com.google.android.youtube.tv"]
)
@pytest.mark.parametrize("button", ["home", "back", "stop"])
def test_remote_refuses_when_another_app_is_in_front(ops, app, button):
    ops.t.running = True
    foreground(ops, app)
    with pytest.raises(ShieldError, match="Another TV app"):
        ops.remote(button)
    assert not keyevents(ops)


def test_remote_override_needs_env_opt_in(ops):
    foreground(ops, "com.netflix.ninja")
    ops.t.players = [{"playerid": 1}]
    with pytest.raises(ShieldError, match="NVIDIA_MCP_ALLOW_INTERRUPT"):
        ops.remote("stop", allow_during_playback=True)
    assert not keyevents(ops)
    ops.c = replace(ops.c, allow_interrupt=True)
    assert ops.remote("stop", allow_during_playback=True) == {"sent": "stop"}
    assert keyevents(ops)


def test_remote_works_on_launcher_with_kodi_stopped(ops):
    ops.t.offline = True  # Kodi HTTP is down because Kodi is not running.
    foreground(ops, "com.google.android.tvlauncher")
    assert ops.remote("select") == {"sent": "select"}


def test_remote_refuses_during_kodi_playback(ops):
    ops.t.running = True
    ops.t.players = [{"playerid": 1}]
    with pytest.raises(ShieldError, match="playing"):
        ops.remote("home")


def test_layout_rebuild_uses_guard(ops):
    ops.t.running = True
    foreground(ops, "com.netflix.ninja")
    with pytest.raises(ShieldError, match="Another TV app"):
        ops.rebuild_layout()
    assert not any(c[0] == "/api/widgets/layout/rebuild" for c in ops.t.calls)
    foreground(ops, "org.xbmc.kodi")
    ops.rebuild_layout()
    assert any(c[0] == "/api/widgets/layout/rebuild" for c in ops.t.calls)


def test_lifecycle_interrupt_other_app_needs_env_opt_in(ops):
    foreground(ops, "com.netflix.ninja")
    with pytest.raises(ShieldError, match="NVIDIA_MCP_ALLOW_INTERRUPT"):
        ops.lifecycle("start", interrupt_other_app=True)
    ops.c = replace(ops.c, allow_interrupt=True)
    assert ops.lifecycle("start", interrupt_other_app=True)["requested"] == "start"


def test_extra_launchers_from_env(monkeypatch, ops):
    monkeypatch.setenv("SHIELD_HOST", "192.168.1.50")
    monkeypatch.setenv("NVIDIA_MCP_EXTRA_LAUNCHERS", "com.example.home, com.other.launcher")
    config = Config.from_env()
    assert config.extra_launchers == ("com.example.home", "com.other.launcher")
    ops.c = replace(ops.c, extra_launchers=config.extra_launchers)
    foreground(ops, "com.example.home")
    assert ops.remote("up") == {"sent": "up"}
    monkeypatch.setenv("NVIDIA_MCP_EXTRA_LAUNCHERS", "not a package;rm")
    with pytest.raises(ShieldError):
        Config.from_env()


def test_single_launcher_set_and_pidof_helper():
    source = Path(__file__).parents[1] / "src" / "nvidia_mcp"
    text = "".join(p.read_text() for p in source.glob("*.py"))
    assert text.count("pidof ") == 1
    assert text.count("com.google.android.tvlauncher") == 1
    assert "com.google.android.tvlauncher" in LAUNCHERS


def force_stops(ops):
    return [c for c in ops.t.calls if c[0] == "shell" and c[1][:2] == ("am", "force-stop")]


def test_kodi_in_front_is_checked_even_when_process_probe_misses_it(ops):
    # pidof can miss a Kodi the viewer has just opened; the resumed activity says otherwise.
    ops.t.running = False
    ops.t.players = [{"playerid": 1}]
    with pytest.raises(ShieldError, match="playing"):
        ops.remote("stop")
    assert not keyevents(ops)
    with pytest.raises(ShieldError, match="playing"):
        ops.lifecycle("start")
    assert not any(c[0] == "shell" and c[1][:2] == ("am", "start") for c in ops.t.calls)


@pytest.mark.parametrize(
    "kind", ["authentication_denied", "rpc_error", "invalid_response", "service_error"]
)
def test_offline_recovery_needs_an_unreachable_kodi(ops, kind):
    # Wrong credentials or a protocol error mean Kodi's HTTP server is alive; it may be playing.
    def rpc(method, params=None):
        raise ShieldError("Kodi answered but not usefully", kind)

    ops.t.rpc = rpc
    with pytest.raises(ShieldError, match="unknown"):
        ops.lifecycle("restart", allow_offline=True)
    assert not force_stops(ops)


@pytest.mark.parametrize("state", [2, 3, 6])  # paused, playing, buffering
def test_offline_recovery_refused_while_android_reports_kodi_media(ops, state):
    ops.t.offline = True
    ops.t.media = media_session("org.xbmc.kodi", state)
    with pytest.raises(ShieldError, match="playing or paused"):
        ops.lifecycle("restart", allow_offline=True)
    assert not force_stops(ops)


def test_offline_recovery_refused_when_media_state_unreadable(ops):
    ops.t.offline = True
    shell = ops.t.shell
    ops.t.shell = lambda *a, **kw: "" if a == ("dumpsys", "media_session") else shell(*a, **kw)
    with pytest.raises(ShieldError, match="media playback state is unknown"):
        ops.lifecycle("stop", allow_offline=True)
    assert not force_stops(ops)


def test_offline_recovery_ignores_stopped_or_other_sessions(ops):
    ops.t.offline = True
    ops.t.media = (
        media_session("org.xbmc.kodi", 1)
        + media_session("org.xbmc.kodi", 3, active=False)
        + media_session("com.spotify.tv.android", 2, active=False)
    )
    assert ops.lifecycle("restart", allow_offline=True)["requested"] == "restart"
    assert force_stops(ops)


@pytest.mark.parametrize("button", ["play_pause", "stop"])
def test_media_keys_refused_while_a_background_app_plays(ops, button):
    # Android routes media keys to the active session, not to the foreground launcher.
    ops.t.offline = True
    foreground(ops, "com.google.android.tvlauncher")
    ops.t.media = media_session("com.spotify.tv.android", 3)
    with pytest.raises(ShieldError, match="another app's media"):
        ops.remote(button)
    assert not keyevents(ops)
    assert ops.remote("down") == {"sent": "down"}
