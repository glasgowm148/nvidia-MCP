"""ADB patches must not turn executable helper scripts into data files."""
from types import SimpleNamespace

import pytest

from nvidia_mcp.config import ShieldError
from nvidia_mcp.files import Files, digest


@pytest.mark.parametrize("mode", ["755", "640", "600"])
def test_adb_patch_preserves_mode(tmp_path, monkeypatch, mode):
    calls = []
    state = {"data": b"original"}

    def shell(*args):
        calls.append(args)
        if args[0] == "stat":
            return mode
        if args[0] == "mv":
            state["data"] = b"patched"
        return ""

    transport = SimpleNamespace(c=SimpleNamespace(mount=None, state=tmp_path), shell=shell,
                                adb=lambda *args: calls.append(args))
    files = Files(transport)
    monkeypatch.setattr(files, "location", lambda *a, **kw: "/kodi/addons/example/helper.sh")
    monkeypatch.setattr(files, "read", lambda *a: state["data"])
    files.write("addons/example/helper.sh", b"patched", digest(b"original"))
    assert next(c for c in calls if c[0] == "chmod")[1] == mode
    assert state["data"] == b"patched"


def test_unknown_permissions_refuse_before_upload(tmp_path, monkeypatch):
    uploads = []
    transport = SimpleNamespace(c=SimpleNamespace(mount=None, state=tmp_path),
                                shell=lambda *a: "unavailable", adb=lambda *a: uploads.append(a))
    files = Files(transport)
    monkeypatch.setattr(files, "location", lambda *a, **kw: "/kodi/addons/example/helper.sh")
    monkeypatch.setattr(files, "read", lambda *a: b"original")
    with pytest.raises(ShieldError, match="permissions"):
        files.write("addons/example/helper.sh", b"patched", digest(b"original"))
    assert not uploads
