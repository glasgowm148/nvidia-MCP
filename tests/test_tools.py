"""M3/M4/M5/M7: tool registration, schemas, patch split, widget cache, APK status, retention."""

import asyncio
import json
import os
import time
from dataclasses import replace

import pytest

from nvidia_mcp import privacy
from nvidia_mcp.config import Config, ShieldError
from nvidia_mcp.files import digest
from nvidia_mcp.retention import prune_state
from nvidia_mcp.server import create_server, progress_callback

WRITE_TOOLS = {
    "shield_apk_apply",
    "shield_remote",
    "kodi_lifecycle",
    "kodi_patch_apply",
    "kodi_patch_file",
    "kodi_restore_file",
    "kodi_set_addon_setting",
    "kodi_set_setting",
    "kodi_layout_apply",
    "kodi_layout_rebuild",
    "kodi_manager_widget_cache_refresh",
}


def tools(tmp_path, **kwargs):
    mcp, ops = create_server(Config(host="127.0.0.1", state=tmp_path / "state", **kwargs))
    listed = asyncio.run(mcp.list_tools())
    ops.t.close()
    return {t.name: t.model_dump(by_alias=True) for t in getattr(listed, "tools", listed)}


def test_write_tools_registered_only_with_writes(tmp_path):
    read_only = tools(tmp_path)
    full = tools(tmp_path, allow_writes=True)
    assert not set(read_only) & WRITE_TOOLS
    assert set(full) - set(read_only) == WRITE_TOOLS
    for tool in full.values():
        hints = tool["annotations"]
        assert hints["title"] and tool["title"] == hints["title"]
        assert hints["idempotentHint"] is not None
        if tool["name"] in WRITE_TOOLS:
            assert hints["readOnlyHint"] is False
    preview = full["shield_apk_preview"]["annotations"]
    assert preview["readOnlyHint"] is False and preview["destructiveHint"] is False


def test_typed_schemas(tmp_path):
    full = tools(tmp_path, allow_writes=True)
    method = full["kodi_read"]["inputSchema"]["properties"]["method"]
    assert "Settings.GetSettingValue" in method["enum"] and "System.Shutdown" not in method["enum"]
    for name in ("kodi_patch_preview", "kodi_patch_apply", "kodi_patch_file"):
        schema = full[name]["inputSchema"]
        assert schema["$defs"]["PatchEdit"]["required"] == ["before", "after"]
    plan = full["kodi_layout_preview"]["inputSchema"]["$defs"]["LayoutPlan"]
    assert {"section_id", "expected_revision", "rows"} <= set(plan["required"])
    assert plan["properties"]["rows"]["maxItems"] == 20
    assert "ctx" not in full["shield_apk_apply"]["inputSchema"]["properties"]


def test_patch_preview_returns_redacted_diff(ops):
    path = "userdata/advancedsettings.xml"
    (ops.c.mount / path).write_text(
        "<advancedsettings>\n  <videodatabase>\n    <host>192.168.1.20</host>\n"
        "    <pass>hunter22secret</pass>\n  </videodatabase>\n</advancedsettings>\n"
    )
    sha = digest(ops.files.read(path))
    edits = [{"before": "<host>192.168.1.20</host>", "after": "<host>192.168.1.21</host>"}]
    result = ops.patch_preview(path, sha, edits)
    assert "-    <host>192.168.1.20</host>" in result["diff"]
    assert "+    <host>192.168.1.21</host>" in result["diff"]
    assert "hunter22secret" not in json.dumps(result)
    assert ops.files.read(path).count(b"192.168.1.20") == 1  # preview never writes
    assert ops.patch_file(path, sha, edits)["diff"] == result["diff"]  # deprecated alias
    applied = ops.patch_apply(path, sha, edits)
    assert b"192.168.1.21" in ops.files.read(path) and applied["backup_id"]


@pytest.mark.parametrize(
    "content,edit",
    [
        (
            "<a>\n  <pass>hunter22secret</pass>\n</a>\n",
            {"before": "hunter22secret", "after": "changed-pass"},
        ),
        (
            '<settings>\n<setting id="rd.auth">abc</setting>\n</settings>\n',
            {"before": ">abc<", "after": ">xyz<"},
        ),
        (
            '<settings>\n<setting id="trakt.refresh"\n value="old" />\n</settings>\n',
            {"before": '"old"', "after": '"new"'},
        ),
        ('{"trakt": {"access_token": "abc"}}', {"before": '"abc"', "after": '"xyz"'}),
        ("token = 'abc'\n", {"before": "abc", "after": "xyz"}),
    ],
)
def test_patch_refuses_secret_edits(ops, content, edit):
    suffix = ".json" if content.startswith("{") else ".py" if "token =" in content else ".xml"
    path = "userdata/secrets" + suffix
    (ops.c.mount / path).write_text(content)
    sha = digest(ops.files.read(path))
    for call in (ops.patch_preview, ops.patch_apply):
        with pytest.raises(ShieldError, match="credentials") as exc:
            call(path, sha, [edit])
        assert exc.value.kind == "secret_edit"
    assert (ops.c.mount / path).read_text() == content


def test_patch_refuses_addon_python(ops):
    path = "addons/plugin.video.example/default.py"
    (ops.c.mount / "addons/plugin.video.example").mkdir(parents=True)
    (ops.c.mount / path).write_text("x = 1\n")
    with pytest.raises(ShieldError, match="Add-on Python"):
        ops.patch_preview(path, digest(b"x = 1\n"), [{"before": "1", "after": "2"}])


def test_widget_cache_tools(ops):
    ops.t.manager = lambda path, method="GET", body=None: (
        ops.t.calls.append((path, method)) or {"path": path, "api_token": "private-token-1"}
    )
    result = ops.widget_cache()
    assert result["status"]["path"] == "/api/widget-cache"
    assert result["rows"]["path"] == "/api/widget-cache/rows"
    assert "private-token-1" not in json.dumps(result)
    ops.widget_cache_refresh()
    assert ("/api/widget-cache/refresh", "POST") in ops.t.calls
    ops.c = replace(ops.c, allow_writes=False)
    with pytest.raises(ShieldError, match="disabled"):
        ops.widget_cache_refresh()


def test_widget_cache_needs_manager_06(ops):
    def old_manager(path, method="GET", body=None):
        raise ShieldError("Device HTTP request failed (404)", "service_error")

    ops.t.manager = old_manager
    with pytest.raises(ShieldError, match="0.6"):
        ops.widget_cache()


def test_video_library_reads_get_default_limits(ops):
    ops.rpc_read("VideoLibrary.GetMovies", {})
    ops.rpc_read("VideoLibrary.GetEpisodes", {"limits": {"start": 10, "end": 100_000}})
    calls = [c[1] for c in ops.t.calls if str(c[0]).startswith("VideoLibrary.")]
    assert calls[0]["limits"] == {"start": 0, "end": 50}
    assert calls[1]["limits"] == {"start": 10, "end": 510}


def test_missing_rpc_fields_are_friendly(ops):
    ops.t.rpc = lambda method, params=None: [] if method == "Player.GetActivePlayers" else {}
    with pytest.raises(ShieldError, match="returned no 'value'"):
        ops.set_core_setting("audiooutput.passthrough", True)


def test_apk_status_reports_bundle_and_installed_version(ops):
    backup_id = "a" * 32
    folder = ops.c.state / "apk_backups" / backup_id
    folder.mkdir(parents=True)
    (folder / "0.apk").write_bytes(b"original")
    manifest = {
        "backup_id": backup_id,
        "device": ops.c.serial,
        "package": "dev.example.player",
        "created": 1,
        "status": "verified",
        "original_version_code": 1,
        "candidate_version_code": 2,
        "original_apks": [{"sha256": digest(b"original")}],
        "kodi_data": None,
    }
    (folder / "manifest.json").write_text(json.dumps(manifest))
    ops.apks.installed = lambda package: {"version_code": 2}
    status = ops.apks.status(backup_id, verify_checksums=True)
    assert status["status"] == "verified" and status["installed_matches"] == "candidate"
    assert status["original_apks"] == [
        {"file": "0.apk", "present": True, "bytes": 8, "sha256_ok": True}
    ]
    with pytest.raises(ShieldError, match="Invalid"):
        ops.apks.status("../etc")


def test_progress_callback_is_safe_without_event_loop():
    events = []

    class Ctx:
        async def report_progress(self, progress, total=None, message=None):
            events.append((progress, total, message))

    assert progress_callback(None) is None
    # Not inside an anyio worker thread: progress must be dropped silently, not raise.
    progress_callback(Ctx())(1, 2, "stage")


def test_progress_reaches_context_from_worker_thread():
    import anyio

    events = []

    class Ctx:
        async def report_progress(self, progress, total=None, message=None):
            events.append((progress, total, message))

    async def main():
        report = progress_callback(Ctx())
        await anyio.to_thread.run_sync(lambda: [report(1, 3, "tar"), report(2, 3, "push")])

    anyio.run(main)
    assert events == [(1, 3, "tar"), (2, 3, "push")]


def test_rpc_error_message_is_kept_and_redacted():
    import httpx

    from nvidia_mcp.transport import Transport

    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "error": {
            "code": -32602,
            "message": "Invalid params.",
            "data": {
                "method": "Settings.SetSettingValue",
                "stack": {"name": "value"},
                "password": "pw-1",
            },
        },
    }
    t = Transport(Config(host="127.0.0.1"))
    t.http.close()
    t.http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=body)))
    with pytest.raises(ShieldError) as exc:
        t.rpc("Settings.SetSettingValue")
    assert "Invalid params." in str(exc.value) and "stack" in str(exc.value)
    assert "pw-1" not in str(exc.value) and "[rpc_error]" in str(exc.value)
    t.close()


def test_error_kind_is_visible():
    assert str(ShieldError("Busy", "timeout")) == "Busy [timeout]"
    assert str(ShieldError("Plain")) == "Plain"


def test_retention_prunes_old_state(tmp_path):
    config = Config(host="127.0.0.1", state=tmp_path, keep_file_backups=1, keep_apk_backups=1)
    backups = tmp_path / "backups"
    backups.mkdir()
    old = time.time() - 200 * 86400
    for index in range(3):
        for suffix in (".json", ".bin"):
            path = backups / f"{index:032x}{suffix}"
            path.write_text("{}")
            os.utime(path, (old + index, old + index))
    bundles = tmp_path / "apk_backups"
    for index, status in enumerate(["verified", "verified", "failed_after_transfer"]):
        folder = bundles / f"{index:032x}"
        folder.mkdir(parents=True)
        (folder / "manifest.json").write_text(json.dumps({"status": status}))
        os.utime(folder / "manifest.json", (old + index, old + index))
    stale = tmp_path / "apk_previews" / "stale"
    stale.mkdir(parents=True)
    os.utime(stale, (old, old))
    fresh = tmp_path / "apk_previews" / "fresh"
    fresh.mkdir()
    removed = prune_state(config)
    assert removed == {"file_backups": 2, "apk_backups": 1, "apk_previews": 1}
    assert len(list(backups.glob("*.json"))) == 1 and len(list(backups.glob("*.bin"))) == 1
    assert (bundles / f"{2:032x}").exists()  # failed bundles are kept for recovery
    assert fresh.exists() and not stale.exists()
    assert prune_state(replace(config, retention_days=0))["file_backups"] == 0


def test_secret_helpers():
    assert privacy.contains_secret('<setting id="rd.auth">x</setting>')
    assert not privacy.contains_secret('<setting id="widget_limit">20</setting>')
    assert not privacy.contains_secret("https://example.com/repo/")
