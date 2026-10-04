from dataclasses import replace

import pytest

from nvidia_mcp.config import Config, ShieldError, private_host
from nvidia_mcp.files import digest, relative
from nvidia_mcp.privacy import file_text, scrub, text


@pytest.mark.parametrize(
    "path",
    [
        "../.env",
        "/etc/passwd",
        "userdata/../addons/x.py",
        "addons//x.py",
        "userdata/a;id",
        "userdata/./a.xml",
        "secret.txt",
    ],
)
def test_paths_refuse_traversal_and_shell_injection(path):
    with pytest.raises(ShieldError):
        relative(path)


@pytest.mark.parametrize(
    "host",
    ["8.8.8.8", "0.0.0.0", "224.0.0.1", "example.com", "127.0.0.1:8080", "http://192.168.1.50"],
)
def test_device_scope(host):
    with pytest.raises(ShieldError):
        private_host(host)


def test_config_rejects_invalid_ports(monkeypatch):
    monkeypatch.setenv("SHIELD_HOST", "192.168.1.50")
    monkeypatch.setenv("KODI_PORT", "0")
    with pytest.raises(ShieldError):
        Config.from_env()


def test_redaction_covers_xml_json_and_signed_streams():
    xml = '<settings><setting id="trakt.token">opaque-credential</setting><setting id="autoplay">true</setting></settings>'
    clean = file_text(xml)
    assert "opaque-credential" not in clean and "true" in clean
    assert "opaque" not in str(scrub({"id": "trakt.token", "value": "opaque"}))
    clean = text(
        "Bearer secretvalue stream https://cdn.example/video?signature=private email=person@example.com password=badword"
    )
    assert all(
        v not in clean
        for v in ["secretvalue", "signature=private", "person@example.com", "badword"]
    )
    assert "opaque" not in file_text('<setting id="token">opaque')


def test_busy_or_unknown_playback_prevents_disruption(ops):
    ops.t.players = [{"playerid": 1}]
    with pytest.raises(ShieldError, match="playing"):
        ops.lifecycle("restart")
    assert not any(c[0] == "shell" for c in ops.t.calls)
    ops.t.players = []
    ops.t.offline = True
    with pytest.raises(ShieldError, match="unknown"):
        ops.lifecycle("restart")
    assert not any(c[0] == "shell" for c in ops.t.calls)


def test_explicit_offline_recovery_and_other_app_guard(ops):
    ops.t.offline = True
    ops.lifecycle("start", allow_offline=True)
    original = ops.t.shell
    ops.t.shell = lambda *a, **kw: (
        "mResumedActivity: com.google.android.youtube.tv/.Main"
        if a[0] == "dumpsys"
        else original(*a, **kw)
    )
    with pytest.raises(ShieldError, match="Another TV app"):
        ops.lifecycle("start", allow_offline=True)


def test_write_disabled_and_running_kodi_cannot_patch(ops):
    path = "userdata/test.py"
    (ops.c.mount / path).write_text("value = 1\n")
    edits = [{"before": "value = 1", "after": "value = 2"}]
    sha = digest(ops.files.read(path))
    ops.c = replace(ops.c, allow_writes=False)
    assert ops.patch_file(path, sha, edits)["dry_run"]
    with pytest.raises(ShieldError, match="disabled"):
        ops.patch_file(path, sha, edits, False)
    ops.c = replace(ops.c, allow_writes=True)
    ops.t.running = True
    with pytest.raises(ShieldError, match="Stop Kodi"):
        ops.patch_file(path, sha, edits, False)
    assert ops.files.read(path) == b"value = 1\n"


def test_patch_restore_and_conflicts(ops):
    path = "userdata/test.py"
    (ops.c.mount / path).write_text("value = 1\n")
    original = ops.files.read(path)
    edits = [{"before": "value = 1", "after": "value = 2"}]
    change = ops.patch_file(path, digest(original), edits, False)
    assert ops.files.read(path) == b"value = 2\n"
    with pytest.raises(ShieldError, match="changed"):
        ops.patch_file(path, digest(original), edits, False)
    restored = ops.restore_file(change["backup_id"], change["sha256"])
    assert ops.files.read(path) == original and restored["undo_backup_id"]
    assert "value = 1" not in (ops.c.state / "audit.jsonl").read_text()


def test_ambiguous_anchor_syntax_and_backup_integrity(ops):
    path = "userdata/test.py"
    (ops.c.mount / path).write_text("a = 1\nb = 1\n")
    sha = digest(ops.files.read(path))
    with pytest.raises(ShieldError, match="exactly once"):
        ops.patch_file(path, sha, [{"before": "1", "after": "2"}], False)
    with pytest.raises(ShieldError, match="syntax"):
        ops.patch_file(path, sha, [{"before": "a = 1", "after": "a = ("}], False)
    backup = ops.files.snapshot(path, ops.files.read(path))
    (ops.files.backups / (backup + ".bin")).write_bytes(b"changed")
    with pytest.raises(ShieldError, match="checksum"):
        ops.restore_file(backup, sha)


def test_symlink_escape_is_refused(ops, tmp_path):
    outside = tmp_path / "outside.xml"
    outside.write_text("private")
    try:
        (ops.c.mount / "userdata/link.xml").symlink_to(outside)
    except OSError:
        pytest.skip("Windows does not grant symlink privileges")
    with pytest.raises(ShieldError, match="Symlink"):
        ops.files.read("userdata/link.xml")


def test_addon_settings_target_active_profile_and_check_version(ops):
    addon = "plugin.video.example"
    metadata = ops.c.mount / "addons" / addon
    metadata.mkdir(parents=True)
    (metadata / "addon.xml").write_text(f'<addon id="{addon}" version="1.2"/>')
    for profile in ("userdata", "userdata/profiles/kids"):
        p = ops.c.mount / profile / "addon_data" / addon
        p.mkdir(parents=True)
        (p / "settings.xml").write_text(
            '<settings><setting id="autoplay" default="true">false</setting></settings>'
        )
    ops.t.profile = "Kids"
    with pytest.raises(ShieldError, match="version"):
        ops.set_addon_setting(addon, "1.3", "autoplay", True)
    ops.set_addon_setting(addon, "1.2", "autoplay", True)
    assert (
        ">true<"
        in (ops.c.mount / f"userdata/profiles/kids/addon_data/{addon}/settings.xml").read_text()
    )
    assert ">false<" in (ops.c.mount / f"userdata/addon_data/{addon}/settings.xml").read_text()
    with pytest.raises(ShieldError, match="credential"):
        ops.set_addon_setting(addon, "1.2", "trakt.token", "do-not-change")


def test_core_setting_readback_and_backup(ops):
    result = ops.set_core_setting("audiooutput.passthrough", True)
    assert result["previous"] is False and result["current"] is True
    assert ops.files.restore_data(result["backup_id"])[0] == "userdata/guisettings.xml"


def test_settings_search_is_paginated_and_redacted(ops):
    tree = {
        "categories": [
            {
                "settings": [
                    {"id": "option" + str(i), "label": "Autoplay " + str(i), "value": True}
                    for i in range(30)
                ]
            },
            {
                "settings": [
                    {"id": "trakt.token", "value": "private-cloud-credential", "secret": True}
                ]
            },
        ]
    }
    page = ops.settings_page(tree, "Autoplay", 0, 25)
    assert len(page["settings"]) == 25 and page["total"] == 30 and page["next_start"] == 25
    assert len(ops.settings_page(tree, "Autoplay", 25, 25)["settings"]) == 5
    assert "private-cloud-credential" not in str(ops.settings_page(tree, "token", 0, 25))


def test_offline_running_kodi_does_not_assume_saved_profile(ops):
    ops.t.offline = True
    ops.t.running = True
    with pytest.raises(ShieldError, match="no profile assumed"):
        ops.profile_userdata()


def test_android_log_location_and_bounded_redacted_tail(ops):
    temp = ops.c.mount / "temp"
    temp.mkdir()
    (temp / "kodi.log").write_text(
        "old line\nERROR curl timeout https://cdn.example/path?token=private\nFATAL SIGSEGV\n"
    )
    report = ops.logs(lines=2)
    assert "old line" not in report["lines"] and "private" not in report["lines"]
    assert report["signals"]["crash"] == 2


def test_rpc_and_plugin_action_escape_hatches_refused(ops):
    with pytest.raises(ShieldError):
        ops.rpc_read("XBMC.ExecuteBuiltin", {"command": "quit"})
    with pytest.raises(ShieldError, match="utility"):
        ops.directory("plugin://plugin.video.example/?action=delete")
    with pytest.raises(ShieldError):
        ops.directory("https://example.com/private")
    assert not any(c[0] == "Files.GetDirectory" for c in ops.t.calls)


def test_layout_preview_is_immutable_profile_bound_and_expires(ops):
    plan = {
        "section_id": "hub:moviehub",
        "expected_revision": "rev1",
        "rows": [{"id": "row1", "label": "Trending", "path": "plugin://plugin.video.example/"}],
    }
    token = ops.layout_preview(plan)["preview_id"]
    plan["rows"][0]["label"] = "Changed after preview"
    ops.t.profile = "Kids"
    with pytest.raises(ShieldError, match="profile changed"):
        ops.layout_apply(token)
    ops.t.profile = "Adults"
    ops.layout_apply(token)
    apply = next(c for c in ops.t.calls if c[0] == "/api/widgets/layout/apply")
    assert apply[2]["rows"][0]["label"] == "Trending"
    with pytest.raises(ShieldError, match="expired"):
        ops.layout_apply(token)
    token = ops.layout_preview(plan)["preview_id"]
    saved = ops.plans[token]
    ops.plans[token] = (saved[0] - 601, *saved[1:])
    with pytest.raises(ShieldError, match="expired"):
        ops.layout_apply(token)
