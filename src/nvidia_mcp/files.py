"""Kodi-scoped file access, checksum-checked patches and private rollback snapshots."""

import hashlib
import json
import os
import re
import tempfile
import uuid
from pathlib import Path, PurePosixPath

from .config import ShieldError

MAX_FILE = 600_000


def digest(data):
    return hashlib.sha256(data).hexdigest()


def relative(path):
    if not isinstance(path, str) or not re.fullmatch(r"[A-Za-z0-9_./ -]+", path):
        raise ShieldError("Use a simple relative Kodi path")
    p = PurePosixPath(path)
    if p.is_absolute() or ".." in p.parts or path != str(p) or not p.parts:
        raise ShieldError("Absolute paths, traversal and ambiguous path segments are forbidden")
    if p.parts[0] not in ("addons", "userdata") and path not in (
        "kodi.log",
        "kodi.old.log",
        "temp/kodi.log",
        "temp/kodi.old.log",
    ):
        raise ShieldError("File tools are scoped to Kodi addons, userdata and Kodi logs")
    return path


class Files:
    def __init__(self, transport):
        self.t = transport
        self.c = transport.c
        self.backups = self.c.state / "backups"

    def location(self, path, must_exist=False):
        path = relative(path)
        if self.c.mount:
            root = self.c.mount.resolve()
            target = root / path
            if not target.resolve().is_relative_to(root) or any(
                p.is_symlink() for p in [target, *target.parents] if p != root
            ):
                raise ShieldError("Symlinked Kodi files/directories are not supported")
            if must_exist and not target.is_file():
                raise ShieldError(f"Kodi file not found: {path}", "not_found")
            return target
        root = self.t.shell("readlink", "-f", self.c.remote_root)
        target = self.t.shell("readlink", "-f", self.c.remote_root + "/" + path)
        if not root or not target.startswith(root + "/"):
            raise ShieldError("Kodi path unavailable or escapes the configured root")
        if must_exist and not self.t.is_file(target):
            raise ShieldError(f"Kodi file not found: {path}", "not_found")
        return target

    def read(self, path):
        target = self.location(path, must_exist=True)
        try:
            if self.c.mount:
                with target.open("rb") as f:
                    data = f.read(MAX_FILE + 1)
            else:
                data = self.t.exec_out(
                    ["head", "-c", str(MAX_FILE + 1), str(target)], limit=MAX_FILE + 1
                )
        except OSError:
            raise ShieldError(
                "Cannot read Kodi file: check the mounted share and file permissions"
            ) from None
        if len(data) > MAX_FILE:
            raise ShieldError("File exceeds 600 KB; use the bounded log tool for logs")
        return data

    def tail(self, path, lines):
        target = self.location(path, must_exist=True)
        if self.c.mount:
            try:
                with target.open("rb") as f:
                    f.seek(0, os.SEEK_END)
                    f.seek(max(0, f.tell() - MAX_FILE))
                    data = f.read(MAX_FILE)
            except OSError:
                raise ShieldError(
                    "Cannot read Kodi log: check the mounted share and file permissions"
                ) from None
            return b"\n".join(data.splitlines()[-lines:]).decode("utf-8", "replace")
        data = self.t.exec_out(["tail", "-n", str(lines), str(target)], limit=MAX_FILE)
        return data.decode("utf-8", "replace").strip()

    def snapshot(self, path, data):
        self.backups.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.c.state.chmod(0o700)
        self.backups.chmod(0o700)
        backup_id = uuid.uuid4().hex
        blob = self.backups / (backup_id + ".bin")
        blob.write_bytes(data)
        blob.chmod(0o600)
        manifest = self.backups / (backup_id + ".json")
        manifest.write_text(
            json.dumps({"path": relative(path), "sha256": digest(data), "device": self.c.serial})
        )
        manifest.chmod(0o600)
        return backup_id

    def write(self, path, data, expected):
        target = self.location(path)
        if digest(self.read(path)) != expected:
            raise ShieldError("File changed since inspection; read it again before applying")
        if self.c.mount:
            temp = target.with_name(".nvidia-mcp-" + uuid.uuid4().hex)
            try:
                with temp.open("xb") as f:
                    f.write(data)
                    f.flush()
                    os.fsync(f.fileno())
                os.chmod(temp, target.stat().st_mode & 0o777)
                if digest(self.read(path)) != expected:
                    raise ShieldError("File changed while staging; patch cancelled")
                os.replace(temp, target)
            finally:
                temp.unlink(missing_ok=True)
        else:
            remote_temp = str(target) + ".nvidia-mcp-" + uuid.uuid4().hex
            with tempfile.TemporaryDirectory() as local:
                staging = Path(local) / "staging"
                staging.write_bytes(data)
                staging.chmod(0o600)
                try:
                    self.t.adb("push", str(staging), remote_temp)
                    self.t.shell("chmod", "600", remote_temp)
                    if digest(self.read(path)) != expected:
                        raise ShieldError("File changed while staging; patch cancelled")
                    self.t.shell("mv", "-f", remote_temp, str(target))
                finally:
                    self.t.shell("rm", "-f", remote_temp)
        if digest(self.read(path)) != digest(data):
            raise ShieldError(
                "Write verification failed; restore the returned backup before restarting Kodi"
            )

    def list_backups(self, limit=50):
        rows = []
        if not self.backups.exists():
            return rows
        manifests = sorted(
            self.backups.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True
        )[:limit]
        for p in manifests:
            try:
                d = json.loads(p.read_text())
                if d.get("device") == self.c.serial:
                    rows.append({"backup_id": p.stem, "path": d["path"], "sha256": d["sha256"]})
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                continue  # A corrupt manifest must not hide every other snapshot.
        return rows

    def restore_data(self, backup_id):
        if not re.fullmatch(r"[0-9a-f]{32}", backup_id):
            raise ShieldError("Invalid backup ID")
        info = json.loads((self.backups / (backup_id + ".json")).read_text())
        if info["device"] != self.c.serial:
            raise ShieldError("Backup belongs to a different Shield")
        data = (self.backups / (backup_id + ".bin")).read_bytes()
        if len(data) > MAX_FILE or digest(data) != info["sha256"]:
            raise ShieldError("Backup checksum failed")
        return relative(info["path"]), data
