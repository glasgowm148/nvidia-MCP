"""Catch an ignored/missing companion even when source-tree export tests pass."""

import hashlib
import importlib.util
import io
import json
import tarfile
from pathlib import Path
from zipfile import ZipFile

import pytest

spec = importlib.util.spec_from_file_location(
    "check_release", Path(__file__).resolve().parents[1] / "scripts/check_release.py"
)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def zip_bytes(members):
    stream = io.BytesIO()
    with ZipFile(stream, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return stream.getvalue()


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
@pytest.mark.parametrize("damage", ["none", "missing", "checksum", "extra"])
def test_packaged_companion_is_required_and_matches_manifest(tmp_path, kind, damage):
    payload = zip_bytes({"service.kodi.addonadmin/addon.xml": b'<addon version="1.0.0" />'})
    filename = "service.kodi.addonadmin-1.0.0.zip"
    prefix = "nvidia_mcp/companion/" if kind == "wheel" else "example-1.0/src/nvidia_mcp/companion/"
    manifest = {
        "version": "1.0.0",
        "filename": filename,
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    members = {prefix + "manifest.json": json.dumps(manifest).encode(), prefix + filename: payload}
    if damage == "missing":
        del members[prefix + filename]
    elif damage == "checksum":
        members[prefix + filename] = zip_bytes({"altered.txt": b"changed"})
    elif damage == "extra":
        members[prefix + "service.kodi.addonadmin-0.9.0.zip"] = payload
    path = tmp_path / ("example.whl" if kind == "wheel" else "example.tar.gz")
    if kind == "wheel":
        path.write_bytes(zip_bytes(members))
    else:
        with tarfile.open(path, "w:gz") as archive:
            for name, data in members.items():
                info = tarfile.TarInfo(name)
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
    if damage == "none":
        release.inspect_archive(path)
    else:
        with pytest.raises(ValueError, match="companion"):
            release.inspect_archive(path)
