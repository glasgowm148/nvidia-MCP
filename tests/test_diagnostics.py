import sys
from dataclasses import replace

import httpx
import pytest

from nvidia_mcp.config import Config, ShieldError
from nvidia_mcp.diagnostics import health, readiness
from nvidia_mcp.transport import Transport, adb_error


def test_independent_readiness_does_not_confuse_adb_with_kodi(ops):
    def adb(*args):
        raise adb_error(b"error: device unauthorized private-serial")

    def rpc(*args):
        return {"name": "Kodi", "version": {"major": 22}}

    ops.t.adb, ops.t.rpc = adb, rpc
    status = readiness(ops)
    assert status["adb"]["state"] == "authorization_required"
    assert status["kodi_http"]["state"] == "ready"
    assert status["manager"]["state"] == "not_configured"
    assert "private-serial" not in str(status)


@pytest.mark.parametrize(
    "text,kind",
    [
        (b"device offline", "offline"),
        (b"failed to connect private-ip", "unreachable"),
        (b"permission denied private-path", "permission_denied"),
    ],
)
def test_adb_errors_are_actionable_and_do_not_expose_stderr(text, kind):
    error = adb_error(text)
    assert error.kind == kind and "private-" not in str(error)


def test_http_failure_classification():
    t = Transport(Config(host="127.0.0.1"))
    t.http.close()
    t.http = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(401, text="private-token"))
    )
    with pytest.raises(ShieldError) as exc:
        t.rpc("Application.GetProperties")
    assert exc.value.kind == "authentication_denied"
    assert "private-token" not in str(exc.value)
    t.close()


def test_health_excludes_historical_thermal_readings_and_unknown_is_not_zero():
    # Historical temperatures can be stale; only feed the current HAL section to the parser.
    parsed = health(
        "MemTotal: 1000 kB\nMemAvailable: 250 kB",
        "Filesystem 1K-blocks Used Available Use% Mounted on\n/dev/data 1000 300 700 30% /data",
        "12.5 10",
        "Thermal Status: 2\nTemperature{mValue=67.0, mType=0, mName=CPU, mStatus=2}",
    )
    assert parsed["thermal_status"] == 2
    assert parsed["temperatures"][0]["celsius"] == 67
    assert parsed["storage"][0]["available_kb"] == 700
    assert health("", "", "", "")["thermal_status"] is None


def test_unknown_foreground_blocks_lifecycle_even_with_offline_permission(ops):
    ops.c = replace(ops.c, allow_interrupt=True)
    original = ops.t.shell
    ops.t.shell = lambda *args, **kwargs: (
        "" if args == ("dumpsys", "activity", "activities") else original(*args, **kwargs)
    )
    with pytest.raises(ShieldError, match="Foreground TV app is unknown"):
        ops.lifecycle("restart", True, True)
    assert not any(
        call[0] == "shell" and call[1][:2] == ("am", "force-stop") for call in ops.t.calls
    )


def test_stream_download_is_bounded_and_removes_partial_file(tmp_path):
    t = Transport(Config(host="127.0.0.1"))
    target = tmp_path / "private.bin"
    with pytest.raises(ShieldError, match="byte limit"):
        t.stream_to_file(
            [sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'x' * 10000)"],
            target,
            100,
            10,
        )
    assert not target.exists()
    assert t.stream_to_file([sys.executable, "-c", "print('ok')"], target, 100, 10) > 0
    existing = target.read_bytes()
    with pytest.raises(ShieldError):
        t.stream_to_file([sys.executable, "-c", "print('overwrite')"], target, 100, 10)
    assert target.read_bytes() == existing
    target.unlink()
    with pytest.raises(ShieldError, match="timed out"):
        t.stream_to_file([sys.executable, "-c", "import time; time.sleep(10)"], target, 100, 0.1)
    assert not target.exists()
    t.close()
