# Changelog

## 0.3.2 — 2026-10-06 (prerelease)

- Refresh-rate settings such as `videoplayer.adjustrefreshrate` are no longer treated as credentials.
  They can be read, searched and changed. Refresh tokens are still redacted.
- `kodi_lifecycle start` works without `allow_offline_recovery` when Kodi is stopped. Restart, stop,
  and start while Kodi is running still require known-idle playback.
- The Kodi data snapshot taken before a Kodi APK upgrade skips regenerable caches
  (`userdata/Thumbnails`, `addons/packages`, `addons/temp`), which often exceeded the 2 GB limit.
- Non-UTF-8 Kodi files return a clear error instead of a raw decoding failure.
- `kodi_backups` skips a corrupt snapshot manifest instead of failing the whole listing.
- Works with mcp 1.x and 2.x (`mcp>=1.28,<3`). Error guidance is shown to clients on mcp 2.x.
- Bundle Kodi Manager 0.4.2.

## 0.3.1 — 2026-10-04 (prerelease)

- Bundle Kodi Manager 0.4.1 with the fix for backups/restore made within the same second.
- Add clean-wheel MCP stdio/export smoke checks, archive/checksum tooling, dependency/secret checks,
  compatibility/recovery guidance and issue templates.

## 0.3.0 — 2026-10-04 (prerelease)

- Separate ADB, Kodi HTTP and optional Manager readiness diagnostics.
- Explicit local APK/split previews, official SDK signature/compatibility checks, guarded installation
  and retained original APK/Kodi-data recovery bundles.
- Uptime and Android thermal-status diagnostics. Actual live installation/recovery remains unverified.

## 0.2.0 — 2026-10-04 (prerelease)

- Pinned optional Kodi Manager 0.4.0 companion ZIP, verified offline export and companion setup guide.

## 0.1.0 — 2026-10-04 (prerelease)

- Local stdio Shield/Kodi inspection, redacted file/log access, guarded settings/patch/recovery tools
  and version-bound optional Manager layout workflows. TV-first and agent-computer onboarding.
