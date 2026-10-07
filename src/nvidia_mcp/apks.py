"""Single-device, staged APK installation with verified originals and recovery bundles.

No updater websites, APK unpacking, automatic uninstall, downgrade or TV navigation.
"""

import copy
import json
import os
import re
import shutil
import tarfile
import time
import uuid
from pathlib import Path, PurePosixPath

from .android_tools import inspect_set, sha256_file
from .config import ShieldError, fingerprint
from .transport import TRAILER, checked_script, strip_status

MAX_BACKUP = 2_000_000_000
# Regenerable caches. Thumbnails alone often exceed the backup limit on real libraries.
SNAPSHOT_EXCLUDES = ("userdata/Thumbnails", "addons/packages", "addons/temp")
TTL = 600


def private_dir(path):
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)
    return path


def save_json(path, value):
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")
    path.chmod(0o600)


class ApkOperations:
    def __init__(self, operations):
        self.ops = operations
        self.t = operations.t
        self.c = operations.c
        self.plans = {}

    def installed(self, package):
        listed = self.t.shell("pm", "list", "packages", package, limit=16000).splitlines()
        if any(line and not line.startswith("package:") for line in listed):
            raise ShieldError("Installed package list is unavailable")
        if "package:" + package not in listed:
            return None
        text = self.t.shell("pm", "path", package, limit=16000)
        paths = [line[8:] for line in text.splitlines() if line.startswith("package:")]
        if not paths:
            raise ShieldError("Installed app has no readable APK paths")
        if len(paths) > 20 or any(
            not re.fullmatch(r"/(?:data/app|system|product|vendor)/[A-Za-z0-9_./=+~@-]+\.apk", path)
            or ".." in PurePosixPath(path).parts
            for path in paths
        ):
            raise ShieldError("Installed APK paths are unsupported")
        detail = self.t.shell("dumpsys", "package", package, limit=500_000)
        if re.search(r"(?:pkgFlags|flags)=\[[^\]]*\bSYSTEM\b", detail):
            raise ShieldError("System app updates are outside this tool's scope")
        code = re.search(r"\bversionCode=(\d+)\b", detail)
        if not code:
            raise ShieldError("Installed app version is unknown")
        hashes = []
        for path in paths:
            value = self.t.shell("sha256sum", path, limit=2000).split()
            if not value or not re.fullmatch(r"[a-fA-F0-9]{64}", value[0]):
                raise ShieldError("Cannot checksum installed APK; no install permitted")
            hashes.append(value[0].lower())
        return {"version_code": int(code[1]), "paths": paths, "sha256": hashes}

    def device(self):
        abis = self.t.shell("getprop", "ro.product.cpu.abilist").strip().split(",")
        sdk = self.t.shell("getprop", "ro.build.version.sdk").strip()
        if (
            not sdk.isdigit()
            or not abis
            or not all(re.fullmatch(r"[A-Za-z0-9_-]+", abi) for abi in abis)
        ):
            raise ShieldError("Shield Android SDK/CPU compatibility is unknown")
        return {"sdk": int(sdk), "abis": abis}

    def compatible(self, items, device):
        for item in items:
            if item["min_sdk"] > device["sdk"]:
                raise ShieldError("APK requires a newer Android version than this Shield")
            if item["abis"] and not set(item["abis"]) & set(device["abis"]):
                raise ShieldError("APK CPU architecture is incompatible with this Shield")

    def preview(self, paths, trusted_signers=None, progress=None):
        report = progress or (lambda *args: None)
        with self.ops.lock:
            now = time.monotonic()
            for key, value in list(self.plans.items()):
                if now - value["created"] > TTL:
                    shutil.rmtree(value["directory"], ignore_errors=True)
                    del self.plans[key]
            if len(self.plans) >= 5:
                raise ShieldError("Five APK previews are pending; apply or wait for expiry")
            report(0, 4, "Inspecting candidate APKs")
            base, items = inspect_set(paths, self.c)
            device = self.device()
            self.compatible(items, device)
            package = base["package"]
            original = self.installed(package)
            if original and base["version_code"] <= original["version_code"]:
                raise ShieldError("Only upgrades are supported; reinstall/downgrade refused")
            trusted_new = None if original else self.trusted_for_new_app(trusted_signers)
            preview_id = uuid.uuid4().hex
            directory = private_dir(private_dir(self.c.state) / "apk_previews" / preview_id)
            try:
                candidates = private_dir(directory / "candidate")
                staged = []
                for index, (path, item) in enumerate(zip(paths, items, strict=True)):
                    target = candidates / f"{index}.apk"
                    shutil.copyfile(path, target)
                    target.chmod(0o600)
                    if sha256_file(target) != item["sha256"]:
                        raise ShieldError("APK changed while staging; preview cancelled")
                    staged.append(str(target))
                inspect_set(staged, self.c)
                report(1, 4, "Saving the installed APKs from the Shield")
                originals = []
                if original:
                    folder = private_dir(directory / "original")
                    remaining = 1_000_000_000
                    for index, (remote, expected) in enumerate(
                        zip(original["paths"], original["sha256"], strict=True)
                    ):
                        target = folder / f"{index}.apk"
                        if remaining <= 0:
                            raise ShieldError("Installed APK set exceeds 1 GB")
                        self.t.download(remote, target, limit=min(600_000_000, remaining))
                        remaining -= target.stat().st_size
                        if sha256_file(target) != expected:
                            raise ShieldError("Installed APK changed while saving its original")
                        originals.append(str(target))
                    report(2, 4, "Verifying saved original APKs")
                    old_base, old_items = inspect_set(originals, self.c)
                    if (
                        old_base["package"] != package
                        or old_base["version_code"] != original["version_code"]
                    ):
                        raise ShieldError("Exported original does not match the installed app")
                    trusted = old_base["signers"]
                else:
                    old_items = []
                if original:
                    signed_ok = base["signers"] == trusted
                else:
                    signed_ok = bool(base["signers"]) and set(base["signers"]) <= trusted_new
                if not signed_ok:
                    raise ShieldError(
                        "APK verified signers differ from the trusted app; no install permitted"
                    )
                if self.installed(package) != original:
                    raise ShieldError("Installed app changed during preview")
                plan = {
                    "created": time.monotonic(),
                    "directory": directory,
                    "paths": staged,
                    "items": copy.deepcopy(items),
                    "originals": originals,
                    "original_items": copy.deepcopy(old_items),
                    "installed": original,
                    "device": device,
                    "package": package,
                    "version_code": base["version_code"],
                }
                self.plans[preview_id] = plan
                report(4, 4, "Preview ready")
                return {
                    "preview_id": preview_id,
                    "expires_in_seconds": TTL,
                    "package": package,
                    "installed_version_code": original["version_code"] if original else None,
                    "candidate": base,
                    "apk_count": len(items),
                    "original_apks_saved": len(originals),
                    "kodi_data_snapshot_required": package == "org.xbmc.kodi"
                    and original is not None,
                    "note": "No Shield changes. Apply requires write mode, stopped target app and known idle TV. APK backups do not contain Android app-private data.",
                }
            except Exception:
                shutil.rmtree(directory, ignore_errors=True)
                raise

    def trusted_for_new_app(self, requested=None):
        """Signer trust for new apps comes only from human config, never from the model.

        ``requested`` (a tool argument) can only narrow the configured set.
        """
        configured = frozenset(getattr(self.c, "trusted_signers", ()) or ())
        if not configured:
            raise ShieldError(
                "New app installation needs independently trusted SHA-256 signing "
                "fingerprints. The user must set NVIDIA_MCP_TRUSTED_SIGNERS (or "
                "NVIDIA_MCP_TRUSTED_SIGNERS_FILE); fingerprints passed by the agent are not trusted",
                "untrusted_signer",
            )
        if not requested:
            return configured
        try:
            narrowed = frozenset(fingerprint(value) for value in requested)
        except ShieldError:
            raise ShieldError("trusted_signers must be SHA-256 fingerprints") from None
        if not narrowed <= configured:
            raise ShieldError(
                "trusted_signers may only narrow NVIDIA_MCP_TRUSTED_SIGNERS; it lists a "
                "fingerprint the user has not configured",
                "untrusted_signer",
            )
        return narrowed

    def guard(self, package):
        return self.ops.guard_tv("apk", package=package)

    def kodi_snapshot(self, folder):
        self.ops.stopped()
        target = folder / "kodi-data.tar"
        if self.c.mount:
            self.mounted_snapshot(target)
        else:
            root = self.t.shell("readlink", "-f", self.c.remote_root).strip()
            if (
                not re.fullmatch(
                    r"/(?:storage/emulated/[0-9]+|sdcard|mnt/user/[0-9]+/primary)/[A-Za-z0-9_./ -]+",
                    root,
                )
                or ".." in PurePosixPath(root).parts
            ):
                raise ShieldError("Configured Kodi root cannot be verified for a full data backup")
            script, token = checked_script(
                ["tar", "-cf", "-", "-C", root]
                + ["--exclude=" + path for path in SNAPSHOT_EXCLUDES]
                + ["addons", "userdata"]
            )
            command = [self.c.adb_path, "-s", self.c.serial, "exec-out", script]
            self.t.stream_to_file(command, target, MAX_BACKUP + TRAILER, 300)
            # tar's exit status: a partial archive must never pass as a recovery bundle.
            strip_status(target, token)
        target.chmod(0o600)
        total, count, roots = 0, 0, set()
        try:
            with tarfile.open(target, "r:") as archive:
                for member in archive:
                    path = PurePosixPath(member.name)
                    count += 1
                    total += member.size
                    if (
                        path.is_absolute()
                        or any(
                            path.as_posix() == item or path.as_posix().startswith(item + "/")
                            for item in SNAPSHOT_EXCLUDES
                        )
                        or ".." in path.parts
                        or not path.parts
                        or path.parts[0] not in {"addons", "userdata"}
                        or not (member.isfile() or member.isdir())
                        or member.size < 0
                        or total > MAX_BACKUP
                        or count > 100_000
                    ):
                        raise ShieldError(
                            "Kodi data backup contains unsupported paths/types or exceeds limits"
                        )
                    roots.add(path.parts[0])
                    if member.isfile():
                        with archive.extractfile(member) as source:
                            read = 0
                            while chunk := source.read(65536):
                                read += len(chunk)
                            if read != member.size:
                                raise ShieldError("Kodi data backup is truncated")
            if roots != {"addons", "userdata"}:
                raise ShieldError("Kodi data backup is incomplete")
        except (OSError, tarfile.TarError):
            raise ShieldError("Kodi data backup could not be validated; no APK installed") from None
        return {
            "file": target.name,
            "sha256": sha256_file(target),
            "bytes": target.stat().st_size,
            "members": count,
            "excluded": list(SNAPSHOT_EXCLUDES),
        }

    def mounted_snapshot(self, target):
        root = self.c.mount.resolve()
        count, total = 0, 0
        with tarfile.open(target, "w") as archive:
            target.chmod(0o600)
            for name in ("addons", "userdata"):
                folder = root / name
                if not folder.is_dir() or folder.is_symlink():
                    raise ShieldError("Mounted Kodi addons/userdata is missing or symlinked")
                for current, dirs, files in os.walk(folder, followlinks=False):
                    relative_dir = Path(current).relative_to(root).as_posix()
                    dirs[:] = [d for d in dirs if f"{relative_dir}/{d}" not in SNAPSHOT_EXCLUDES]
                    for path in [Path(current), *(Path(current) / child for child in dirs + files)]:
                        if (
                            path.is_symlink()
                            or not path.resolve().is_relative_to(root)
                            or not (path.is_file() or path.is_dir())
                        ):
                            raise ShieldError(
                                "Mounted Kodi backup contains unsupported links or file types"
                            )
                    path = Path(current)
                    count += 1
                    if count > 100_000:
                        raise ShieldError("Kodi data backup exceeds the entry limit")
                    archive.add(path, arcname=path.relative_to(root).as_posix(), recursive=False)
                    for name in files:
                        path = Path(current) / name
                        count += 1
                        total += path.stat().st_size
                        if count > 100_000 or total > MAX_BACKUP:
                            raise ShieldError("Kodi data backup exceeds the limits")
                        archive.add(
                            path, arcname=path.relative_to(root).as_posix(), recursive=False
                        )
                        if target.stat().st_size > MAX_BACKUP:
                            raise ShieldError("Kodi data archive exceeds 2 GB")
        if target.stat().st_size > MAX_BACKUP:
            raise ShieldError("Kodi data archive exceeds 2 GB")

    def apply(self, preview_id, progress=None):
        report = progress or (lambda *args: None)
        self.ops.writes()
        with self.ops.lock:
            plan = self.plans.get(preview_id)
            if not plan or time.monotonic() - plan["created"] > TTL:
                raise ShieldError("APK preview is missing or expired; preview again")
            self.guard(plan["package"])
            base, items = inspect_set(plan["paths"], self.c)
            if (
                items != plan["items"]
                or self.device() != plan["device"]
                or self.installed(plan["package"]) != plan["installed"]
            ):
                raise ShieldError(
                    "APK, installed app or device changed since preview; preview again"
                )
            if (
                plan["originals"]
                and inspect_set(plan["originals"], self.c)[1] != plan["original_items"]
            ):
                raise ShieldError("Original APK backup changed; preview again")
            backup_id = uuid.uuid4().hex
            backup = private_dir(private_dir(self.c.state) / "apk_backups" / backup_id)
            manifest = {
                "backup_id": backup_id,
                "device": self.c.serial,
                "package": plan["package"],
                "created": time.time(),
                "original_version_code": plan["installed"]["version_code"]
                if plan["installed"]
                else None,
                "candidate_version_code": base["version_code"],
                "original_apks": plan["original_items"],
                "status": "preparing",
                "kodi_data": None,
            }
            remotes = []
            attempted = False
            try:
                report(0, 6, "Saving original APKs to the recovery bundle")
                for index, source in enumerate(plan["originals"]):
                    shutil.copyfile(source, backup / f"{index}.apk")
                    (backup / f"{index}.apk").chmod(0o600)
                    if (
                        sha256_file(backup / f"{index}.apk")
                        != plan["original_items"][index]["sha256"]
                    ):
                        raise ShieldError("Saved original APK checksum failed")
                if plan["package"] == "org.xbmc.kodi" and plan["installed"]:
                    report(1, 6, "Archiving Kodi addons/userdata (tar)")
                    manifest["kodi_data"] = self.kodi_snapshot(backup)
                manifest["status"] = "prepared"
                save_json(backup / "manifest.json", manifest)
                self.guard(plan["package"])
                if self.installed(plan["package"]) != plan["installed"]:
                    raise ShieldError("Installed app changed during backup; preview again")
                report(2, 6, "Pushing APKs to the Shield")
                for index, source in enumerate(plan["paths"]):
                    remote = f"/data/local/tmp/nvidia-mcp-{preview_id}-{index}.apk"
                    remotes.append(remote)
                    attempted = True
                    self.t.adb("push", source, remote, timeout=180)
                    actual = self.t.shell("sha256sum", remote).split()
                    if not actual or actual[0].lower() != plan["items"][index]["sha256"]:
                        raise ShieldError("Transferred APK checksum failed")
                self.guard(plan["package"])
                if self.installed(plan["package"]) != plan["installed"]:
                    raise ShieldError("Installed app changed before installation")
                manifest["status"] = "installing"
                save_json(backup / "manifest.json", manifest)
                report(3, 6, "Installing")
                output = self.install_remote(remotes, items, plan["package"])
                if not re.search(r"^Success\s*$", output, re.M):
                    raise ShieldError(
                        "Android rejected the install; inspect backup/status, no automatic uninstall or retry"
                    )
                report(5, 6, "Verifying installed version and checksums")
                after = self.installed(plan["package"])
                if (
                    not after
                    or after["version_code"] != plan["version_code"]
                    or sorted(after["sha256"]) != sorted(item["sha256"] for item in items)
                ):
                    raise ShieldError("Installed APK version/checksum verification failed")
                manifest["status"] = "verified"
                report(6, 6, "Verified")
                self.ops.audit(
                    "apk_upgrade" if plan["installed"] else "apk_install",
                    plan["package"],
                    backup_id,
                )
                return {
                    "package": plan["package"],
                    "version_code": after["version_code"],
                    "backup_id": backup_id,
                    "status": "verified",
                    "note": "App remains stopped. Verify its startup/functionality separately. Recovery bundle is not a guarantee Android permits a downgrade.",
                }
            except Exception as exc:
                manifest["status"] = (
                    "failed_after_transfer" if attempted else "failed_before_transfer"
                )
                reason = (
                    str(exc)
                    if isinstance(exc, ShieldError)
                    else "Check private storage and bounded device diagnostics"
                )
                raise ShieldError(
                    f"APK change failed: {reason}. Recovery bundle {backup_id}. Inspect current app state before recovery; no automatic retry or uninstall."
                ) from None
            finally:
                save_json(backup / "manifest.json", manifest)
                for remote in remotes:
                    try:
                        self.t.shell("rm", "-f", remote)
                    except ShieldError:
                        pass
                if attempted:
                    self.plans.pop(preview_id, None)
                    shutil.rmtree(plan["directory"], ignore_errors=True)

    def install_remote(self, remotes, items, package):
        if len(remotes) == 1:
            return self.t.shell("pm", "install", "-r", remotes[0], timeout=300, limit=16000)
        result = self.t.shell(
            "pm",
            "install-create",
            "-r",
            "-S",
            str(sum(item["bytes"] for item in items)),
            timeout=30,
            limit=16000,
        )
        match = re.search(r"Success:.*\[(\d+)\]", result)
        if not match:
            raise ShieldError("Android could not create a split APK installation session")
        session = match[1]
        try:
            for index, (remote, item) in enumerate(zip(remotes, items, strict=True)):
                result = self.t.shell(
                    "pm",
                    "install-write",
                    "-S",
                    str(item["bytes"]),
                    session,
                    f"{index}.apk",
                    remote,
                    timeout=180,
                    limit=16000,
                )
                if not re.search(r"^Success", result, re.M):
                    raise ShieldError("Android could not stage an APK split")
            self.guard(package)
            return self.t.shell("pm", "install-commit", session, timeout=300, limit=16000)
        finally:
            try:
                self.t.shell("pm", "install-abandon", session, limit=16000)
            except ShieldError:
                pass

    def status(self, backup_id, verify_checksums=False):
        """Local recovery-bundle state plus the version currently installed on the Shield."""
        if not isinstance(backup_id, str) or not re.fullmatch(r"[0-9a-f]{32}", backup_id):
            raise ShieldError("Invalid APK backup ID")
        folder = self.c.state / "apk_backups" / backup_id
        try:
            manifest = json.loads((folder / "manifest.json").read_text())
        except (OSError, ValueError):
            raise ShieldError(
                "APK backup not found in local private storage", "not_found"
            ) from None
        if not isinstance(manifest, dict) or manifest.get("device") != self.c.serial:
            raise ShieldError("APK backup belongs to a different Shield")
        files = []
        for index, item in enumerate(manifest.get("original_apks") or []):
            path = folder / f"{index}.apk"
            row = {"file": path.name, "present": path.is_file()}
            if row["present"]:
                row["bytes"] = path.stat().st_size
                if verify_checksums:
                    row["sha256_ok"] = sha256_file(path) == item.get("sha256")
            files.append(row)
        kodi = manifest.get("kodi_data")
        if kodi:
            path = folder / "kodi-data.tar"
            kodi = dict(kodi, present=path.is_file())
            if kodi["present"] and verify_checksums:
                kodi["sha256_ok"] = sha256_file(path) == kodi.get("sha256")
        result = {
            key: manifest.get(key)
            for key in (
                "backup_id",
                "package",
                "created",
                "status",
                "original_version_code",
                "candidate_version_code",
            )
        }
        result.update({"original_apks": files, "kodi_data": kodi})
        try:
            installed = self.installed(manifest["package"])
            current = installed["version_code"] if installed else None
            result["installed_version_code"] = current
            result["installed_matches"] = (
                "candidate"
                if current == manifest.get("candidate_version_code")
                else "original"
                if current == manifest.get("original_version_code")
                else "other"
            )
        except (ShieldError, KeyError) as exc:
            result["installed_version_code"] = None
            result["installed_unavailable"] = str(exc) or "Shield unavailable"
        result["recovery"] = (
            "See docs/apk-upgrades.md#manual-recovery; restore is a reviewed manual step."
        )
        return result

    def backups(self):
        rows = []
        root = self.c.state / "apk_backups"
        if root.exists():
            manifests = sorted(
                root.glob("*/manifest.json"), key=lambda path: path.stat().st_mtime, reverse=True
            )[:50]
            for path in manifests:
                try:
                    value = json.loads(path.read_text())
                    if value["device"] == self.c.serial:
                        rows.append(
                            {
                                key: value[key]
                                for key in (
                                    "backup_id",
                                    "package",
                                    "created",
                                    "original_version_code",
                                    "candidate_version_code",
                                    "status",
                                    "kodi_data",
                                )
                            }
                        )
                except (OSError, ValueError, KeyError):
                    continue
        return {
            "backups": rows,
            "scope": "Original APKs and, for Kodi upgrades, addons/userdata; no other Android app-private data. Restore is a reviewed manual recovery step.",
        }
