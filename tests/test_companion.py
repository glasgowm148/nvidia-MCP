import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest

from nvidia_mcp.companion import companion_metadata, export_manager
from nvidia_mcp.config import ShieldError


def test_export_pinned_companion_and_preserve_existing_files(tmp_path):
    result = export_manager(tmp_path)
    target = Path(result["path"])
    metadata = companion_metadata()
    assert hashlib.sha256(target.read_bytes()).hexdigest() == metadata["sha256"]
    assert result["version"] == "0.4.2"
    assert result["installed_on_device"] is False
    assert export_manager(tmp_path) == result
    with ZipFile(target) as archive:
        assert b'version="0.4.2"' in archive.read("service.kodi.addonadmin/addon.xml")
        assert not any("device_fixes" in name or ".env" in name for name in archive.namelist())
    target.write_bytes(b"preserve-this-file")
    with pytest.raises(ShieldError, match="different file"):
        export_manager(tmp_path)
    assert target.read_bytes() == b"preserve-this-file"


def test_export_cli_needs_no_device_configuration(tmp_path):
    env = {
        key: value for key, value in os.environ.items() if not key.startswith(("SHIELD_", "KODI_"))
    }
    result = subprocess.run(
        [sys.executable, "-m", "nvidia_mcp.server", "--export-manager", str(tmp_path)],
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["installed_on_device"] is False


def test_failed_bundle_integrity_cannot_export(tmp_path, monkeypatch):
    metadata = companion_metadata()
    metadata["sha256"] = "0" * 64
    monkeypatch.setattr("nvidia_mcp.companion.companion_metadata", lambda: metadata)
    with pytest.raises(ShieldError, match="checksum"):
        export_manager(tmp_path)
    assert list(tmp_path.iterdir()) == []
