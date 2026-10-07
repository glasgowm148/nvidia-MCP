"""Prune old private local state on server start: file snapshots, APK bundles, stale previews.

Configured by NVIDIA_MCP_RETENTION_DAYS (0 disables pruning of backups),
NVIDIA_MCP_KEEP_FILE_BACKUPS and NVIDIA_MCP_KEEP_APK_BACKUPS. The newest N of each kind are
always kept regardless of age, and APK bundles whose install did not verify are never pruned.
"""

import json
import shutil
import time

PREVIEW_TTL = 600


def _age_days(path, now):
    return (now - path.stat().st_mtime) / 86400


def prune_state(config, now=None):
    now = time.time() if now is None else now
    removed = {"file_backups": 0, "apk_backups": 0, "apk_previews": 0}
    state = config.state
    if not state.is_dir():
        return removed
    previews = state / "apk_previews"
    if previews.is_dir():
        # Preview plans live in memory, so a preview directory outlives its server process.
        for folder in previews.iterdir():
            try:
                if folder.is_dir() and now - folder.stat().st_mtime > PREVIEW_TTL:
                    shutil.rmtree(folder, ignore_errors=True)
                    removed["apk_previews"] += 1
            except OSError:
                continue
    days = config.retention_days
    if days <= 0:
        return removed
    backups = state / "backups"
    if backups.is_dir():
        manifests = sorted(backups.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for manifest in manifests[config.keep_file_backups :]:
            try:
                if _age_days(manifest, now) > days:
                    manifest.with_suffix(".bin").unlink(missing_ok=True)
                    manifest.unlink(missing_ok=True)
                    removed["file_backups"] += 1
            except OSError:
                continue
    bundles = state / "apk_backups"
    if bundles.is_dir():
        verified = []
        for manifest in bundles.glob("*/manifest.json"):
            try:
                if json.loads(manifest.read_text()).get("status") == "verified":
                    verified.append(manifest)
            except (OSError, ValueError, AttributeError):
                continue  # Unknown state: keep it for manual review.
        verified.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        for manifest in verified[config.keep_apk_backups :]:
            try:
                if _age_days(manifest, now) > days:
                    shutil.rmtree(manifest.parent, ignore_errors=True)
                    removed["apk_backups"] += 1
            except OSError:
                continue
    return removed
