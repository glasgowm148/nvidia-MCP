import asyncio
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


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
            },
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as client:
                await client.initialize()
                tools = (await client.list_tools()).tools
                assert len(tools) == 29
                assert next(t for t in tools if t.name == "kodi_status").annotations.readOnlyHint
                assert not next(
                    t for t in tools if t.name == "kodi_patch_file"
                ).annotations.readOnlyHint
                assert not next(
                    t for t in tools if t.name == "shield_apk_apply"
                ).annotations.readOnlyHint
                apk = await client.call_tool("shield_apk_apply", {"preview_id": "synthetic"})
                assert apk.isError and "disabled" in str(apk.content)
                status = await client.call_tool("kodi_status", {})
                assert not status.isError and "Kodi" in str(status.content)
                assert status.structuredContent["application"]["name"] == "Kodi"
                bad = await client.call_tool("kodi_read", {"method": "System.Shutdown"})
                assert bad.isError and "allowlist" in str(bad.content)
                write = await client.call_tool("shield_remote", {"button": "home"})
                assert write.isError and "disabled" in str(write.content)
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
