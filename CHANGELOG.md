# Changelog

## Unreleased

### Security

- **Redaction** now covers segment-style setting ids (`trakt.refresh`, `rd.refresh`, `rd.auth`,
  `*.pin`, `*_user`...), credential XML elements (`<user>`, `<pass>`, `<lockcode>`...), JSON and
  Python-style quoted pairs in logs, `Authorization`/`Cookie` headers, URL userinfo for any scheme
  and secret query parameters. A fixture corpus of realistic fake Fen/POV/Trakt/Real-Debrid/Torbox
  settings, MySQL `advancedsettings.xml`, `profiles.xml`, `passwords.xml`, `sources.xml`, `kodi.log`
  and logcat lines guards this.
- **One TV guard** (`guard_tv`) for remote buttons, Kodi lifecycle, skin-menu rebuild, plugin
  browsing and APK installs: Kodi playback state, the foreground app against one shared launcher
  set (`NVIDIA_MCP_EXTRA_LAUNCHERS` extends it) and running state. `shield_remote` no longer sends
  Home/Back/Stop to Netflix, YouTube or SmartTube. The model-supplied `allow_during_playback` and
  `interrupt_other_app` flags now also need `NVIDIA_MCP_ALLOW_INTERRUPT=1`.
- `kodi_set_setting` refuses security/service settings (`services.*`, `masterlock.*`, `system.*`,
  `debug.*` except `debug.showloginfo`, `pvrparental.*`, HTTP proxy, `addons.unknownsources`,
  `addons.updatemode`, `lookandfeel.skin`). `NVIDIA_MCP_ALLOW_SETTINGS` allows exact ids.
- `kodi_browse` checks plugin path segments and every query parameter for action words (play,
  sign/out, maintenance, settings, search/input, ...), not only `mode`/`action` values.
- New-app APK signer trust comes only from `NVIDIA_MCP_TRUSTED_SIGNERS` /
  `NVIDIA_MCP_TRUSTED_SIGNERS_FILE`; the `trusted_signers` argument can only narrow it.
- `kodi_patch_*` refuses edits touching credential settings/values and add-on `.py` files.
- Write and disruptive tools are registered only when `NVIDIA_MCP_ALLOW_WRITES=1` (23 tools are
  listed read-only, 34 with writes).

### Added

- `kodi_patch_preview` (read-only, redacted unified diff) and `kodi_patch_apply`;
  `kodi_patch_file` remains as a deprecated alias.
- `shield_apk_status(backup_id)`; APK preview/apply report per-stage progress to MCP clients.
- `kodi_manager_widget_cache` and write-gated `kodi_manager_widget_cache_refresh` (Kodi Manager 0.6+).
- Every tool has a title and read-only/destructive/idempotent/open-world hints; `kodi_read.method` is
  an enum of the allowlist, patch edits and layout plans have typed schemas.
- Start-up pruning of old local backups and stale APK previews (`NVIDIA_MCP_RETENTION_DAYS`,
  `NVIDIA_MCP_KEEP_FILE_BACKUPS`, `NVIDIA_MCP_KEEP_APK_BACKUPS`).
- Generated README tool reference (`scripts/gen_tool_docs.py`), tag-driven release workflow, CI axis
  for the oldest (1.28) and latest mcp, `nvidia-mcp --version`.
- Manual APK recovery steps in `docs/apk-upgrades.md#manual-recovery`.

### Changed

- Bundle the public Kodi Manager 0.6.2 release (MCP tools support Kodi Manager 0.4+; widget-cache
  tools need 0.6+).
- `exec-out` reads (`head`, `tail`, `cat`, `tar`) check the remote exit status, so a missing file is
  an error instead of `head: ... No such file` content and a failed tar cannot pass as a backup.
- Kodi JSON-RPC errors keep Kodi's (redacted, bounded) message and data; error text shows the error
  kind; missing result fields give actionable errors. `VideoLibrary.*` reads default to 50 items
  (maximum 500).
- `shield_apk_preview` is annotated `readOnlyHint=false` (it downloads up to 1 GB locally).
- The package version has a single source (`src/nvidia_mcp/__init__.py`).

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
