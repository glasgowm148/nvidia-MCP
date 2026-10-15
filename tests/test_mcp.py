import asyncio
import json
import re
import sys
import threading
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.metadata import version
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def field(obj, name):
    """Read a result field under its mcp 1.x camelCase or mcp 2.x snake_case name."""
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
    return getattr(obj, name) if hasattr(obj, name) else getattr(obj, snake)


def test_real_stdio_protocol(tmp_path):
    class Kodi(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            method = body["method"]
            values = {
                "Application.GetProperties": {"name": "Kodi", "version": {"major": 22}},
                "GUI.GetProperties": {"skin": {"id": "skin.estuary"}},
                "Profiles.GetCurrentProfile": {"label": "Adults"},
                "Player.GetActivePlayers": [],
                "Settings.GetSettingValue": {"value": "not-secret"},
            }
            data = json.dumps({"jsonrpc": "2.0", "id": 1, "result": values[method]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    http = ThreadingHTTPServer(("127.0.0.1", 0), Kodi)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()

    async def exercise():
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "nvidia_mcp.server"],
            env={
                "SHIELD_HOST": "127.0.0.1",
                "KODI_PORT": str(http.server_port),
                "KODI_MANAGER_TOKEN": "",
                "NVIDIA_MCP_ALLOW_WRITES": "0",
                "NVIDIA_MCP_STATE_DIR": str(tmp_path / "private"),
                # Test this checkout even when another copy is installed in the environment.
                "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
            },
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(
                read,
                write,
                read_timeout_seconds=(
                    timedelta(seconds=45) if version("mcp").startswith("1.") else 45
                ),
            ) as client:
                await client.initialize()
                tools = (await client.list_tools()).tools
                names = {t.name for t in tools}
                # Write tools are not registered at all without NVIDIA_MCP_ALLOW_WRITES=1.
                assert len(tools) == 10
                assert not names & {"shield_apk_apply", "shield_remote", "kodi_patch_file"}
                assert {"kodi_get_status", "kodi_list_settings"} <= names
                assert not names & {
                    "kodi_preview_file_patch",
                    "kodi_inspect_manager",
                    "kodi_status",
                }
                assert field(
                    next(t for t in tools if t.name == "kodi_get_status").annotations,
                    "readOnlyHint",
                )
                assert all(field(t.annotations, "title") for t in tools)
                canonical = await client.call_tool("kodi_get_status", {})
                assert not field(canonical, "isError")
                status = await client.call_tool("kodi_status", {})
                assert not field(status, "isError") and "Kodi" in str(status.content)
                assert field(status, "structuredContent")["application"]["name"] == "Kodi"
                bad = await client.call_tool("kodi_read", {"method": "System.Shutdown"})
                assert field(bad, "isError")
                for name in (
                    "kodi_set_setting",
                    "kodi_patch_apply",
                    "kodi_apply_file_patch",
                    "kodi_patch_file",
                ):
                    denied = await client.call_tool(name, {})
                    assert field(denied, "isError")
                traversal = await client.call_tool("kodi_read_file", {"path": "../.env"})
                assert field(traversal, "isError") and "traversal" in str(traversal.content)
                resource = await client.read_resource("nvidia://playbook")
                assert "independent OAuth grant" in str(resource.contents)
                prompts = await client.list_prompts()
                assert prompts.prompts[0].name == "audit_kodi"

    try:
        asyncio.run(exercise())
    finally:
        http.shutdown()
        http.server_close()
        thread.join()
