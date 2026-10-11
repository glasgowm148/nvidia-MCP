"""kodi_lifecycle stop/restart: Application.Quit first, a bounded wait, and a force-stop only
after kodi.log shows Kodi saved its settings and the TV guard still passes.

On the household Shield (Kodi 22.0 RC1, 2026-10-11) Kodi hung at "Stopping all" for more than
90 s after quitting with a paused video. The log lines below are from that exit."""

import pytest
from conftest import media_session

from nvidia_mcp.config import ShieldError
from nvidia_mcp.operations import settings_saved_on_exit

STARTED = (
    "2026-10-10 23:59:55.636 T:13579    info <general>: Starting Kodi (22.0-RC1 (21.90.901) "
    "Git:20260927-28ea2eac1e). Platform: Android ARM 64-bit\n"
)
HUNG_EXIT = (
    "2026-10-11 14:07:24.777 T:13579    info <general>: XBMCApp: Finishing the activity\n"
    "2026-10-11 14:07:25.959 T:13579    info <general>: CWinSystemAndroid::DestroyWindow\n"
    "2026-10-11 14:07:27.363 T:13578    info <general>: XBMCApp: Stopping the application...\n"
    "2026-10-11 14:07:27.535 T:13579    info <general>: Stopping the application...\n"
    "2026-10-11 14:07:27.536 T:13579    info <general>: Stopping player\n"
    "2026-10-11 14:07:27.536 T:13579    info <general>: Storing total System Uptime\n"
    "2026-10-11 14:07:27.536 T:13579    info <general>: Saving settings\n"
    "2026-10-11 14:07:27.544 T:13579    info <general>: Saving skin settings\n"
    "2026-10-11 14:07:27.555 T:13579    info <general>: Stopping all\n"
    "2026-10-11 14:07:28.284 T:13709    info <general>: Example add-on: service update finished\n"
)
# The same exit, cut off before the skin settings were written.
MID_SAVE = HUNG_EXIT.split("2026-10-11 14:07:27.544")[0]
PROJECTIVY = (
    "    mResumedActivity: ActivityRecord{357b962 u0 com.spocky.projengmenu/"
    ".ui.home.MainActivity t3246}\n"
)


def shield(ops, *, exits, log=None, quit_error=None, after_quit=None):
    """Kodi running and idle with Projectivy in front; Application.Quit either ends the
    process or leaves it hung. ``after_quit`` may change media/activities once quit is sent."""
    ops.t.running = True
    tv = {"activities": PROJECTIVY}
    if log is not None:
        (ops.c.mount / "temp").mkdir(exist_ok=True)
        # Bytes, so Windows newline translation cannot change what the parser sees.
        (ops.c.mount / "temp" / "kodi.log").write_bytes(("\ufeff" + log).encode())
    rpc, shell = ops.t.rpc, ops.t.shell

    def fake_rpc(method, params=None):
        if method == "Application.Quit":
            ops.t.calls.append((method, params))
            if after_quit:
                after_quit(ops, tv)
            if quit_error:
                raise quit_error
            ops.t.running = not exits
            return "OK"
        return rpc(method, params)

    def fake_shell(*args, **kwargs):
        if args == ("dumpsys", "activity", "activities"):
            return tv["activities"]
        return shell(*args, **kwargs)

    ops.t.rpc, ops.t.shell = fake_rpc, fake_shell


def shell_calls(ops, *prefix):
    return [c for c in ops.t.calls if c[0] == "shell" and c[1][: len(prefix)] == prefix]


def quits(ops):
    return [c for c in ops.t.calls if c[0] == "Application.Quit"]


@pytest.mark.parametrize("action", ["stop", "restart"])
def test_kodi_is_asked_to_quit_before_any_force_stop(ops, action):
    shield(ops, exits=True)
    result = ops.lifecycle(action)
    assert quits(ops) and not shell_calls(ops, "am", "force-stop")
    assert result["stopped_by"] == "Application.Quit"
    assert bool(shell_calls(ops, "am", "start")) == (action == "restart")


def test_a_dropped_connection_during_quit_counts_as_sent(ops):
    def exits(ops, tv):
        ops.t.running = False

    shield(
        ops,
        exits=True,
        quit_error=ShieldError("Cannot reach device HTTP service", "timeout"),
        after_quit=exits,
    )
    assert ops.lifecycle("stop")["stopped_by"] == "Application.Quit"
    assert not shell_calls(ops, "am", "force-stop")


def test_a_refused_quit_leaves_kodi_alone(ops):
    shield(ops, exits=False, quit_error=ShieldError("Kodi Application.Quit failed", "rpc_error"))
    with pytest.raises(ShieldError, match="Application.Quit") as error:
        ops.lifecycle("restart")
    assert error.value.kind == "quit_failed"
    assert not shell_calls(ops, "am")


@pytest.mark.parametrize("action", ["stop", "restart"])
def test_hung_exit_after_saved_settings_is_force_stopped(ops, action):
    # The real hang: settings and skin settings saved, then stuck at "Stopping all". The
    # launcher is in front and Kodi's session lingers at STOPPED (state=1).
    def lingering(ops, tv):
        ops.t.media = media_session("org.xbmc.kodi", 1)

    shield(ops, exits=False, log=STARTED + HUNG_EXIT, after_quit=lingering)
    result = ops.lifecycle(action)
    assert result["stopped_by"] == "force-stop after a hung exit"
    assert "Saving skin settings" in "\n".join(result["exit_evidence"])
    assert shell_calls(ops, "am", "force-stop")
    assert bool(shell_calls(ops, "am", "start")) == (action == "restart")


@pytest.mark.parametrize(
    "case",
    ["no_log", "mid_save", "paused_session", "other_app", "earlier_process"],
)
def test_hung_exit_without_evidence_or_guard_is_left_for_the_user(ops, case):
    log, after = STARTED + HUNG_EXIT, None
    if case == "no_log":
        log = None
    elif case == "mid_save":
        log = STARTED + MID_SAVE

    def paused_session(ops, tv):  # Android still holds a paused film.
        ops.t.media = media_session("org.xbmc.kodi", 2)

    def other_app(ops, tv):  # Somebody opened Netflix while Kodi was closing.
        tv["activities"] = "mResumedActivity: ActivityRecord{1 u0 com.netflix.ninja/.Main t9}"

    if case == "paused_session":
        after = paused_session
    elif case == "other_app":
        after = other_app
    elif case == "earlier_process":
        log = HUNG_EXIT + STARTED  # kodi.log of a newer Kodi run: the old exit does not count.
    shield(ops, exits=False, log=log, after_quit=after)
    with pytest.raises(ShieldError, match="did not exit") as error:
        ops.lifecycle("restart")
    assert error.value.kind == "exit_hung"
    assert "not started again" in str(error.value)
    assert not shell_calls(ops, "am", "force-stop")
    assert not shell_calls(ops, "am", "start")


def test_wait_is_bounded_and_polls_until_kodi_exits(ops):
    shield(ops, exits=False)
    polls = []
    running = ops.kodi_running

    def probe():
        polls.append(1)
        if len(polls) == 3:
            ops.t.running = False
        return running()

    ops.kodi_running = probe
    ops.quit_wait, ops.quit_poll = 5, 0
    assert ops.lifecycle("stop")["stopped_by"] == "Application.Quit"
    assert len(polls) == 3


def test_parser_needs_the_whole_save_sequence():
    assert settings_saved_on_exit(STARTED + HUNG_EXIT)
    assert settings_saved_on_exit(HUNG_EXIT.replace("\n", "\r\n"))
    assert not settings_saved_on_exit(STARTED + MID_SAVE)
    assert not settings_saved_on_exit(HUNG_EXIT + STARTED)
    assert not settings_saved_on_exit(HUNG_EXIT.replace("Saving settings", "Saving settings!"))


KODI_IN_FRONT = "    mResumedActivity: ActivityRecord{20632b5 u0 org.xbmc.kodi/.Main t3482}\n"


def respawn(activities=None):
    """Kodi exits, then Android starts a new org.xbmc.kodi process (pid 29040 on 2026-10-11)."""

    def after(ops, tv):
        ops.t.pid = "29040"
        if activities:
            tv["activities"] = activities

    return after


@pytest.mark.parametrize("action", ["stop", "restart"])
def test_a_new_kodi_process_after_the_exit_is_not_a_hung_exit(ops, action):
    shield(ops, exits=False, after_quit=respawn())
    result = ops.lifecycle(action)
    assert result["stopped_by"] == "Application.Quit"
    assert result["respawned_process_stopped"] == ["29040"]
    assert len(shell_calls(ops, "am", "force-stop")) == 1
    assert bool(shell_calls(ops, "am", "start")) == (action == "restart")


def test_a_kodi_someone_opened_again_is_left_running(ops):
    shield(ops, exits=False, after_quit=respawn(KODI_IN_FRONT))
    with pytest.raises(ShieldError, match="opened again") as error:
        ops.lifecycle("stop")
    assert error.value.kind == "restarted"
    assert not shell_calls(ops, "am", "force-stop")


def test_the_same_process_still_running_is_still_a_hung_exit(ops):
    shield(ops, exits=False, log=STARTED + MID_SAVE)
    with pytest.raises(ShieldError, match="did not exit") as error:
        ops.lifecycle("stop")
    assert error.value.kind == "exit_hung"
    assert not shell_calls(ops, "am", "force-stop")
