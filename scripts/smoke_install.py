"""Exercise an installed wheel through real MCP stdio and synthetic local Kodi HTTP."""

import asyncio
import json
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from nvidia_mcp import __version__
from nvidia_mcp.companion import export_manager


def main():
    class Kodi(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            values = {
                "Application.GetProperties": {"name": "Kodi", "version": {"major": 22}},
                "GUI.GetProperties": {"skin": {"id": "skin.estuary"}},
                "Profiles.GetCurrentProfile": {"label": "Synthetic"},
                "Player.GetActivePlayers": [],
            }
            data = json.dumps(
                {"jsonrpc": "2.0", "id": 1, "result": values[request["method"]]}
            ).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    http = ThreadingHTTPServer(("127.0.0.1", 0), Kodi)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory() as directory:
            exported = export_manager(Path(directory) / "export")
            assert not exported["installed_on_device"]

            def field(result, snake, camel):
                # mcp 1.x uses camelCase result fields; mcp 2.x uses snake_case.
                value = getattr(result, snake, None)
                return getattr(result, camel, None) if value is None else value

            async def exercise():
                parameters = StdioServerParameters(
                    command=sys.executable,
                    args=["-I", "-m", "nvidia_mcp.server"],
                    env={
                        "SHIELD_HOST": "127.0.0.1",
                        "KODI_PORT": str(http.server_port),
                        "KODI_USERNAME": "synthetic",
                        "KODI_PASSWORD": "synthetic-password",
                        "KODI_MANAGER_TOKEN": "",
                        "NVIDIA_MCP_ALLOW_WRITES": "0",
                        "NVIDIA_MCP_ALLOW_PLUGIN_BROWSE": "0",
                        "NVIDIA_MCP_STATE_DIR": str(Path(directory) / "state"),
                        "ADB_PATH": str(Path(directory) / "no-adb"),
                    },
                )
                async with stdio_client(parameters) as (read, write):
                    async with ClientSession(read, write) as client:
                        await client.initialize()
                        names = {t.name for t in (await client.list_tools()).tools}
                        assert {"shield_connection", "shield_apk_apply", "kodi_status"} <= names
                        result = await client.call_tool("kodi_status", {})
                        assert not field(result, "is_error", "isError")
                        assert (
                            field(result, "structured_content", "structuredContent")["application"][
                                "name"
                            ]
                            == "Kodi"
                        )
                        for name, args in (
                            ("shield_remote", {"button": "home"}),
                            ("shield_apk_apply", {"preview_id": "synthetic"}),
                            ("kodi_read", {"method": "System.Shutdown"}),
                        ):
                            assert field(await client.call_tool(name, args), "is_error", "isError")
                        assert (await client.read_resource("nvidia://playbook")).contents
                        assert (await client.list_prompts()).prompts
                print(
                    "Installed nvidia-MCP %s: stdio, %d tools, refusal gates and companion export passed"
                    % (__version__, len(names))
                )

            asyncio.run(exercise())
    finally:
        http.shutdown()
        http.server_close()
        thread.join()


if __name__ == "__main__":
    main()
