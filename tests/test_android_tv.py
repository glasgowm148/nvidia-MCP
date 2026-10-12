"""Synthetic Android TV / Fire OS cases, not captures from tested physical devices."""

import io
import subprocess
from dataclasses import replace

import pytest
from conftest import media_session

from nvidia_mcp import AndroidTV, Shield
from nvidia_mcp.config import Config, ShieldError
from nvidia_mcp.operations import foreground_state
from nvidia_mcp.transport import Transport


@pytest.fixture
def device_environment(monkeypatch):
    for key in ("ANDROID_TV_HOST", "ANDROID_TV_ADB_PORT", "SHIELD_HOST", "SHIELD_ADB_PORT"):
        monkeypatch.delenv(key, raising=False)
    return monkeypatch


def test_portable_config_preserves_legacy_and_dynamic_ports(device_environment):
    env = device_environment
    env.setenv("ANDROID_TV_HOST", "192.168.0.80")
    env.setenv("ANDROID_TV_ADB_PORT", "37123")
    assert Config.from_env().serial == "192.168.0.80:37123"
    env.setenv("SHIELD_HOST", "192.168.0.80")
    env.setenv("SHIELD_ADB_PORT", "037123")
    assert Config.from_env().adb_port == 37123
    env.delenv("ANDROID_TV_HOST")
    env.delenv("ANDROID_TV_ADB_PORT")
    assert Config.from_env().serial == "192.168.0.80:37123"
    assert AndroidTV is Shield


@pytest.mark.parametrize(
    "key,value", [("SHIELD_HOST", "192.168.0.81"), ("SHIELD_ADB_PORT", "5555")]
)
def test_conflicting_aliases_never_choose_another_device(device_environment, key, value):
    env = device_environment
    env.setenv("ANDROID_TV_HOST", "192.168.0.80")
    env.setenv("ANDROID_TV_ADB_PORT", "37123")
    env.setenv(key, value)
    with pytest.raises(ShieldError, match="conflict"):
        Config.from_env()


def activity(ops, text):
    original = ops.t.shell

    def shell(*args, **kwargs):
        if args == ("dumpsys", "activity", "activities"):
            return text
        return original(*args, **kwargs)

    ops.t.shell = shell


@pytest.mark.parametrize(
    "field", ["mFocusedActivity", "mResumedActivity", "topResumedActivity", "ResumedActivity"]
)
def test_fire_home_idle_remote_and_start(ops, field):
    ops.t.offline = True  # Kodi stopped, so its HTTP server is unavailable.
    activity(ops, f"  {field}: ActivityRecord{{1 u0 com.amazon.tv.launcher/.Home t1}}")
    assert ops.remote("select") == {"sent": "select"}
    assert ops.lifecycle("start")["requested"] == "start"


@pytest.mark.parametrize("state", [2, 3, 6])
def test_fire_home_does_not_override_background_media(ops, state):
    activity(ops, "mFocusedActivity: com.amazon.tv.launcher/.Home")
    ops.t.media = media_session("com.amazon.avod", state)
    with pytest.raises(ShieldError) as error:
        ops.remote("home")
    assert error.value.kind == "other_app_playing"
    assert not any(
        call[0] == "shell" and call[1][:2] == ("input", "keyevent") for call in ops.t.calls
    )


def test_old_foreground_other_app_still_blocks(ops):
    activity(ops, "mFocusedActivity: com.amazon.avod/.Playback")
    with pytest.raises(ShieldError, match="Another TV app"):
        ops.lifecycle("start")


@pytest.mark.parametrize("resumed", ["null", "com.amazon.avod/.Playback"])
def test_old_focus_cannot_override_modern_resumed(ops, resumed):
    activity(ops, f"mFocusedActivity: com.amazon.tv.launcher/.Home\nmResumedActivity: {resumed}")
    with pytest.raises(ShieldError):
        ops.remote("home")


def test_ambiguous_old_focus_is_refused(ops):
    activity(
        ops,
        "mFocusedActivity: com.amazon.tv.launcher/.Home\nmFocusedActivity: com.amazon.avod/.Playback",
    )
    with pytest.raises(ShieldError) as error:
        foreground_state(ops.t)
    assert error.value.kind == "foreground_unknown"


def test_active_media_with_unrecognized_state_blocks(ops):
    activity(ops, "mFocusedActivity: com.amazon.tv.launcher/.Home")
    ops.t.media = "package=com.amazon.avod\nactive=true\nstate=vendor-specific format\n"
    with pytest.raises(ShieldError) as error:
        ops.remote("home")
    assert error.value.kind == "playback_unknown"


def test_one_valid_foreground_entry_cannot_hide_unparseable_entry(ops):
    activity(
        ops,
        "mResumedActivity: com.amazon.tv.launcher/.Home\ntopResumedActivity: vendor-specific activity format",
    )
    with pytest.raises(ShieldError) as error:
        ops.remote("home")
    assert error.value.kind == "foreground_unknown"


@pytest.mark.parametrize("flag", ["yes", "", "true, flags=3"])
def test_unknown_media_active_flag_is_not_treated_as_inactive(ops, flag):
    activity(ops, "mResumedActivity: com.amazon.tv.launcher/.Home")
    ops.t.media = f"package=com.amazon.avod\nactive={flag}\nstate=PlaybackState {{state=3}}\n"
    with pytest.raises(ShieldError) as error:
        ops.remote("home")
    assert error.value.kind == "playback_unknown"


def process_dump(ops, sdk, dump):
    def shell(*args, **kwargs):
        ops.t.calls.append(("shell", args))
        if args[:2] == ("sh", "-c"):
            return "__NO_PIDOF__"
        if args == ("getprop", "ro.build.version.sdk"):
            return str(sdk)
        if args[0] == "ps":
            return dump
        raise AssertionError(args)

    ops.t.shell = shell


@pytest.mark.parametrize("sdk", [22, 23, 25, 33])
def test_missing_pidof_finds_kodi_and_ignores_similar_packages(ops, sdk):
    process_dump(
        ops,
        sdk,
        "USER PID PPID VSIZE RSS WCHAN PC NAME\n"
        "u0_a1 123 1 100 20 0 0 S org.xbmc.kodi\n"
        "u0_a1 124 1 100 20 0 0 S org.xbmc.kodi:service\n"
        "u0_a2 125 1 100 20 0 0 S org.xbmc.kodi.extra\n",
    )
    assert ops.kodi_pids() == {"123", "124"}
    assert ops.t.calls[-1][1] == (("ps",) if sdk <= 23 else ("ps", "-A", "-o", "PID,NAME"))
    with pytest.raises(ShieldError, match="running"):
        ops.stopped()


def test_missing_pidof_can_confirm_stopped(ops):
    process_dump(ops, 33, "PID NAME\n100 com.amazon.tv.launcher\n101 org.xbmc.kodi.extra\n")
    assert ops.kodi_pids() == set()


@pytest.mark.parametrize(
    "sdk,dump",
    [
        ("", "PID NAME\n"),
        (22, "permission denied"),
        (33, "PID NAME\n???\n"),
        (33, "PID CMD\n1 truncated-name\n"),
    ],
)
def test_missing_pidof_unknown_state_cannot_look_stopped(ops, sdk, dump):
    process_dump(ops, sdk, dump)
    with pytest.raises(ShieldError) as error:
        ops.stopped()
    assert error.value.kind == "process_unknown"


@pytest.mark.parametrize("failure", [False, True, "timeout", "unconfirmed"])
def test_pairing_secret_uses_stdin_and_never_output(monkeypatch, failure):
    commands, signals = [], []

    class Process:
        returncode = 1 if failure is True else 0

        def __init__(self, command, stdout, stderr, stdin):
            commands.append(command)
            assert stdin == subprocess.PIPE
            self.stdout, self.stderr = stdout, stderr

        def communicate(self, input, timeout):
            assert input == b"123456\n" and timeout == 60
            if failure == "timeout":
                raise subprocess.TimeoutExpired(commands[-1], timeout)
            self.stderr.write(b"failed with secret 123456")
            self.stdout.write(
                b"123456"
                if failure == "unconfirmed"
                else b"Successfully paired to 192.168.0.80:37001"
            )

        def kill(self):
            signals.append("killed")

        def wait(self):
            signals.append("reaped")

    monkeypatch.setattr(subprocess, "Popen", Process)
    transport = Transport(Config(host="192.168.0.80", adb_port=37123))
    try:
        if failure:
            with pytest.raises(ShieldError) as error:
                transport.pair(37001, "123456")
            assert "123456" not in str(error.value)
        else:
            assert transport.pair(37001, "123456") == {"paired": True, "connected": False}
        assert commands == [["adb", "pair", "192.168.0.80:37001"]]
        if failure == "timeout":
            assert signals == ["killed", "reaped"]
    finally:
        transport.close()


@pytest.mark.parametrize(
    "port,code", [(0, "123456"), (65536, "123456"), (37001, "123456;id"), (37001, "12345")]
)
def test_invalid_pairing_never_launches_adb(monkeypatch, port, code):
    def forbidden(*args, **kwargs):
        raise AssertionError("invalid input reached ADB")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    transport = Transport(Config(host="192.168.0.80"))
    try:
        with pytest.raises(ShieldError):
            transport.pair(port, code)
    finally:
        transport.close()


def test_pairing_cli_without_mcp_or_write_mode(monkeypatch, capsys, tmp_path):
    from nvidia_mcp import server

    config = Config(host="192.168.0.80", state=tmp_path / "unused")
    monkeypatch.setattr(server.Config, "from_env", lambda: config)
    monkeypatch.setattr("sys.argv", ["nvidia-mcp", "--pair-adb", "37001"])
    monkeypatch.setattr("sys.stdin", io.StringIO("123456\n"))

    def pair(self, port, code):
        assert self.c == config and port == 37001 and code == "123456"
        return {"paired": True, "connected": False}

    monkeypatch.setattr(Transport, "pair", pair)
    assert server.main() == 0
    assert "123456" not in capsys.readouterr().out
    assert not config.state.exists()


def test_pairing_targets_ipv6_host(monkeypatch):
    transport = Transport(replace(Config(host="fd00::80"), adb_port=37123))
    commands = []
    monkeypatch.setattr(
        transport,
        "adb",
        lambda *args, **kwargs: commands.append(args) or b"Successfully paired to [fd00::80]:37001",
    )
    try:
        transport.pair(37001, "123456")
        assert commands == [("pair", "[fd00::80]:37001")]
    finally:
        transport.close()
