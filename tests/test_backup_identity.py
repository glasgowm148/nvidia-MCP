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
    with pytest.raises(ShieldError, match="different device"):
        other.restore_data(backup)


def test_older_manifests_and_missing_adb_fall_back_to_host_and_port(ops):
    legacy = files_for(ops, "192.168.1.50", None)  # ADB unavailable: no serial recorded.
    backup = legacy.snapshot("userdata/advancedsettings.xml", b"<advancedsettings/>")
    manifest = json.loads((legacy.backups / f"{backup}.json").read_text())
    assert "device_id" not in manifest
    same_host = files_for(ops, "192.168.1.50", "0423318016789")
    assert [b["backup_id"] for b in same_host.list_backups()] == [backup]
    assert files_for(ops, "192.168.1.51", "0423318016789").list_backups() == []


def test_recorded_hardware_identity_cannot_downgrade_to_ip(ops):
    first = files_for(ops, "192.168.1.50", "0423318016789")
    backup = first.snapshot("userdata/advancedsettings.xml", b"<advancedsettings/>")
    unavailable = files_for(ops, "192.168.1.50", None)
    assert unavailable.list_backups() == []
    with pytest.raises(ShieldError):
        unavailable.restore_data(backup)


@pytest.mark.parametrize("serial", ["unknown", "UNKNOWN", "null", "000000000000"])
def test_placeholder_serials_do_not_identify_different_devices(ops, serial):
    first = files_for(ops, "192.168.1.50", serial)
    backup = first.snapshot("userdata/advancedsettings.xml", b"<advancedsettings/>")
    assert first.device_id() is None
    assert files_for(ops, "192.168.1.51", serial).list_backups() == []
    assert [row["backup_id"] for row in first.list_backups()] == [backup]


def test_cached_identity_cannot_hide_device_replacement(ops):
    files = files_for(ops, "192.168.1.50", "0423318016789")
    backup = files.snapshot("userdata/advancedsettings.xml", b"<advancedsettings/>")
    files.t.serialno = "0999999999999"
    with pytest.raises(ShieldError):
        files.restore_data(backup)


def test_backup_reads_remain_bounded_when_private_files_are_corrupt(ops, monkeypatch):
    files = files_for(ops, "192.168.1.50", "0423318016789")
    backup = files.snapshot("userdata/advancedsettings.xml", b"<advancedsettings/>")
    original = type(files.backups).open

    class Bounded:
        def __init__(self, handle, limit):
            self.handle, self.limit = handle, limit

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.handle.close()

        def read(self, size=-1):
            assert 0 < size <= self.limit, "unbounded private backup read"
            return self.handle.read(size)

    def open_file(path, mode="r", *args, **kwargs):
        handle = original(path, mode, *args, **kwargs)
        if path.parent == files.backups and mode == "rb":
            return Bounded(handle, 600_001 if path.suffix == ".bin" else 64_001)
        return handle

    monkeypatch.setattr(type(files.backups), "open", open_file)
    assert files.restore_data(backup)[1] == b"<advancedsettings/>"
