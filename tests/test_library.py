"""nvidia_mcp.Shield, the library API (docs/library.md), against the replayed reference Shield."""

import stat

import pytest
from replay import KODI_ROOT, SCENARIOS, ReplayShield, capture, config

import nvidia_mcp
from nvidia_mcp import Config, Shield, ShieldError
from nvidia_mcp.device import UNATTENDED


def shield(tmp_path, scenario, route="direct", **overrides):
    cfg = config(tmp_path, **overrides)
    return Shield(cfg, transport=ReplayShield(cfg, scenario, route))


def test_package_exports_the_library():
    assert nvidia_mcp.Shield is Shield and nvidia_mcp.Config is Config
    assert issubclass(nvidia_mcp.ShieldError, Exception)
    assert nvidia_mcp.__version__.count(".") == 2


VERDICTS = {
    "idle_home": "idle",
    "launcher_foreground": "idle",
    "exit_hang": "idle",
    "screensaver": "screensaver",
    "low_memory_kill": "screensaver",
    "paused_osd": "paused",
    "other_app_media": "other_app",
}


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_viewing_state_verdict(tmp_path, scenario):
    assert shield(tmp_path, scenario).viewing_state()["verdict"] == VERDICTS[scenario]


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_verdict_agrees_with_the_guard(tmp_path, scenario):
    """An unattended verdict is exactly when a guarded action (starting Kodi) goes ahead."""
    verdict = shield(tmp_path, scenario).viewing_state()["verdict"]
    tv = shield(tmp_path, scenario)
    try:
        tv.start_kodi()
        allowed = True
    except ShieldError:
        allowed = False
    assert allowed == (verdict in UNATTENDED)


def test_viewing_state_reports_each_signal(tmp_path):
    state = shield(tmp_path, "paused_osd").viewing_state()
    assert state["players"] == [{"playerid": 1, "playertype": "internal", "type": "video"}]
    assert state["media_sessions"] == [{"package": "org.xbmc.kodi", "state": 2}]
    assert (state["screen"], state["foreground"]) == ("app", "org.xbmc.kodi")
    assert state["wakefulness"] == "Awake" and state["kodi_running"] is True
    assert state["unavailable"] == {}

    state = shield(tmp_path, "screensaver").viewing_state()
    assert state["foreground"] == "com.google.android.backdrop"
    assert state["wakefulness"] == "Dreaming"

    state = shield(tmp_path, "launcher_foreground").viewing_state()
    assert state["foreground"] == "com.spocky.projengmenu"
    # Kodi's lingering STOPPED session is listed but does not count as viewing.
    assert state["media_sessions"] == [{"package": "org.xbmc.kodi", "state": 1}]


def test_low_memory_kill_is_visible(tmp_path):
    tv = shield(tmp_path, "low_memory_kill")
    state = tv.viewing_state()
    assert state["kodi_running"] is False and state["players"] == []
    assert tv.kodi_alive() is False
    assert tv.process_deaths() == [
        {
            "time": "10-11 16:16:00.000",
            "event": "am_proc_died",
            "pid": 10785,
            "oom_adj": 200,
            "proc_state": 2,
        }
    ]
    assert tv.process_deaths("com.netflix.ninja") == []


def test_kodi_playing_rather_than_paused(tmp_path):
    tv = shield(tmp_path, "paused_osd")
    tv.transport.answers_rpc["Player.GetProperties"] = {"speed": 1}
    assert tv.viewing_state()["verdict"] == "playing"


def test_unreadable_signals_make_the_verdict_unknown(tmp_path):
    tv = shield(tmp_path, "idle_home")
    tv.transport.media = "Can't find service: media_session\n"
    state = tv.viewing_state()
    assert state["verdict"] == "unknown"
    assert state["unavailable"] == {"media_sessions": "playback_unknown"}

    # Kodi's process is alive but its HTTP server is closed (an exit in progress).
    tv = shield(tmp_path, "exit_hang")
    tv.transport.http_up = False
    state = tv.viewing_state()
    assert state["verdict"] == "unknown" and state["unavailable"]["players"] == "unreachable"


def test_sleeping_shield_is_asleep(tmp_path):
    # Not yet observed on the reference Shield: its power dump with the state changed.
    tv = shield(tmp_path, "launcher_foreground")
    tv.transport.power = capture("power-awake.txt").replace("Awake", "Asleep")
    assert tv.viewing_state()["verdict"] == "asleep"


def test_kodi_alive(tmp_path):
    assert shield(tmp_path, "idle_home").kodi_alive() is True


# --- quit / start ------------------------------------------------------------------------------


def test_quit_kodi_clean_exit(tmp_path):
    tv = shield(tmp_path, "idle_home")
    assert tv.quit_kodi()["stopped_by"] == "Application.Quit"
    assert tv.kodi_alive() is False and not tv.transport.sent("am", "force-stop")


def test_quit_kodi_force_stops_only_a_saved_hung_exit(tmp_path):
    tv = shield(tmp_path, "exit_hang")
    result = tv.quit_kodi(wait=0)
    assert result["stopped_by"] == "force-stop after a hung exit"
    assert result["exit_evidence"][-1].endswith("Stopping all")
    assert tv.operations.quit_wait == 30  # The caller's wait does not leak into the server.

    tv = shield(tmp_path, "exit_hang")
    log = capture("kodi-exit-hang-idle.txt").split("Saving skin settings")[0]
    tv.transport.files[f"{KODI_ROOT}/temp/kodi.log"] = log.encode()
    with pytest.raises(ShieldError) as exc:
        tv.quit_kodi(wait=0)
    assert exc.value.kind == "exit_hung"
    assert tv.kodi_alive() and not tv.transport.sent("am", "force-stop")


def test_quit_kodi_refuses_while_a_film_is_paused(tmp_path):
    tv = shield(tmp_path, "paused_osd")
    with pytest.raises(ShieldError, match="Kodi is playing"):
        tv.quit_kodi()
    assert not tv.transport.rpc_sent("Application.Quit")


def test_quit_kodi_when_already_gone(tmp_path):
    tv = shield(tmp_path, "low_memory_kill")
    assert tv.quit_kodi()["stopped_by"] is None
    assert not tv.transport.rpc_sent("Application.Quit") and not tv.transport.sent("am")


def test_mutations_need_writes_enabled(tmp_path):
    tv = shield(tmp_path, "idle_home", allow_writes=False)
    for call in (tv.quit_kodi, tv.start_kodi, lambda: tv.push_verified(__file__, "/sdcard/x")):
        with pytest.raises(ShieldError, match="Write tools are disabled"):
            call()
    assert tv.kodi_alive() and not tv.transport.sent("am")


def test_start_kodi_waits_until_json_rpc_answers(tmp_path):
    tv = shield(tmp_path, "low_memory_kill")
    result = tv.start_kodi(wait=5)
    assert result["ready"] is True and tv.kodi_alive()
    assert tv.transport.sent("am", "start", "-n", "org.xbmc.kodi/.Splash")


# --- JSON-RPC routes ---------------------------------------------------------------------------


def http_urls(tv):
    return {call[1] for call in tv.transport.calls if call[0] == "http"}


def test_direct_route(tmp_path):
    tv = shield(tmp_path, "idle_home")
    assert (
        tv.rpc("Application.GetProperties", {"properties": ["version"]})["version"]["major"] == 22
    )
    assert http_urls(tv) == {"http://192.168.0.20:8080/jsonrpc"}


def test_forward_route_when_the_lan_is_blocked(tmp_path):
    tv = shield(tmp_path, "idle_home", route="forward")
    tv.transport.lan_blocked = True
    version = tv.rpc("Application.GetProperties", {"properties": ["version"]})["version"]
    assert (version["tag"], version["tagversion"]) == ("releasecandidate", "1")
    # The guard's own JSON-RPC calls use the same forward.
    assert tv.viewing_state()["verdict"] == "idle"
    assert http_urls(tv) == {"http://127.0.0.1:41234/jsonrpc"}
    forwards = [c for c in tv.transport.calls if c[0] == "adb" and c[1][0] == "forward"]
    assert forwards == [("adb", ("forward", "tcp:0", "tcp:8080"))]
    tv.close()
    assert tv.transport.calls[-1] == ("adb", ("forward", "--remove", "tcp:41234"))


def test_auto_route(tmp_path):
    tv = shield(tmp_path, "idle_home", route="auto")
    tv.transport.lan_blocked = True
    assert tv.rpc("Player.GetActivePlayers") == []
    assert tv.transport.forward_port == 41234

    tv = shield(tmp_path, "idle_home", route="auto")
    assert tv.rpc("Player.GetActivePlayers") == []
    assert tv.transport.forward_port is None
    assert http_urls(tv) == {"http://192.168.0.20:8080/jsonrpc"}


def test_rpc_errors_are_shield_errors(tmp_path):
    with pytest.raises(ShieldError, match="Method not found") as exc:
        shield(tmp_path, "idle_home").rpc("Addons.ExecuteAddon", {"addonid": "x"})
    assert exc.value.kind == "rpc_error"


def test_unknown_route_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        Shield(config(tmp_path), kodi_route="lan")


# --- raw adb and files -------------------------------------------------------------------------


def test_adb_takes_an_argument_list(tmp_path):
    tv = shield(tmp_path, "idle_home")
    assert tv.adb(["get-state"]) == b"device\n"
    assert "mWakefulness=Awake" in tv.shell(["dumpsys", "power"])
    with pytest.raises(TypeError):
        tv.adb("shell reboot")


def test_pull_bytes_and_to_a_private_file(tmp_path):
    tv = shield(tmp_path, "exit_hang")
    remote = f"{KODI_ROOT}/temp/kodi.log"
    assert tv.pull(remote) == capture("kodi-exit-hang-idle.txt").encode()
    target = tmp_path / "kodi.log"
    assert tv.pull(remote, target) == target.stat().st_size
    assert target.read_bytes() == capture("kodi-exit-hang-idle.txt").encode()
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    with pytest.raises(ShieldError) as exc:
        tv.pull(f"{KODI_ROOT}/temp/missing.log")
    assert exc.value.kind == "not_found"


@pytest.mark.parametrize(
    "path", ["/data/data/org.xbmc.kodi/x", "/sdcard/../data/x", "relative/x", "/sdcard/dir/"]
)
def test_file_helpers_refuse_other_paths(tmp_path, path):
    tv = shield(tmp_path, "idle_home")
    with pytest.raises(ShieldError, match="Device paths must be absolute"):
        tv.pull(path)
    with pytest.raises(ShieldError, match="Device paths must be absolute"):
        tv.push_verified(__file__, path)
    assert not [c for c in tv.transport.calls if c[0] == "adb" and c[1][0] == "push"]


def test_push_verified_replaces_atomically(tmp_path):
    tv = shield(tmp_path, "idle_home")
    remote = f"{KODI_ROOT}/addons/script.example/relaunch.sh"
    tv.transport.files[remote] = b"old"
    local = tmp_path / "relaunch.sh"
    local.write_bytes(b"#!/system/bin/sh\necho new\n")
    result = tv.push_verified(local, remote)
    assert tv.transport.files[remote] == local.read_bytes()
    assert result["bytes"] == len(local.read_bytes()) and len(result["sha256"]) == 64
    assert tv.transport.sent("chmod", "644")  # The existing file's mode is kept.
    assert [path for path in tv.transport.files if ".nvidia-mcp-" in path] == []


def test_push_verified_never_replaces_with_a_corrupt_copy(tmp_path):
    tv = shield(tmp_path, "idle_home")
    remote = f"{KODI_ROOT}/addons/script.example/relaunch.sh"
    tv.transport.files[remote] = b"old"
    tv.transport.corrupt_next_push = True
    local = tmp_path / "relaunch.sh"
    local.write_bytes(b"new contents")
    with pytest.raises(ShieldError, match="was not replaced") as exc:
        tv.push_verified(local, remote)
    assert exc.value.kind == "verify_failed"
    assert tv.transport.files[remote] == b"old"
    assert [path for path in tv.transport.files if ".nvidia-mcp-" in path] == []


def test_push_verified_new_file(tmp_path):
    tv = shield(tmp_path, "idle_home")
    local = tmp_path / "a.zip"
    local.write_bytes(b"PK\x03\x04")
    tv.push_verified(local, "/data/local/tmp/a.zip", mode="600")
    assert tv.transport.files["/data/local/tmp/a.zip"] == b"PK\x03\x04"
    assert tv.transport.sent("chmod", "600")
    with pytest.raises(ShieldError, match="octal"):
        tv.push_verified(local, "/data/local/tmp/a.zip", mode="u+x")


# --- memory -----------------------------------------------------------------------------------


def test_memory_after_an_evening_of_playback(tmp_path):
    memory = shield(tmp_path, "idle_home").memory()
    assert memory["mem_available_kb"] // 1024 == 467
    assert memory["swap_used_percent"] == 96.0
    assert memory["kodi"]["pss_kb"] > 1_000_000  # > 1 GB
    assert memory["kodi"]["native_heap_kb"] / memory["kodi"]["pss_kb"] > 0.8


def test_memory_without_kodi(tmp_path):
    memory = shield(tmp_path, "low_memory_kill").memory()
    assert memory["kodi"] is None and memory["mem_total_kb"] == 3016708
