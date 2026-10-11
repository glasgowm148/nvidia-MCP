"""Every guard decision and lifecycle path, replayed from the reference Shield's own output
(tests/replay.py lists where each capture comes from). Assertions are about what the user or
the TV sees: which refusal text comes back, whether Kodi was asked to quit, force-stopped,
started or sent a key."""

import pytest
from replay import KODI_ROOT, SCENARIOS, ReplayShield, capture, config

from nvidia_mcp.config import ShieldError
from nvidia_mcp.diagnostics import readiness
from nvidia_mcp.operations import Operations

KODI_PLAYING = "Kodi is playing. Wait until viewing has finished"
NETFLIX = r"Another app's media is playing or paused \(com\.netflix\.ninja\)"
UNKNOWN = "Playback state is unknown; no disruptive action performed"
OK = None


def tv(tmp_path, scenario, **overrides):
    ops = Operations(ReplayShield(config(tmp_path, **overrides), scenario))
    ops.quit_wait, ops.quit_poll = 0, 0
    return ops


def test_every_scenario_is_covered():
    assert set(SCENARIOS) == set(EXPECTED)


# scenario: (remote select, kodi_set_setting, kodi_lifecycle start, kodi_lifecycle stop)
EXPECTED = {
    "idle_home": (OK, OK, OK, OK),
    "launcher_foreground": (OK, OK, OK, OK),
    "screensaver": (OK, OK, OK, OK),
    "exit_hang": (OK, OK, OK, OK),
    "paused_osd": (KODI_PLAYING, KODI_PLAYING, KODI_PLAYING, KODI_PLAYING),
    "other_app_media": (NETFLIX, NETFLIX, NETFLIX, NETFLIX),
    # Kodi was killed: nothing to stop, and its settings cannot be reached.
    "low_memory_kill": (OK, UNKNOWN, OK, UNKNOWN),
}
ACTIONS = {
    "remote": lambda ops: ops.remote("select"),
    "setting": lambda ops: ops.set_core_setting("audiooutput.passthrough", True),
    "start": lambda ops: ops.lifecycle("start"),
    "stop": lambda ops: ops.lifecycle("stop"),
}
CASES = [
    (scenario, action, refusal)
    for scenario, refusals in EXPECTED.items()
    for action, refusal in zip(ACTIONS, refusals, strict=True)
]


@pytest.mark.parametrize(("scenario", "action", "refusal"), CASES)
def test_guard_decision(tmp_path, scenario, action, refusal):
    ops = tv(tmp_path, scenario)
    device = ops.t
    if refusal:
        with pytest.raises(ShieldError, match=refusal):
            ACTIONS[action](ops)
        # A refusal changes nothing on the TV.
        assert not device.sent("input") and not device.sent("am")
        assert not device.rpc_sent("Application.Quit")
        assert not device.rpc_sent("Settings.SetSettingValue")
        return
    result = ACTIONS[action](ops)
    if action == "remote":
        assert result == {"sent": "select"} and device.sent("input", "keyevent", "23")
    elif action == "setting":
        assert result["current"] is True and result["backup_id"]
    elif action == "start":
        assert device.sent("am", "start", "-n", "org.xbmc.kodi/.Splash")
    else:
        assert device.rpc_sent("Application.Quit")
        assert not device.kodi_running


def test_refusals_name_what_is_being_watched(tmp_path):
    with pytest.raises(ShieldError) as paused:
        tv(tmp_path, "paused_osd").lifecycle("stop")
    with pytest.raises(ShieldError) as netflix:
        tv(tmp_path, "other_app_media").remote("select")
    assert "Wait until viewing has finished" in str(paused.value)
    assert "com.netflix.ninja" in str(netflix.value) and "[other_app_playing]" in str(netflix.value)


def test_kodi_paused_under_a_failed_http_server_still_refuses(tmp_path):
    # Kodi's HTTP answers nothing, but Android still holds its paused film (state=2).
    ops = tv(tmp_path, "paused_osd", allow_offline_recovery=True)
    ops.t.http_up = False
    with pytest.raises(ShieldError, match="Android reports Kodi media is playing or paused"):
        ops.lifecycle("stop", allow_offline=True)
    assert not ops.t.sent("am", "force-stop")


def test_media_keys_do_nothing_when_nobody_is_watching(tmp_path):
    ops = tv(tmp_path, "launcher_foreground")
    with pytest.raises(ShieldError, match="would only wake another app's media"):
        ops.remote("play_pause")
    assert not ops.t.sent("input")


# --- kodi_lifecycle stop: clean exit vs. the hung exits of 2026-10-11 --------------------------


@pytest.mark.parametrize("scenario", ["idle_home", "launcher_foreground", "screensaver"])
def test_clean_exit_needs_no_force_stop(tmp_path, scenario):
    ops = tv(tmp_path, scenario)
    result = ops.lifecycle("stop")
    assert result["stopped_by"] == "Application.Quit"
    assert result["note"] == "Kodi has exited."
    assert not ops.t.sent("am", "force-stop")


@pytest.mark.parametrize("log", ["kodi-exit-hang-idle.txt", "kodi-exit-hang-after-playback.txt"])
def test_hung_exit_after_saving_is_force_stopped_with_the_evidence(tmp_path, log):
    ops = tv(tmp_path, "exit_hang")
    ops.t.files[f"{KODI_ROOT}/temp/kodi.log"] = capture(log).encode()
    result = ops.lifecycle("stop")
    assert result["stopped_by"] == "force-stop after a hung exit"
    assert [line.split("<general>: ")[1] for line in result["exit_evidence"]] == [
        "Stopping the application...",
        "Saving settings",
        "Saving skin settings",
        "Stopping all",
    ]
    assert ops.t.sent("am", "force-stop", "org.xbmc.kodi") and not ops.t.kodi_running


def test_restart_after_a_hung_exit_starts_kodi_again(tmp_path):
    ops = tv(tmp_path, "exit_hang")
    result = ops.lifecycle("restart")
    assert result["stopped_by"] == "force-stop after a hung exit"
    assert ops.t.sent("am", "start") and ops.t.kodi_running


def cut_before(log, message):
    lines = capture(log).splitlines()
    return "\n".join(lines[: next(i for i, s in enumerate(lines) if s.endswith(message))])


@pytest.mark.parametrize(
    "log",
    [
        # The exit stopped mid-save: skin settings were not written yet.
        cut_before("kodi-exit-hang-idle.txt", "Saving skin settings"),
        # No exit logged at all.
        cut_before("kodi-exit-hang-idle.txt", "XBMCApp: Finishing the activity"),
        # A previous Kodi's clean exit, then this Kodi started and has not saved anything.
        capture("kodi-exit-clean.txt")
        + "\n".join(capture("kodi-exit-hang-idle.txt").splitlines()[:6]),
    ],
    ids=["mid-save", "no-exit-logged", "previous-process-only"],
)
def test_hung_exit_without_proof_of_saving_is_left_alone(tmp_path, log):
    ops = tv(tmp_path, "exit_hang")
    ops.t.files[f"{KODI_ROOT}/temp/kodi.log"] = log.encode()
    with pytest.raises(ShieldError, match="kodi.log does not show it finished saving") as exc:
        ops.lifecycle("restart")
    assert exc.value.kind == "exit_hung"
    assert "it was not started again" in exc.value.message
    assert "Settings > Apps > Kodi > Force stop" in exc.value.message
    assert not ops.t.sent("am", "force-stop") and not ops.t.sent("am", "start")
    assert ops.t.kodi_running


def test_hung_exit_with_a_paused_film_again_is_left_for_the_viewer(tmp_path):
    ops = tv(tmp_path, "exit_hang")
    ops.t.after_quit = lambda: setattr(ops.t, "media", capture("media_session-kodi-paused.txt"))
    with pytest.raises(
        ShieldError, match="the TV guard refused a force-stop: Android reports Kodi"
    ):
        ops.lifecycle("stop")
    assert not ops.t.sent("am", "force-stop")


def test_hung_exit_while_netflix_plays_is_left_alone(tmp_path):
    ops = tv(tmp_path, "exit_hang")
    ops.t.after_quit = lambda: setattr(ops.t, "media", capture("media_session-netflix-paused.txt"))
    with pytest.raises(ShieldError, match="TV guard refused a force-stop: Another app's media"):
        ops.lifecycle("stop")
    assert not ops.t.sent("am", "force-stop")


def test_hung_exit_behind_the_screensaver_is_force_stopped(tmp_path):
    ops = tv(tmp_path, "exit_hang")
    ops.t.after_quit = lambda: setattr(ops.t, "activities", capture("activities-dream.txt"))
    assert ops.lifecycle("stop")["stopped_by"] == "force-stop after a hung exit"


# --- Diagnostics report the real numbers ----------------------------------------------------


def test_shield_status_reports_low_memory_and_full_swap(tmp_path):
    status = tv(tmp_path, "low_memory_kill").shield_status()
    memory = status["health"]["memory_kb"]
    assert memory["MemAvailable"] // 1024 == 467
    swap_used = 1 - memory["SwapFree"] / memory["SwapTotal"]
    assert round(swap_used * 100) == 96
    assert status["kodi_running"] is False


def test_kodi_status_reports_the_release_candidate(tmp_path):
    status = tv(tmp_path, "paused_osd").kodi_status()
    assert status["application"]["version"]["tag"] == "releasecandidate"
    assert status["application"]["version"]["major"] == 22
    assert status["players"] == [{"playerid": 1, "playertype": "internal", "type": "video"}]


def test_kodi_status_after_a_low_memory_kill_says_kodi_is_unreachable(tmp_path):
    status = tv(tmp_path, "low_memory_kill").kodi_status()
    for name in ("application", "screen", "profile", "players"):
        assert status[name]["unavailable"].startswith("Cannot reach device HTTP service")


def test_connection_check_separates_adb_from_a_killed_kodi(tmp_path):
    ready = readiness(tv(tmp_path, "low_memory_kill"))
    assert ready["adb"] == {"state": "ready"}
    assert ready["kodi_http"]["state"] == "unreachable"


def test_kodi_logs_show_where_the_exit_stopped(tmp_path):
    result = tv(tmp_path, "exit_hang").logs(lines=5)
    assert result["lines"].splitlines()[-2].endswith("Stopping all")
