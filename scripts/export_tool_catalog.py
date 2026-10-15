"""Export synthetic MCP tool definitions for offline review; never contact a TV."""

import argparse
import asyncio
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nvidia_mcp.config import Config  # noqa: E402
from nvidia_mcp.server import create_server  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("standard", "full"), default="standard")
    parser.add_argument("--writes", action="store_true")
    parser.add_argument("--manager", action="store_true")
    parser.add_argument("--plugin-browse", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as state:
        server, ops = create_server(
            Config(
                host="127.0.0.1",
                state=Path(state),
                tool_profile=args.profile,
                allow_writes=args.writes,
                allow_plugin_browse=args.plugin_browse,
                manager_token="synthetic-not-a-device-token" if args.manager else "",
            )
        )
        try:
            tools = asyncio.run(server.list_tools())
            payload = {
                "serverName": "nvidia-MCP",
                "tools": [tool.model_dump(by_alias=True, exclude_none=True) for tool in tools],
            }
            args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            print(f"Exported {len(tools)} synthetic {args.profile} tool definitions")
        finally:
            ops.t.close()


if __name__ == "__main__":
    main()
