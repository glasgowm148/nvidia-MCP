"""Regression tests for the 2026-10-05 review fixes."""

import hashlib
import json
from dataclasses import replace

import pytest

from nvidia_mcp import privacy
from nvidia_mcp.config import ShieldError


@pytest.mark.parametrize(
    "setting", ["videoplayer.adjustrefreshrate", "videoscreen.delayrefreshchange"]
)
def test_refresh_rate_settings_are_not_credentials(setting):
    assert not privacy.SECRET.search(setting)
    assert privacy.scrub({"id": setting, "value": 2})["value"] == 2


@pytest.mark.parametrize("key", ["refresh_token", "trakt.refresh.token", "refresh-key", "token"])
def test_refresh_tokens_are_still_credentials(key):
    assert privacy.SECRET.search(key)


def test_refresh_rate_can_be_read_and_changed_once_allowed(ops):
    ops.t.settings["videoplayer.adjustrefreshrate"] = 0
    assert ops.rpc_read(
        "Settings.GetSettingValue", {"setting": "videoplayer.adjustrefreshrate"}
    ) == {"value": 0}
    # Refresh-rate switching can blank some TVs, so it needs the user's exact opt-in.
    ops.c = replace(ops.c, allow_settings=("videoplayer.adjustrefreshrate",))
    result = ops.set_core_setting("videoplayer.adjustrefreshrate", 2)
    assert result["current"] == 2


def test_start_needs_no_offline_flag_when_kodi_is_stopped(ops):
    ops.t.offline = True
    ops.t.running = False
    shell = ops.t.shell
    ops.t.shell = lambda *a, **kw: (
        "mResumedActivity: com.google.android.tvlauncher/.MainActivity"
        if a == ("dumpsys", "activity", "activities")
        else shell(*a, **kw)
    )
    assert ops.lifecycle("start")["requested"] == "start"


def test_start_while_running_still_checks_playback(ops):
    ops.t.offline = True
    ops.t.running = True
    with pytest.raises(ShieldError, match="unknown"):
        ops.lifecycle("start")
    ops.t.offline = False
    ops.t.players = [{"playerid": 1}]
    with pytest.raises(ShieldError, match="playing"):
        ops.lifecycle("start")


def test_non_utf8_file_raises_actionable_error(ops):
    data = b"<a>caf\xe9</a>"
    (ops.c.mount / "userdata/latin.xml").write_bytes(data)
    with pytest.raises(ShieldError, match="not UTF-8"):
        ops.read_file("userdata/latin.xml")
    with pytest.raises(ShieldError, match="not UTF-8"):
        ops.patch_file(
            "userdata/latin.xml", hashlib.sha256(data).hexdigest(), [{"before": "a", "after": "b"}]
        )


def test_corrupt_backup_manifest_does_not_hide_others(ops):
    good = ops.files.snapshot("userdata/guisettings.xml", b"<settings/>")
    (ops.files.backups / "broken.json").write_text("{not json")
    (ops.files.backups / "wrong.json").write_text(json.dumps(["not", "a", "dict"]))
    rows = ops.files.list_backups()
    assert [row["backup_id"] for row in rows] == [good]


# --- 2026-10-15 deep audit -------------------------------------------------------------


def test_playback_refusals_carry_refusal_kinds(ops):
    from nvidia_mcp.operation_records import REFUSALS

    ops.t.running = True
    ops.t.players = [{"playerid": 1}]
    with pytest.raises(ShieldError, match="Kodi is playing") as error:
        ops.set_core_setting("audiooutput.passthrough", True)
    assert error.value.kind == "playing" and "playing" in REFUSALS
    ops.t.players = {"unexpected": True}
    with pytest.raises(ShieldError, match="Playback state is unknown") as error:
        ops.set_core_setting("audiooutput.passthrough", True)
    assert error.value.kind == "playback_unknown" and "playback_unknown" in REFUSALS


def test_editing_files_under_a_running_kodi_is_a_refusal(ops):
    from nvidia_mcp.operation_records import REFUSALS

    ops.t.running = True
    with pytest.raises(ShieldError, match="Stop Kodi") as error:
        ops.stopped()
    assert error.value.kind == "app_running" and "app_running" in REFUSALS


@pytest.mark.parametrize("addon_id", [".", "..", "a..b", ".hidden", "trailing.", "a/b", ""])
def test_dot_segment_addon_ids_never_reach_manager(ops, addon_id):
    ops.c = replace(ops.c, manager_token="synthetic-manager-token")
    calls = [
        lambda: ops.manager_read("backups", addon_id),
        lambda: ops.addon_settings(addon_id),
        lambda: ops.set_addon_setting(addon_id, "1", "autoplay", True),
        lambda: ops.configuration_backup(addon_id),
        lambda: ops.configuration_restore("backup-1", addon_id),
    ]
    for call in calls:
        with pytest.raises(ShieldError, match="add-on"):
            call()
    assert not [c for c in ops.t.calls if isinstance(c[0], str) and c[0].startswith("/api/")]


@pytest.mark.parametrize(
    "addon_id", ["plugin.video.pov", "script.module.a4ksubtitles", "service.kodi.addonadmin"]
)
def test_real_addon_ids_are_accepted(ops, addon_id):
    ops.c = replace(ops.c, manager_token="synthetic-manager-token")
    ops.manager_read("backups", addon_id)
    assert ops.t.calls[-1][0] == f"/api/addons/{addon_id}/backups"


KM_SETTINGS = {
    "addon_id": "plugin.video.fenlight",
    "editable": False,
    "read_only_reason": "Add-on is outside the detected stack",
    "groups": [
        {"settings": [{"id": "autoplay", "value": "true", "editable": True, "raw": {}}]},
        {
            "id": "raw_user_settings",
            "settings": [
                {
                    "id": "legacy.flag",
                    "value": "1",
                    "editable": True,
                    "warning": "Schema missing; edited as raw text",
                    "raw": {"source": "raw"},
                }
            ],
        },
        {
            "id": "fenlight_db",
            "settings": [
                {
                    "id": "results.timeout",
                    "value": "20",
                    "editable": True,
                    "raw": {"source": "plugin.video.fenlight/databases/settings.db"},
                }
            ],
        },
    ],
}


def fake_manager(ops, listing):
    ops.c = replace(ops.c, manager_token="synthetic-manager-token")

    def manager(path, method="GET", body=None):
        ops.t.calls.append((path, method, json.loads(json.dumps(body))))
        if method == "GET" and path.endswith("/settings"):
            return json.loads(json.dumps(listing))
        return {"changed_count": 1, "backup_id": "manager-owned-backup"}

    ops.t.manager = manager


def test_manager_settings_keep_store_and_addon_editability(ops):
    fake_manager(ops, KM_SETTINGS)
    page = ops.addon_settings("plugin.video.fenlight")
    assert page["editable"] is False
    assert page["read_only_reason"] == "Add-on is outside the detected stack"
    rows = {row["id"]: row for row in page["settings"]}
    assert "source" not in rows["autoplay"]
    assert rows["legacy.flag"]["source"] == "raw"
    assert rows["results.timeout"]["source"] == "settings.db"


@pytest.mark.parametrize(
    ("setting", "source"),
    [("autoplay", None), ("legacy.flag", "raw"), ("results.timeout", "settings.db"), ("x", None)],
)
def test_addon_setting_patch_names_the_listed_store(ops, setting, source):
    addon = "plugin.video.fenlight"
    (ops.c.mount / "addons" / addon).mkdir(parents=True)
    (ops.c.mount / "addons" / addon / "addon.xml").write_text(f'<addon id="{addon}" version="1"/>')
    fake_manager(ops, KM_SETTINGS)
    ops.set_addon_setting(addon, "1", setting, "5")
    patch = [c for c in ops.t.calls if c[1] == "PATCH"]
    expected = {"id": setting, "value": "5"} | ({"source": source} if source else {})
    assert patch == [(f"/api/addons/{addon}/settings", "PATCH", {"changes": [expected]})]


def test_addon_setting_listed_in_two_stores_is_refused(ops):
    addon = "plugin.video.fenlight"
    (ops.c.mount / "addons" / addon).mkdir(parents=True)
    (ops.c.mount / "addons" / addon / "addon.xml").write_text(f'<addon id="{addon}" version="1"/>')
    listing = json.loads(json.dumps(KM_SETTINGS))
    listing["groups"][2]["settings"][0]["id"] = "autoplay"
    fake_manager(ops, listing)
    with pytest.raises(ShieldError, match="more than one store") as error:
        ops.set_addon_setting(addon, "1", "autoplay", "5")
    assert error.value.kind == "invalid_request"
    assert not [c for c in ops.t.calls if c[1] == "PATCH"]


@pytest.mark.parametrize("has_reset", [True, False])
def test_connect_clears_cached_adb_forwards(ops, has_reset):
    events = []

    class Transport:
        def adb(self, *args, **kwargs):
            events.append(args[0])
            return b"device\n"

    if has_reset:
        Transport.reset_forwards = lambda self: events.append("reset_forwards")
    ops.t = Transport()
    assert ops.connect() == {"state": "device"}
    expected = ["connect", "reset_forwards", "get-state"] if has_reset else ["connect", "get-state"]
    assert events == expected
