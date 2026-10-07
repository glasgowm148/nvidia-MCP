"""H2: one guard (Kodi idle + foreground app + running state) for every disruptive tool."""

from dataclasses import replace
from pathlib import Path

import pytest

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
