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
    assert text.count("def pids(") == 1
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


def offline_permitted(ops):
    """The user's own NVIDIA_MCP_ALLOW_OFFLINE_RECOVERY=1, which the model flag needs."""
    ops.c = replace(ops.c, allow_offline_recovery=True)


def test_offline_recovery_flag_needs_the_users_env_opt_in(ops):
    # Kodi HTTP is down and nothing plays: the flag alone (model-controlled) is not enough.
    ops.t.offline = True
    ops.t.running = True
    with pytest.raises(ShieldError, match="NVIDIA_MCP_ALLOW_OFFLINE_RECOVERY") as error:
        ops.lifecycle("restart", allow_offline=True)
    assert error.value.kind == "offline_recovery_not_permitted"
    assert not force_stops(ops)
    assert not any(c[0] == "shell" and c[1][0] == "am" for c in ops.t.calls)
    offline_permitted(ops)
    assert ops.lifecycle("restart", allow_offline=True)["requested"] == "restart"
    assert force_stops(ops)


def test_offline_recovery_env_is_read_from_the_mcp_client_config(monkeypatch):
    monkeypatch.setenv("SHIELD_HOST", "192.168.1.50")
    monkeypatch.delenv("NVIDIA_MCP_ALLOW_OFFLINE_RECOVERY", raising=False)
    assert Config.from_env().allow_offline_recovery is False
    monkeypatch.setenv("NVIDIA_MCP_ALLOW_OFFLINE_RECOVERY", "1")
    assert Config.from_env().allow_offline_recovery is True


@pytest.mark.parametrize(
    "kind", ["authentication_denied", "rpc_error", "invalid_response", "service_error"]
)
def test_offline_recovery_needs_an_unreachable_kodi(ops, kind):
    offline_permitted(ops)

    # Wrong credentials or a protocol error mean Kodi's HTTP server is alive; it may be playing.
    def rpc(method, params=None):
        raise ShieldError("Kodi answered but not usefully", kind)

    ops.t.rpc = rpc
    with pytest.raises(ShieldError, match="unknown"):
        ops.lifecycle("restart", allow_offline=True)
    assert not force_stops(ops)


@pytest.mark.parametrize("state", [2, 3, 6])  # paused, playing, buffering
def test_offline_recovery_refused_while_android_reports_kodi_media(ops, state):
    offline_permitted(ops)
    ops.t.offline = True
    ops.t.media = media_session("org.xbmc.kodi", state)
    with pytest.raises(ShieldError, match="playing or paused"):
        ops.lifecycle("restart", allow_offline=True)
    assert not force_stops(ops)


def test_offline_recovery_refused_when_media_state_unreadable(ops):
    offline_permitted(ops)
    ops.t.offline = True
    shell = ops.t.shell
    ops.t.shell = lambda *a, **kw: "" if a == ("dumpsys", "media_session") else shell(*a, **kw)
    with pytest.raises(ShieldError, match="media playback state is unknown"):
        ops.lifecycle("stop", allow_offline=True)
    assert not force_stops(ops)


def test_offline_recovery_ignores_stopped_or_other_sessions(ops):
    offline_permitted(ops)
    ops.t.offline = True
    ops.t.media = (
        media_session("org.xbmc.kodi", 1)
        + media_session("org.xbmc.kodi", 3, active=False)
        + media_session("com.spotify.tv.android", 2, active=False)
    )
    assert ops.lifecycle("restart", allow_offline=True)["requested"] == "restart"
    assert force_stops(ops)


@pytest.mark.parametrize("button", ["play_pause", "stop", "down", "select"])
def test_any_button_refused_while_a_background_app_plays(ops, button):
    # Android routes media keys to the active session, and Select can open an app that
    # takes audio focus: background audio counts as somebody listening.
    ops.t.offline = True
    foreground(ops, "com.google.android.tvlauncher")
    ops.t.media = media_session("com.spotify.tv.android", 3)
    with pytest.raises(ShieldError, match="Another app's media"):
        ops.remote(button)
    assert not keyevents(ops)


@pytest.mark.parametrize("button", ["play_pause", "stop"])
def test_media_keys_refused_when_nothing_plays(ops, button):
    # With nothing playing, a media key only reaches the last media-button receiver and can
    # start a background app's audio.
    foreground(ops, "com.google.android.tvlauncher")
    with pytest.raises(ShieldError, match="Nothing is playing"):
        ops.remote(button)
    assert not keyevents(ops)


@pytest.mark.parametrize(
    "button,method", [("play_pause", "Player.PlayPause"), ("stop", "Player.Stop")]
)
def test_permitted_media_key_goes_to_kodis_player(ops, button, method):
    ops.c = replace(ops.c, allow_interrupt=True)
    ops.t.running = True
    ops.t.players = [{"playerid": 1, "type": "video"}]
    result = ops.remote(button, allow_during_playback=True)
    assert result["via"].endswith(method)
    assert (method, {"playerid": 1}) in ops.t.calls
    assert not keyevents(ops)


def test_interrupt_other_app_still_refuses_kodi_playback(ops):
    ops.c = replace(ops.c, allow_interrupt=True)
    ops.t.running = True
    ops.t.players = [{"playerid": 1, "type": "video"}]  # A film is playing in Kodi, in front.
    with pytest.raises(ShieldError, match="Kodi is playing"):
        ops.lifecycle("restart", interrupt_other_app=True)
    assert not force_stops(ops)
    ops.t.players = []
    ops.t.media = media_session("org.xbmc.kodi", 2)  # Android: Kodi paused.
    with pytest.raises(ShieldError, match="Kodi media playing or paused"):
        ops.lifecycle("restart", interrupt_other_app=True)
    assert not force_stops(ops)


def test_interrupt_other_app_covers_other_apps_only(ops):
    ops.c = replace(ops.c, allow_interrupt=True)
    foreground(ops, "com.netflix.ninja")
    ops.t.media = media_session("com.netflix.ninja", 3)
    assert ops.lifecycle("start", interrupt_other_app=True)["requested"] == "start"


def screen(ops, text):
    original = ops.t.shell

    def shell(*args, **kwargs):
        if args == ("dumpsys", "activity", "activities"):
            return text
        return original(*args, **kwargs)

    ops.t.shell = shell


DREAM = (
    "    mResumedActivity: ActivityRecord{1f u0 com.google.android.backdrop/"
    "android.service.dreams.DreamActivity t44}\n"
    "  topResumedActivity=ActivityRecord{1f u0 com.google.android.backdrop/"
    "android.service.dreams.DreamActivity t44}"
)
ASLEEP = (
    "  isSleeping=true\n"
    "    mLastPausedActivity: ActivityRecord{1f u0 org.xbmc.kodi/.Main t9}\n"
    "  topResumedActivity=null"
)


@pytest.mark.parametrize("text", [DREAM, ASLEEP])
def test_screensaver_or_sleep_is_nobody_watching(ops, text):
    screen(ops, text)
    ops.t.running = True
    assert ops.set_core_setting("audiooutput.passthrough", True)["current"] is True
    assert ops.lifecycle("restart")["requested"] == "restart"


@pytest.mark.parametrize("text", [DREAM, ASLEEP])
def test_screensaver_or_sleep_still_checks_playback(ops, text):
    screen(ops, text)
    ops.t.running = True
    ops.t.players = [{"playerid": 1}]
    with pytest.raises(ShieldError, match="Kodi is playing"):
        ops.set_core_setting("audiooutput.passthrough", True)
    ops.t.players = []
    ops.t.media = media_session("com.netflix.ninja", 2)  # A film paused under the screensaver.
    with pytest.raises(ShieldError, match="Another app's media"):
        ops.lifecycle("start")
    assert not force_stops(ops)
    assert not any(c[0] == "shell" and c[1][:2] == ("am", "start") for c in ops.t.calls)


def test_remote_refused_while_asleep(ops):
    screen(ops, ASLEEP)
    with pytest.raises(ShieldError, match="asleep"):
        ops.remote("select")
    assert not keyevents(ops)


def test_foreground_message_offers_no_flag_the_tool_lacks(ops):
    ops.t.running = True
    foreground(ops, "com.netflix.ninja")
    with pytest.raises(ShieldError) as error:
        ops.set_core_setting("audiooutput.passthrough", True)
    assert "=true" not in str(error.value)
    with pytest.raises(ShieldError, match="interrupt_other_app=true"):
        ops.lifecycle("start")


def test_restart_that_cannot_stop_kodi_says_so(ops):
    # Offline recovery goes straight to force-stop (Kodi HTTP cannot take a quit request).
    offline_permitted(ops)
    ops.t.offline = True
    shell = ops.t.shell
    ops.t.shell = lambda *a, **kw: "" if a[:2] == ("am", "force-stop") else shell(*a, **kw)
    ops.t.running = True  # pidof still finds Kodi after force-stop.
    with pytest.raises(ShieldError, match="still running after force-stop") as error:
        ops.lifecycle("restart", allow_offline=True)
    assert "editing files" not in str(error.value)
    assert not any(c[0] == "shell" and c[1][:2] == ("am", "start") for c in ops.t.calls)


def test_restart_reports_unconfirmed_stop(ops):
    offline_permitted(ops)
    ops.t.offline = True
    ops.t.running = True
    shell = ops.t.shell
    stopped = []

    def flaky(*args, **kwargs):
        if args[:2] == ("am", "force-stop"):
            stopped.append(True)
        elif stopped and args[:2] == ("sh", "-c"):
            raise ShieldError("ADB timed out", "timeout")
        return shell(*args, **kwargs)

    ops.t.shell = flaky
    with pytest.raises(ShieldError, match="force-stopped .*not started again"):
        ops.lifecycle("restart", allow_offline=True)


def guarded_writes(ops, tmp_path):
    """Every write that changes a running Kodi, with what it needs to get past validation."""
    addon = "plugin.video.example"
    (ops.c.mount / "addons" / addon).mkdir(parents=True)
    (ops.c.mount / "addons" / addon / "addon.xml").write_text(f'<addon id="{addon}" version="1"/>')
    ops.c = replace(ops.c, manager_token="synthetic-manager-token")
    plan = {"section_id": "hub:movies", "expected_revision": "r1", "rows": []}
    preview = ops.layout_preview(plan)["preview_id"]
    return {
        "kodi_set_setting": lambda: ops.set_core_setting("audiooutput.passthrough", True),
        "kodi_set_addon_setting": lambda: ops.set_addon_setting(addon, "1", "autoplay", True),
        "kodi_manager_widget_cache_refresh": ops.widget_cache_refresh,
        "kodi_layout_apply": lambda: ops.layout_apply(preview),
        "kodi_layout_rebuild": ops.rebuild_layout,
        "kodi_configuration_backup": ops.configuration_backup,
        "kodi_configuration_restore": lambda: ops.configuration_restore("backup-1"),
        "shield_remote": lambda: ops.remote("select"),
        "kodi_lifecycle": lambda: ops.lifecycle("restart"),
    }


GUARDED = [
    "kodi_set_setting",
    "kodi_set_addon_setting",
    "kodi_manager_widget_cache_refresh",
    "kodi_layout_apply",
    "kodi_layout_rebuild",
    "kodi_configuration_backup",
    "kodi_configuration_restore",
    "shield_remote",
    "kodi_lifecycle",
]


@pytest.mark.parametrize("name", GUARDED)
def test_running_kodi_write_refuses_another_app_in_front(ops, tmp_path, name):
    ops.t.running = True
    write = guarded_writes(ops, tmp_path)[name]
    foreground(ops, "com.netflix.ninja")
    before = len(ops.t.calls)
    with pytest.raises(ShieldError, match="Another TV app"):
        write()
    mutations = [
        c
        for c in ops.t.calls[before:]
        if c[0] == "Settings.SetSettingValue"
        or (isinstance(c[0], str) and c[0].startswith("/api/") and c[1] != "GET")
        or (c[0] == "shell" and c[1][0] in ("input", "am"))
    ]
    assert not mutations


@pytest.mark.parametrize("name", GUARDED)
def test_running_kodi_write_refuses_playback(ops, tmp_path, name):
    ops.t.running = True
    write = guarded_writes(ops, tmp_path)[name]
    ops.t.players = [{"playerid": 1}]
    with pytest.raises(ShieldError, match="playing"):
        write()


def test_guarded_list_covers_every_write_tool_that_needs_running_kodi():
    from test_tools import WRITE_TOOLS

    # File edits need Kodi stopped; APK installs have their own guard tests in test_apks.
    elsewhere = {"kodi_patch_apply", "kodi_patch_file", "kodi_restore_file", "shield_apk_apply"}
    assert set(WRITE_TOOLS) - elsewhere == set(GUARDED)
