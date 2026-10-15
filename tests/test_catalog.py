"""Discovery is bounded and capability-aware; legacy names retain validation and guards."""

import ast
import asyncio
import json
import re
from pathlib import Path

import pytest

from nvidia_mcp.catalog import TOOL_NAMES
from nvidia_mcp.config import Config
from nvidia_mcp.server import create_server


def names(server):
    return {tool.name for tool in asyncio.run(server.list_tools())}


@pytest.mark.parametrize("writes,expected", [(False, 10), (True, 17)])
def test_standard_discovery_does_not_contact_device(tmp_path, monkeypatch, writes, expected):
    server, ops = create_server(Config(host="127.0.0.1", state=tmp_path, allow_writes=writes))

    def forbidden(*args, **kwargs):
        pytest.fail("Introspection must not connect to a device")

    for method in ("rpc", "adb", "shell", "manager"):
        monkeypatch.setattr(ops.t, method, forbidden)
    try:
        listed = names(server)
        assert len(listed) == expected
        assert "kodi_get_status" in listed and "kodi_status" not in listed
        assert "kodi_preview_file_patch" not in listed
        assert "shield_capture_screenshot" not in listed
        assert "kodi_inspect_manager" not in listed
        assert "kodi_browse_directory" not in listed
    finally:
        ops.t.close()


@pytest.mark.parametrize("writes", [False, True])
def test_standard_writes_list_their_undo_path(tmp_path, writes):
    server, ops = create_server(Config(host="127.0.0.1", state=tmp_path, allow_writes=writes))
    undo = {"kodi_list_file_backups", "kodi_read_file", "kodi_restore_file"}
    try:
        listed = names(server)
        assert ("kodi_set_setting" in listed) is writes
        assert (undo <= listed) is writes
        assert not undo & listed or writes
    finally:
        ops.t.close()


def test_apple_tv_standard_writes_do_not_list_android_only_restore(tmp_path):
    server, ops = create_server(
        Config(host="127.0.0.1", state=tmp_path, platform="apple_tv", allow_writes=True)
    )
    try:
        listed = names(server)
        assert "kodi_set_setting" in listed and "kodi_restore_file" not in listed
    finally:
        ops.t.close()


@pytest.mark.parametrize("profile", ["standard", "full"])
def test_optional_capabilities_and_hidden_legacy_patch(tmp_path, profile):
    server, ops = create_server(
        Config(
            host="127.0.0.1",
            state=tmp_path,
            tool_profile=profile,
            manager_token="synthetic",
            allow_plugin_browse=True,
            allow_writes=True,
        )
    )
    try:
        listed = names(server)
        assert {
            "kodi_inspect_manager",
            "kodi_preview_layout",
            "kodi_apply_layout",
            "kodi_browse_directory",
            "kodi_restore_configuration",
        } <= listed
        assert "kodi_patch_file" not in listed
        assert ("kodi_apply_file_patch" in listed) is (profile == "full")
    finally:
        ops.t.close()


def test_legacy_and_canonical_calls_share_validation_and_dispatch(tmp_path, monkeypatch):
    server, ops = create_server(Config(host="127.0.0.1", state=tmp_path))
    calls = []
    monkeypatch.setattr(ops, "kodi_status", lambda: calls.append("status") or {"fixture": True})
    try:
        for name in ("kodi_get_status", "kodi_status"):
            assert "fixture" in str(asyncio.run(server.call_tool(name, {})))
        assert calls == ["status", "status"]
        for name in ("kodi_query_rpc", "kodi_read"):
            with pytest.raises(Exception, match="System.Shutdown"):
                asyncio.run(server.call_tool(name, {"method": "System.Shutdown"}))
        for name in ("kodi_apply_file_patch", "kodi_patch_apply", "kodi_patch_file"):
            with pytest.raises(Exception, match="Unknown tool"):
                asyncio.run(server.call_tool(name, {}))
    finally:
        ops.t.close()


def test_unlisted_advanced_calls_keep_working_and_deprecated_patch_is_write_gated(
    tmp_path, monkeypatch
):
    server, ops = create_server(Config(host="127.0.0.1", state=tmp_path, allow_writes=True))
    monkeypatch.setattr(ops, "read_file", lambda path: {"path": path})
    monkeypatch.setattr(ops, "patch_file", lambda *args: {"dry_run": args[-1]})
    try:
        listed = names(server)
        assert "kodi_patch_file" not in listed and "kodi_preview_file_patch" not in listed
        assert "userdata/example.xml" in str(
            asyncio.run(server.call_tool("kodi_read_file", {"path": "userdata/example.xml"}))
        )
        assert "dry_run" in str(
            asyncio.run(
                server.call_tool(
                    "kodi_patch_file",
                    {
                        "path": "userdata/example.xml",
                        "expected_sha256": "a" * 64,
                        "edits": [{"before": "old", "after": "new"}],
                    },
                )
            )
        )
    finally:
        ops.t.close()


def test_full_tool_parameters_explain_their_semantics(tmp_path):
    server, ops = create_server(
        Config(
            host="127.0.0.1",
            state=tmp_path,
            tool_profile="full",
            allow_writes=True,
            allow_plugin_browse=True,
        )
    )
    try:
        tools = asyncio.run(server.list_tools())
        for tool in tools:
            schema = json.loads(tool.model_dump_json(by_alias=True))["inputSchema"]
            assert all(p.get("description") for p in schema.get("properties", {}).values()), (
                tool.name
            )
    finally:
        ops.t.close()


@pytest.mark.parametrize(
    "value,expected",
    [("", "standard"), ("Full", "full"), (" full ", "full"), ("STANDARD", "standard")],
)
def test_profile_is_normalised(monkeypatch, value, expected):
    monkeypatch.setenv("SHIELD_HOST", "192.168.1.50")
    monkeypatch.setenv("NVIDIA_MCP_TOOL_PROFILE", value)
    assert Config.from_env().tool_profile == expected


def test_unknown_profile_falls_back_to_standard_with_a_warning(monkeypatch, capsys):
    monkeypatch.setenv("SHIELD_HOST", "192.168.1.50")
    monkeypatch.setenv("NVIDIA_MCP_TOOL_PROFILE", "ful")
    assert Config.from_env().tool_profile == "standard"
    assert "standard or full" in capsys.readouterr().err


def test_messages_name_advertised_tools():
    """User-facing text names the canonical tools, not their legacy aliases."""
    legacy = {old for old, new in TOOL_NAMES.items() if old != new}
    pattern = re.compile(r"\b(" + "|".join(sorted(legacy, key=len, reverse=True)) + r")\b")
    root = Path(__file__).resolve().parents[1] / "src/nvidia_mcp"
    found = []
    for path in sorted(root.glob("*.py")):
        if path.name in ("catalog.py", "operation_records.py", "route_guard.py"):
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                # Sentences only: bare identifiers are registration keys, not messages.
                if " " in node.value.strip() and pattern.search(node.value):
                    found.append(f"{path.name}:{node.lineno}: {pattern.search(node.value)[0]}")
    assert not found, found
