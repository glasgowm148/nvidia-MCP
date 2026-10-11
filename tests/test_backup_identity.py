"""Private backups follow the Shield's hardware serial, not its (DHCP) address."""

import json
from dataclasses import replace

import pytest
from conftest import FakeTransport

from nvidia_mcp.config import ShieldError
from nvidia_mcp.files import Files


class Shield(FakeTransport):
    def __init__(self, config, serialno):
        super().__init__(config)
        self.serialno = serialno

    def shell(self, *args, **kwargs):
        if args == ("getprop", "ro.serialno"):
            if self.serialno is None:
                raise ShieldError("ADB is not connected", "unreachable")
            return self.serialno + "\n"
        return super().shell(*args, **kwargs)


def files_for(ops, host, serialno):
    return Files(Shield(replace(ops.c, host=host), serialno))


def test_backups_survive_a_new_dhcp_address(ops):
    (ops.c.mount / "userdata/advancedsettings.xml").write_text("<advancedsettings/>")
    before = files_for(ops, "192.168.1.50", "0423318016789")
    backup = before.snapshot("userdata/advancedsettings.xml", b"<advancedsettings/>")
    after = files_for(ops, "192.168.1.51", "0423318016789")
    assert [b["backup_id"] for b in after.list_backups()] == [backup]
    assert after.restore_data(backup)[0] == "userdata/advancedsettings.xml"


def test_backups_of_another_shield_at_the_same_address_are_refused(ops):
    first = files_for(ops, "192.168.1.50", "0423318016789")
    backup = first.snapshot("userdata/advancedsettings.xml", b"<advancedsettings/>")
    other = files_for(ops, "192.168.1.50", "0999999999999")
    assert other.list_backups() == []
    with pytest.raises(ShieldError, match="different Shield"):
        other.restore_data(backup)


def test_older_manifests_and_missing_adb_fall_back_to_host_and_port(ops):
    legacy = files_for(ops, "192.168.1.50", None)  # ADB unavailable: no serial recorded.
    backup = legacy.snapshot("userdata/advancedsettings.xml", b"<advancedsettings/>")
    manifest = json.loads((legacy.backups / f"{backup}.json").read_text())
    assert "device_id" not in manifest
    same_host = files_for(ops, "192.168.1.50", "0423318016789")
    assert [b["backup_id"] for b in same_host.list_backups()] == [backup]
    assert files_for(ops, "192.168.1.51", "0423318016789").list_backups() == []
