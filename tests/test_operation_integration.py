"""Local MCP/Manager interface, with the existing synthetic transport and sibling service."""

import asyncio
import importlib
import json
import sys
import threading
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from conftest import manager_checkout

from nvidia_mcp.config import Config, ShieldError
from nvidia_mcp.diagnostics import support_bundle
from nvidia_mcp.operation_records import CONTEXT, clean, record
from nvidia_mcp.server import create_server
from nvidia_mcp.transport import Transport


def test_vendored_contract_matches_optional_manager_checkout():
    root = Path(__file__).resolve().parents[1]
    source = manager_checkout() / "src/kodi_manager/operation_records.py"
    assert source.read_bytes() == (root / "src/nvidia_mcp/operation_records.py").read_bytes()


@pytest.mark.parametrize(
    "error, expected",
    [
        (httpx.ConnectError("unreachable"), "unreachable"),
        (httpx.ConnectTimeout("not connected"), "timeout"),
        (httpx.ReadTimeout("sent"), "outcome_unknown"),
        (
            httpx.RemoteProtocolError("Server disconnected without sending a response."),
            "outcome_unknown",
        ),
    ],
)
def test_transport_never_repeats_a_manager_write(tmp_path, error, expected):
    transport = Transport(Config(host="127.0.0.1", state=tmp_path, manager_token="synthetic"))
    calls = []

    def reply(request):
        calls.append(request)
        raise error

    transport.http.close()
    transport.http = httpx.Client(transport=httpx.MockTransport(reply))
    try:
        with pytest.raises(ShieldError) as caught:
            transport.manager("/api/stack/backup", "POST", {})
        assert caught.value.kind == expected and len(calls) == 1
    finally:
        transport.close()


def test_read_only_manager_post_timeout_is_not_an_unknown_write(tmp_path):
    transport = Transport(Config(host="127.0.0.1", state=tmp_path, manager_token="synthetic"))

    def reply(request):
        raise httpx.ReadTimeout("sent")

    transport.http.close()
    transport.http = httpx.Client(transport=httpx.MockTransport(reply))
    try:
        with pytest.raises(ShieldError) as caught:
            transport.manager("/api/widgets/layout/preview", "POST", {})
        assert caught.value.kind != "outcome_unknown"
    finally:
        transport.close()


def test_read_only_posts_match_optional_manager_checkout():
    from nvidia_mcp.transport import MANAGER_READ_POSTS

    source = manager_checkout() / "src/kodi_manager/server.py"
    import re

    reads = set(re.findall(r'\("POST", r"(/api/[^"]+)", "\w+", False,', source.read_text()))
    assert reads == MANAGER_READ_POSTS


@pytest.mark.parametrize(
    "response", [httpx.Response(200, text="not json"), httpx.Response(200, json={"ok": True})]
)
def test_invalid_write_response_is_ambiguous(tmp_path, response):
    transport = Transport(Config(host="127.0.0.1", state=tmp_path, manager_token="synthetic"))
    transport.http.close()
    transport.http = httpx.Client(transport=httpx.MockTransport(lambda request: response))
    try:
        with pytest.raises(ShieldError) as caught:
            transport.manager("/api/stack/backup", "POST", {})
        assert caught.value.kind == "outcome_unknown"
    finally:
        transport.close()


def test_bundle_negotiates_old_manager_and_projects_private_metadata(ops):
    ops.c = replace(ops.c, manager_token="synthetic-token")
    ops.t.c = ops.c
    ops.t.adb = lambda *args: b"device"
    calls = []

    def old(path, *args):
        calls.append(path)
        return {"token": "synthetic-token", "personal_title": "Private viewing"}

    ops.t.manager = old
    bundle = support_bundle(ops)
    assert bundle["manager"]["reason_code"] == "unsupported"
    assert "/api/diagnostics/support" not in calls
    row = record(
        "stack_restore",
        "a" * 32,
        time.monotonic(),
        "server_retired",
        "unknown",
        {"undo_backup_id": "b" * 32},
    )

    def modern(path, *args):
        if path == "/api/health":
            return {"diagnostics": {"support_bundle_version": 1}}
        return {
            "schema_version": 1,
            "operations": [dict(row, password="synthetic-token")],
            "versions": {"manager": "0.7.34", "private_path": "/private/profile"},
            "metrics": {"mk": 700, "personal_title": "Private viewing"},
            "raw_log": "synthetic-token",
        }

    ops.t.manager = modern
    bundle = support_bundle(ops)
    assert bundle["manager"]["metrics"]["mk"] == 700
    assert bundle["manager"]["operations"][0]["recovery_refs"] == ["b" * 32]
    assert "Do not repeat" in bundle["failures"][0]["next_step"]
    assert all(
        value not in json.dumps(bundle)
        for value in ("synthetic-token", "Private viewing", "/private/profile", "raw_log")
    )


def manager_module():
    path = manager_checkout() / "src"
    sys.path.insert(0, str(path))
    return importlib.import_module("kodi_manager.server")


def test_real_mcp_tools_correlate_manager_success_refusal_and_recovery(tmp_path):
    manager = manager_module()
    from kodi_manager.operation_records import History

    writes = []
    state = SimpleNamespace(
        config={"host": "127.0.0.1", "auth_token": "synthetic-token", "write_enabled": True},
        logs=[],
        log=lambda *args: None,
        web_root="",
        operations=History(tmp_path / "manager"),
        kodi=SimpleNamespace(jsonrpc=lambda *args: {"result": []}),
        delay=0,
    )

    class Handler(manager.make_handler(state)):
        def api_stack_backup(self):
            self._require_idle("Playback active")
            writes.append("backup")
            if state.delay:
                time.sleep(state.delay)
            return {"backup_id": "b" * 32}

        def api_stack_restore(self):
            self._require_idle("Playback active")
            writes.append("restore")
            return {"backup_id": "b" * 32, "undo_backup_id": "c" * 32}

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
            state=tmp_path / "mcp",
            allow_writes=True,
        )
    )
    ops.guard_tv = lambda *args, **kwargs: {"playback": "idle"}

    async def exercise():
        result = await mcp.call_tool("kodi_configuration_backup", {})
        # FastMCP returns a content/structured pair in 1.x; 2.x returns CallToolResult.
        data = result[1] if isinstance(result, tuple) else result.structured_content
        assert data["operation"]["backup_refs"] == ["b" * 32]
        remote = data["manager_operations"][0]
        assert remote["correlation_id"] == data["operation"]["correlation_id"]
        result = await mcp.call_tool("kodi_configuration_restore", {"backup_id": "b" * 32})
        data = result[1] if isinstance(result, tuple) else result.structured_content
        assert data["operation"]["recovery_refs"] == ["c" * 32]
        state.config["write_enabled"] = False
        with pytest.raises(Exception) as caught:
            await mcp.call_tool("kodi_configuration_backup", {})
        assert "write_disabled" in str(caught.value) and "Operation reference" in str(caught.value)
        local, remote = ops.history.selected()[0], state.operations.selected()[0]
        assert local["reason_code"] == remote["reason_code"] == "write_disabled"
        assert local["correlation_id"] == remote["correlation_id"]
        assert local["decision"] == remote["decision"] == "refuse"
        state.config["write_enabled"] = True
        state.delay, ops.t.response_deadline = 0.12, 0.03
        with pytest.raises(Exception) as caught:
            await mcp.call_tool("kodi_configuration_backup", {})
        assert "outcome_unknown" in str(caught.value) or "response_timeout" in str(caught.value)
        await asyncio.sleep(0.16)

    try:
        asyncio.run(exercise())
        assert writes == ["backup", "restore", "backup"]
        local, remote = ops.history.selected()[0], state.operations.selected()[0]
        assert local["outcome"] == "unknown" and remote["outcome"] == "succeeded"
        assert local["correlation_id"] == remote["correlation_id"]
    finally:
        ops.t.close()
        httpd.shutdown()
        httpd.server_close()
        thread.join(2)


def test_completed_tool_keeps_success_when_history_fails(tmp_path, monkeypatch):
    mcp, ops = create_server(Config(host="127.0.0.1", state=tmp_path))
    ops.kodi_status = lambda: {"ready": True}
    monkeypatch.setattr(
        ops.history, "append", lambda row: (_ for _ in ()).throw(OSError("disk full"))
    )
    try:
        result = asyncio.run(mcp.call_tool("kodi_status", {}))
        data = result[1] if isinstance(result, tuple) else result.structured_content
        assert data["ready"] and data["operation"]["outcome"] == "succeeded"
        assert (
            data["history_recorded"] is False
            and data["diagnostic_warning"] == "history_unavailable"
        )
    finally:
        ops.t.close()


def test_context_does_not_leak_between_calls(ops):
    context = {"id": "a" * 32, "backup_refs": []}
    token = CONTEXT.set(context)
    try:
        ops.audit("set_core_setting", "personal value", "b" * 32)
        assert context["backup_refs"] == ["b" * 32]
        assert ops.history.selected() == []
    finally:
        CONTEXT.reset(token)
    ops.audit("set_core_setting", "personal value", "c" * 32)
    assert ops.history.selected()[0]["backup_refs"] == ["c" * 32]
    assert clean(ops.history.selected()[0]) is not None


@pytest.mark.parametrize(
    "name,method,arguments,outcome",
    [
        # A local snapshot only reads the TV: a late reply cannot leave a change behind.
        ("kodi_create_file_backup", "backup_file", {"path": "userdata/x.xml"}, "failed"),
        (
            "kodi_set_setting",
            "set_core_setting",
            {"setting": "videolibrary.showunwatched", "value": True},
            "unknown",
        ),
    ],
)
def test_response_timeout_is_unknown_only_for_tools_that_write_the_tv(
    tmp_path, name, method, arguments, outcome
):
    mcp, ops = create_server(Config(host="127.0.0.1", state=tmp_path, allow_writes=True))

    def stalled(*args, **kwargs):
        raise ShieldError("Device HTTP response deadline exceeded", "response_timeout")

    setattr(ops, method, stalled)
    try:
        with pytest.raises(Exception, match="response_timeout"):
            asyncio.run(mcp.call_tool(name, arguments))
        assert ops.history.selected()[0]["outcome"] == outcome
    finally:
        ops.t.close()
