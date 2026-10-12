"""A long APK preview must not freeze the server for other tool calls (mcp 1.x and 2.x).

mcp 1.x runs plain ``def`` tools on the event loop. If such a tool waits for the operations
lock while an APK worker thread holds it and reports progress (which needs the event loop),
both wait for each other forever. The scenario runs in a subprocess so a regression fails
with a timeout instead of hanging the test session.
"""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

SCRIPT = textwrap.dedent(
    """
    import hashlib, sys, tempfile, threading, time
    from pathlib import Path

    import anyio

    from nvidia_mcp import apks, server
    from nvidia_mcp.config import Config

    tmp = Path(sys.argv[1])
    apk = tmp / "a.apk"
    apk.write_bytes(b"PK synthetic")
    sha = hashlib.sha256(apk.read_bytes()).hexdigest()
    signer = "a" * 64
    locked = threading.Event()

    def inspect_set(paths, config):
        locked.set()  # The preview now holds the operations lock.
        time.sleep(0.5)  # Another tool call arrives while it is held.
        item = {"package": "com.example.app", "version_code": 2, "version_name": "2",
                "split": "", "min_sdk": 21, "abis": [], "signers": [signer],
                "sha256": sha, "bytes": apk.stat().st_size}
        return item, [dict(item) for _ in paths]

    apks.inspect_set = inspect_set

    class Transport:
        def __init__(self, config):
            self.c = config
        def shell(self, *args, **kwargs):
            if args[:2] == ("getprop", "ro.serialno"):
                return "synthetic_tv_001"
            if args[:2] == ("getprop", "ro.product.cpu.abilist"):
                return "arm64-v8a"
            if args[:2] == ("getprop", "ro.build.version.sdk"):
                return "30"
            return ""
        def rpc(self, *args, **kwargs):
            return []
        def close(self):
            pass

    (tmp / "kodi").mkdir()
    config = Config(host="127.0.0.1", state=tmp / "state", mount=tmp / "kodi",
                    allow_writes=True, trusted_signers=frozenset({signer}))
    mcp, ops = server.create_server(config)
    fake = Transport(config)
    ops.t = ops.apks.t = ops.files.t = fake
    done = []

    async def main():
        async def preview():
            await mcp.call_tool("shield_apk_preview", {"apk_paths": [str(apk)]})
            done.append("preview")

        async def other(name, arguments):
            await anyio.to_thread.run_sync(locked.wait)
            try:
                await mcp.call_tool(name, arguments)
            except Exception:
                pass  # Refusals are fine; only finishing matters.
            done.append(name)

        async with anyio.create_task_group() as group:
            group.start_soon(preview)
            group.start_soon(other, "kodi_patch_preview", {
                "path": "userdata/x.xml", "expected_sha256": "0" * 64,
                "edits": [{"before": "a", "after": "b"}]})
            group.start_soon(other, "shield_remote", {"button": "up"})

    anyio.run(main)
    print("FINISHED", sorted(done))
    """
)


def test_tool_waiting_for_the_lock_does_not_deadlock_apk_progress(tmp_path):
    script = tmp_path / "scenario.py"
    script.write_text(SCRIPT)
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
    try:
        result = subprocess.run(
            [sys.executable, str(script), str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
    except subprocess.TimeoutExpired:
        raise AssertionError(
            "Server deadlocked: a tool blocked the event loop on ops.lock"
        ) from None
    assert result.returncode == 0, result.stderr[-2000:]
    assert "FINISHED ['kodi_patch_preview', 'preview', 'shield_remote']" in result.stdout
