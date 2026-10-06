"""Regression tests for the 2026-10-05 review fixes."""

import hashlib
import json

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


def test_refresh_rate_can_be_read_and_changed(ops):
    ops.t.settings["videoplayer.adjustrefreshrate"] = 0
    assert ops.rpc_read(
        "Settings.GetSettingValue", {"setting": "videoplayer.adjustrefreshrate"}
    ) == {"value": 0}
    result = ops.set_core_setting("videoplayer.adjustrefreshrate", 2)
    assert result["current"] == 2


def test_start_needs_no_offline_flag_when_kodi_is_stopped(ops):
    ops.t.offline = True
    ops.t.running = False
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
