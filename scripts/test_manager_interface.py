"""Exercise generated MCP wheel + Manager add-on ZIP together, using a synthetic HTTP backend.

Run with the project's dependency environment; no editable project imports, ADB or TV access.
"""

import argparse
import asyncio
import json
import sys
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--manager-zip", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.wheel.resolve()))
    import nvidia_mcp
    from nvidia_mcp.config import Config
    from nvidia_mcp.server import create_server

    assert str(args.wheel.resolve()) in nvidia_mcp.__file__, nvidia_mcp.__file__
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        with ZipFile(args.manager_zip) as archive:
            for name in archive.namelist():
                prefix = "service.kodi.addonadmin/resources/lib/"
                if name.startswith(prefix) and Path(name).suffix in (".py", ".sh"):
                    relative = Path(name[len(prefix) :])
                    assert not relative.is_absolute() and ".." not in relative.parts
                    (root / relative).parent.mkdir(parents=True, exist_ok=True)
                    (root / relative).write_bytes(archive.read(name))
        sys.path.insert(0, str(root))
        import server as manager
        from diagnostics import CAPABILITIES
        from operation_records import History

        assert Path(manager.__file__).parent == root
        state = SimpleNamespace(
            config={"host": "127.0.0.1", "auth_token": "synthetic-token", "write_enabled": True},
            operations=History(root / "manager-history"),
            log=lambda *args: None,
            web_root="",
            kodi=SimpleNamespace(jsonrpc=lambda *args: {"result": []}),
            writes=[],
        )

        class Handler(manager.make_handler(state)):
            def api_health(self):
                return {"diagnostics": CAPABILITIES}

            def api_stack_backup(self):
                self._require_idle("Playback active")
                state.writes.append("backup")
                return {"backup_id": "b" * 32}

            def api_stack_restore(self):
                self._require_idle("Playback active")
                state.writes.append("restore")
                return {"backup_id": "b" * 32, "undo_backup_id": "c" * 32}

            def api_diagnostics_support(self):
                # Production bundle collector; redirect cached metrics to this test directory.
                import api_status

                api_status.translate = lambda path: str(root / "metrics.json")
                return super().api_diagnostics_support()

        httpd = manager.BoundedThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(
            target=httpd.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
        )
        thread.start()
        mcp, ops = create_server(
            Config(
                host="127.0.0.1",
                manager_port=httpd.server_port,
                manager_token="synthetic-token",
                allow_writes=True,
                state=root / "mcp-history",
            )
        )
        ops.guard_tv = lambda *args, **kwargs: {"playback": "idle"}
        ops.t.adb = lambda *args, **kwargs: b"device"
        ops.t.rpc = lambda *args, **kwargs: {"name": "Kodi", "version": {"major": 22}}

        async def call(name, arguments):
            result = await mcp.call_tool(name, arguments)
            return result[1] if isinstance(result, tuple) else result.structured_content

        async def exercise():
            result = await call("kodi_configuration_backup", {})
            assert (
                result["operation"]["correlation_id"]
                == result["manager_operations"][0]["correlation_id"]
            )
            assert result["operation"]["backup_refs"] == ["b" * 32]
            result = await call("kodi_configuration_restore", {"backup_id": "b" * 32})
            assert result["operation"]["recovery_refs"] == ["c" * 32]
            state.config["write_enabled"] = False
            try:
                await call("kodi_configuration_backup", {})
            except Exception as exc:
                assert "write_disabled" in str(exc) and "Operation reference" in str(exc)
            else:
                raise AssertionError("Write gate was bypassed")
            bundle = await call("shield_support_bundle", {})
            assert bundle["manager"]["schema_version"] == 1
            assert bundle["failures"] and "synthetic-token" not in json.dumps(bundle)
            assert state.writes == ["backup", "restore"]

        try:
            asyncio.run(exercise())
        finally:
            ops.t.close()
            httpd.shutdown()
            httpd.server_close()
            thread.join(2)
    print(
        "Generated wheel/Manager ZIP interface: correlation, refusal, recovery and redacted bundle passed"
    )


if __name__ == "__main__":
    main()
