# Changelog

## 0.4.5 — 2026-10-11 (prerelease)

- Bundle Kodi Manager 0.7.10 (was 0.7.5), built deterministically from the public release commit. Its Shield exit watcher now ends an exit that stalls after Kodi has saved its settings about a minute later, measured on the clock, and never acts once playback starts again. 0.7.6–0.7.9 add all-or-nothing settings saves and restores with rollback, no checkpoints or re-applies during playback, a DNS-rebinding defence (open the dashboard by IP address or `.local` name), masked log lines and the redesigned dashboard. MCP tools are unchanged and still support Kodi Manager 0.4+ (widget-cache tools 0.6+).
- The companion export test also checks that no household-only module is in the bundled ZIP.

## 0.4.4 — 2026-10-11 (prerelease)

- `kodi_lifecycle` stop/restart asks Kodi to quit (`Application.Quit`, so it saves its settings) and waits up to 30 s instead of force-stopping it straight away. Kodi 22.0 RC1 on the Shield can hang at "Stopping all" after quitting with a paused video; the tool then force-stops it only when the current `kodi.log` shows the full save sequence and the TV guard still passes on Android's media sessions and foreground app. Otherwise it reports `exit_hung`, does not start Kodi again and leaves it for the person at the TV. Offline recovery still force-stops directly.
- `allow_offline_recovery` also needs the user's `NVIDIA_MCP_ALLOW_OFFLINE_RECOVERY=1`, like the other model-supplied override flags. A Kodi frozen mid-film still cannot be stopped by the agent, by design (docs/configuration.md).
- `shield_apk_preview` refuses to pull the installed APKs (up to 1 GB over the Shield's network link) while any media is playing or paused, checking again before each APK.
- Tool descriptions say what disruptive tools visibly do on the TV (APK apply replaces the app and can close one opened during the install; ADB connect can show the debugging prompt over playback; settings apply at once; browsing runs add-on code; widget-cache refresh loads the Shield; layout rebuild reloads the skin).
- The `nvidia://configuration` resource reports `offline_recovery`.
- Guard tests use `dumpsys` lines captured from the reference Shield (Android 11, Kodi 22.0 RC1, Projectivy launcher): Kodi's paused session (`state=2`) refuses, Projectivy with Kodi's lingering `state=1` session counts as nobody watching. docs/verification.md lists what was confirmed on the device and what is still pending.

## 0.4.3 — 2026-10-11 (prerelease)

- Resolve the active profile from Kodi's real `profiles.xml` layout (`<id>` child elements; `lastloaded` is a position, not an id). `kodi_set_setting` no longer fails on the master profile, and offline add-on setting edits target the last-loaded profile.
- TV guard: Kodi in front is checked for playback even if the process probe misses it; `allow_offline_recovery` applies only when Kodi HTTP is unreachable/timing out (an authentication or protocol error no longer bypasses the playback check) and is refused while Android's media session reports Kodi playing or paused.
- `kodi_set_setting`, `kodi_set_addon_setting` (via Manager), `kodi_layout_apply` and `kodi_manager_widget_cache_refresh` now use the full TV guard, so they also refuse while another app (Netflix, YouTube...) is in front, not only during Kodi playback.
- `kodi_read` refuses `XBMC.GetInfoLabels` labels that read add-on settings (`Addon.SettingStr(...)` returned raw Real-Debrid/Trakt tokens) or credential-like skin strings and window properties.
- contrib/profile-relaunch: `relaunch.sh` validates pid, profile index and log offset individually; an empty index previously passed and could write `<lastloaded></lastloaded>`. `profile_restart.required()` now also matches Kodi 22.0 RC1 (strictly `22.0-BETA2`/`22.0-RC1`; not RC2, RC10 or final), so following the README on the reference Shield's current build no longer silently uses the unsafe in-process switch. The README documents the early "Finishing the activity" destination write and how to compare a previously deployed copy.
- `kodi_restore_file` reports a missing or damaged local backup as a clean `not_found` error instead of a raw exception that included the private state path.
- `kodi_read` refuses results over 250 KB (for example an unfiltered `Settings.GetSettings`) and points to the paged `kodi_settings` tool. Video-library reads instead shrink the page until it fits and say where to continue.
- TV guard: `interrupt_other_app` no longer skips Kodi's own playback check (it covers only another app in front or playing). Every guarded action now also refuses while any Android media session is playing or paused (background audio). A screensaver (`DreamActivity`) or sleeping display counts as nobody watching instead of "another app"/"unknown"; remote buttons stay refused while the Shield sleeps. Refusal messages name only override flags the tool has.
- `shield_remote`: `play_pause`/`stop` are refused when nothing is playing (they could start a background app's audio) and, with `allow_during_playback`, go to Kodi's player over JSON-RPC when Kodi is playing.
- `kodi_lifecycle restart`: a Kodi that did not stop, or whose state could not be confirmed after force-stop, is reported as such (it previously said "Stop Kodi before editing files").
- `kodi_set_setting` also protects settings that can leave the TV blank, silent or unreadable with no way back from the remote: `videoscreen.*`, `audiooutput.audiodevice`, `audiooutput.passthroughdevice`, `videoplayer.adjustrefreshrate` and `locale.language` (`NVIDIA_MCP_ALLOW_SETTINGS` can allow exact ids).
- `kodi_read` also screens `XBMC.GetInfoBooleans` (`String.StartsWith(Addon.SettingStr(...),a)` was a one-character-at-a-time token oracle) and refuses skin strings/window properties whose names look like account values (`Window(Home).Property(fenlight.debrid.rd)`, `Skin.String(PVRAccessCode)`).
- Redaction decodes percent-encoded and JSON-escaped runs (`url=https%3A%2F%2F…real-debrid.com%2Fd%2F…`, `https:\/\/…`, `access_token%3D…`, `Authorization%3A%20Bearer…`) before matching, so nested stream links, tokens and URL passwords in Kodi logs, plugin paths and patch diffs are withheld, and patches touching them are refused. It also covers `*_api`/`*.client` personal keys (`tmdb_api`, `fanart.tv.client`), `customer_id`, Python `u'…'` values, passwords containing `@` and Netscape cookie files.
- Private file snapshots and APK recovery bundles are tied to the Shield's hardware serial (`ro.serialno`) instead of `host:port`, so a new DHCP address no longer hides earlier backups or refuses their restore. Older manifests and snapshots taken without ADB fall back to `host:port`.
- Kodi Manager errors keep their JSON `code` and a redacted message (`playback_active`, `write_disabled`, `origin_mismatch`, validation errors such as "Expected a whole number") instead of a bare "request failed"; a 403 `write_disabled` is no longer reported as an authentication failure, and only a 404 for a missing route says a newer Kodi Manager is needed (the widget-cache tools previously said so for any error).
- Fix a server-wide hang under mcp 1.x: a tool call that waited for the operations lock while an APK preview/apply was reporting progress blocked the event loop the progress report needed. Every blocking tool now runs in a worker thread.

## 0.4.2 — 2026-10-11 (prerelease)

- Preserve existing file permissions during ADB patches, including executable helper scripts; refuse writes when permissions cannot be read.
- Bundle Kodi Manager 0.7.5 with safe backup retention, shared-file repair and optional row genre filters.

## 0.4.1 — 2026-10-10 (prerelease)

- Bundle Kodi Manager 0.7.4 with widget-cache failure recovery and corrected Android memory-pressure warnings.
- Preserve tested playback crash/decoder checks in the agent playbook.
- Include optional, source-only Kodi 22 beta 2 profile-relaunch helper under contrib/profile-relaunch, with regression tests and a private per-device build script. No automatic installation or account/provider patches.

## 0.4.0 — 2026-10-07 (prerelease)

Breaking for agents: write tools are listed only with `NVIDIA_MCP_ALLOW_WRITES=1`, and overriding the
playback/foreground guard needs `NVIDIA_MCP_ALLOW_INTERRUPT=1`. See docs/configuration.md.

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

- Bundle the public Kodi Manager 0.7.0 release, which fixes an API auth bypass and a restore that could empty an add-on folder (MCP tools support Kodi Manager 0.4+; widget-cache
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
