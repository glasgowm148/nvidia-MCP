# Changelog

## 0.5.11 — 2026-10-15 (prerelease)

- Privacy: key-like words inside one quoted value no longer leak the next value (0.5.10 regression); empty values are not secrets; LWP cookie jars are withheld and `Set-Cookie3` values redacted; quadratic redaction patterns are linear.
- `kodi_browse` uses Kodi Manager's route guard (vendored, byte-identical) for known add-ons, refusing POV/iPlayer action routes such as bookmark erase, sign-out and playback.
- Standard profile with writes (Android) lists the file-backup list/read/restore tools needed to undo setting changes; messages name current tools; an empty or differently-cased `NVIDIA_MCP_TOOL_PROFILE` falls back to standard instead of stopping the server.
- Forwards are dropped only when the connection was refused (not when Kodi is merely down), outside the route lock; Apple TV treats a cut-off Quit reply as sent; any failure after an APK install started is `outcome_unknown`; APK pushes use a size-scaled timeout; file-backup timeouts are plain failures.
- Standard tool discovery starts with 10 everyday Android tools; optional Manager/provider tools follow configured capabilities. `NVIDIA_MCP_TOOL_PROFILE=full` exposes advanced file, Android and APK workflows after a client restart. Profiles do not change permissions.
- Advertised tools use consistent action names, explicit parameter descriptions and clearer settings/file/backup/layout boundaries. Old names remain callable through the same validation and safety guards; the deprecated mixed patch tool is no longer advertised.
- Add synthetic protocol and catalogue regression checks and document the migration. No new delete/uninstall operations or device access during tool discovery.

## 0.5.10 — 2026-10-15 (prerelease)

- adb forwards that disappear (Shield sleep/reboot, adb server restart) are re-established instead of failing every Kodi/Manager call until restart; a request is resent only when the connection was refused before anything was sent. `adb connect` clears cached forwards.
- Large `push_verified` pushes get a size-scaled timeout (and accept one).
- Privacy: quoted values containing spaces and JSON-escaped pairs are fully redacted.
- Empty `NVIDIA_MCP_STATE_DIR`/`LOCALAPPDATA` (and empty or relative `XDG_DATA_HOME`) no longer put private state in the working directory.
- APK recovery bundles of attempts that failed before any transfer are removed, and stale untouched bundles are pruned.
- "Kodi is playing" and similar guards are recorded as refusals with specific kinds; an install timeout after transfer is `outcome_unknown`; a Quit cut off mid-reply counts as sent.
- Add-on ids made of dot segments are rejected; a missing Kodi folder is reported as not found; SDK tool start failures are actionable.
- Kodi Manager add-on settings: rows from raw/settings.db stores are written to the store they were listed from, and the page keeps the add-on's editable/read-only reason.

## 0.5.9 — 2026-10-15 (prerelease)

- Device command status trailers now report the command's own exit code. Previously the status was always 0, so a failed `tar`, `cat` or `head` on the device (including the Kodi data snapshot before an APK install) could pass as success.
- adb and SDK child processes no longer inherit the MCP server's stdin, so a long `adb shell` cannot consume the client's JSON-RPC messages.
- A Kodi that stalls its reply while quitting is treated as "quit sent" (then waited for) instead of "Kodi refused Application.Quit", on Android and Apple TV.
- `kodi_status` stops after the first connection failure by error kind instead of by message text.
- Operation history records `trakt_unavailable` as a refusal (byte-identical with Kodi Manager 0.7.36).

## 0.5.8 — 2026-10-14 (prerelease)

- Operation history retries SQLite busy/locked errors (including table creation on connect and
  reads) for about 2 s, so concurrent writers on Windows no longer drop records. The module stays
  byte-identical with Kodi Manager 0.7.35.

## 0.5.7 — 2026-10-14 (prerelease)

- Add support bundle v1 and bounded private operation history shared with Kodi Manager; carry correlation and backup/undo references across the optional interface.
- Preserve Manager reason codes, refuse automatic write retries after ambiguous replies/timeouts, and keep completed work successful when audit recording fails.
- Add synthetic cross-project and generated-wheel/add-on interface checks. The pinned Manager 0.7.23 ZIP remains unchanged; new diagnostics are capability-negotiated.
- Complete fresh Apple TV installation and CLI environment/path instructions; correct the sample Manager minimum and backup-ownership guidance, and document private token entry when storage is blocked.
- Shorten the project and profile-helper READMEs, add a documentation index, move the generated tool catalogue to `docs/tools.md`, and correct outdated setup/build examples. Runtime and bundled companion are unchanged.

## 0.5.6 — 2026-10-12 (prerelease)

- Fix the opt-in Android profile handoff's automatic reopen race. Arming no longer starts a ten-second countdown while Kodi is quitting. The child waits for `Application stopped`, obtains a versioned `READY` acknowledgment, and schedules one reopen two seconds later before ending the old process.
- Helper APK 1.1 / versionCode 2, client DEX and shell script must be rebuilt and deployed together with the existing private token/signing identity. An outdated APK refuses before Kodi quits. Readiness expires after two minutes and is consumed once; cancel clears it and any pending launch. Unexpected process death before the saved shutdown checkpoint still requires manual recovery.
- The actual Java readiness policy is tested for short/slow shutdowns, expiration, duplicate readiness, permission revocation and cancellation. A private build with unchanged signing key/token passed automatic Adults → Kids → Adults switches on the reference Shield / Kodi 22 RC1 (29.1 / 23.5 seconds), returning to Home and verifying both profiles' channel counts.

## 0.5.5 — 2026-10-12 (prerelease)

- Bound HTTP exchanges to 60 seconds with a socket deadline, including dripping headers and success/error bodies. Disable keepalive reuse so a cancelled timer cannot affect another request; retain the 20-second read/3-second connect timeouts and byte bounds. Never retry mutations automatically.
- Classify answered-but-stalled responses as `response_timeout`; partial or malformed replies stay distinct from offline services. Apple TV launch/restart cannot use these failures as offline permission. Preserve the known no-reply disconnect case.
- Refuse successful Manager envelopes missing `data`, normalize deeply invalid JSON and avoid oversized error-body copies.
- Bundle Manager 0.7.23 with delayed access/profile rechecks, retired-generation refusal and operation-scoped backup roots. Add real loopback header-deadline and synthetic stream/profile regressions. No live TV changes; physical Apple TV validation remains pending.

## 0.5.4 — 2026-10-12 (prerelease)

- Bundle Manager 0.7.22: failed self-restore rollback preserves live access/identity, and aliased tvOS backup paths keep XML in virtual storage.
- Clarify older alias-affected snapshot refusal and fresh-backup guidance. No MCP tool/backend contract changes; retain private pairing traces, Android defaults and reviewed layout gates. Physical Apple TV validation remains pending.

## 0.5.3 — 2026-10-12 (prerelease)

- Silence pyatv's PIN/key logs throughout private pairing, including when debug logging is enabled. Restore prior logger levels after success, cancellation or failure; retain unrelated application logs.
- Bundle Manager 0.7.21 with nested-profile read confinement and Kodi's physical Siri Remote XML exception. Add regressions for both successful and failed noisy pairing.
- Preserve Android/Shield defaults, tool contracts and reviewed layout gates. Physical Apple TV validation remains pending.

## 0.5.2 — 2026-10-12 (prerelease)

- Read private pairing PINs on the calling terminal thread so Ctrl-C/EOF can restore terminal input and close pairing; avoid executor workers stuck on stdin during shutdown.

- Bundle Manager 0.7.19 with bounded portable path traversal and Windows short-path alias handling. Retain the Apple TV playback/launch/ownership/shutdown fixes from 0.5.1.
- Verify the exact public ZIP and platform tool counts in the released wheel. Physical Apple TV validation remains pending; existing Shield configuration is unchanged.

## 0.5.1 — 2026-10-12 (prerelease)

- Preserve unknown MRP playback state and metadata-less paused players instead of accepting pyatv's synthetic idle. Use a bounded read-only adapter for pinned pyatv 0.16; missing internals block changes.
- Explicit launch opt-ins no longer bypass Manager authentication, malformed state or changed device identity. Recheck both paired protocols even with a cached connection.
- Bind file requests/responses to captured Manager identity/profile; require Manager 0.7.17+ for those reads and explain older-server refusal.
- Close the paired event loop without racing new work; cancel/await pending tasks and reject operations on a closed transport.
- Bundle audited Manager 0.7.18, clarify stricter guard/recovery limits, and add real-SDK and concurrent-shutdown regressions. Physical Apple TV validation remains pending; no household TV changes.

## 0.5.0 — 2026-10-12 (prerelease)

- Add explicit experimental Apple TV backend with optional public pyatv 0.16 dependency.
  Keep Android/Shield defaults, existing names and stdio/read-only behavior. Omit Android-only
  tools on tvOS; expose paired installed-app listing, Home, power and graceful launch/quit/restart.
- Pair Companion/AirPlay through private CLI PIN input, scoped to one explicit unicast host.
  Save credentials atomically/private, require both protocols, reject changed device identity,
  serialize SDK actions and establish a fresh connection before playback/power guards.
- Reuse Kodi/Manager skin previews, source/revision/TTL checks, settings and widget workflows.
  Bind tvOS previews to Manager identity/profile path; unknown media/focus blocks changes.
  Native Kodi focus comes from Manager, not playing-app metadata. No force-stop or offline writes.
- Add Manager configuration backup/restore tools and backup listing through Manager inspect
  on both platforms. Apple TV uses bounded checksum-checked VFS reads and private per-file
  snapshots. Export `AppleTV` library facade alongside unchanged AndroidTV/Shield APIs.
- Bundle public Manager 0.7.16; explain setup, parity, disposable tvOS backup/cache limits and
  physical-test requirements. Synthetic tests and SDK contract checks only; no live TV mutations.

## 0.4.10 — 2026-10-12 (prerelease)

- Refresh hardware identity on each operation; reject placeholder serials and refuse to downgrade
  hardware-bound backup ownership to an IP address when identity is unavailable. Read file backups
  and their metadata with size limits before restore.
- Bind APK previews to a verified hardware serial, checking it through backup, transfer, install,
  split-session commit and cleanup. A replacement TV at the same address cannot inherit a preview
  or receive its cleanup commands. Devices without a stable serial retain read-only diagnostics.
- Write recovery phases atomically. A final metadata write failure still consumes transferred
  previews and attempts cleanup on the matching TV; report the recovery bundle and uncertain app
  state without exposing private storage paths. Preserve specific failure codes.
- Reject malformed active-media flags and unreadable resumed-app entries rather than treating
  them as proof the TV is idle. Bundle public Kodi Manager 0.7.15 with its request/restore fixes.

## 0.4.9 — 2026-10-12 (prerelease)

- Extend device scope to Android TV / Google TV and Android-based Fire OS. Keep existing
  package/tool names; add `AndroidTV` library alias and `ANDROID_TV_HOST` / `ANDROID_TV_ADB_PORT`
  configuration names, rejecting conflicting legacy aliases.
- Recognize Amazon’s home launcher and legacy focused-activity dumps without overriding modern
  resumed state. Keep paused/background media guards; unreadable active media blocks changes.
- Fall back to bounded SDK-appropriate process listings when older Android lacks `pidof`;
  malformed/unknown process state cannot masquerade as a stopped app.
- Add `--pair-adb PAIRING_PORT`: pair only the configured host using a six-digit secret via
  hidden terminal input/private stdin, never command arguments or echoed ADB errors. Separate
  pairing from connection readiness; no pairing tool is exposed through MCP.
- Document vendor debugging menus, dynamic ports, storage/ABI limits, synthetic versus physical
  testing, and unsupported Vega OS Firesticks. Bundle public Kodi Manager 0.7.14.

## 0.4.8 — 2026-10-12 (prerelease)

- Fix `kodi_addons`: `type` is returned automatically by Kodi, but is not a valid requested
  property. Listing add-ons previously failed with `Invalid params` on Kodi 22.
- `KODI_HTTP_ROUTE=forward` or `auto` now makes authorized ADB forwarding available to MCP, for
  host applications whose direct LAN HTTP is blocked. Kodi and Manager select their routes
  independently; auth/protocol errors never trigger fallback. Default remains direct.
- Close transports in a `finally` block, including CLI/server failures, to remove owned forwards.
- Report blocked or incompatible ADB executables as actionable readiness failures rather than
  crashing the connection check; Kodi HTTP is still probed independently.
- Bundle the exact public Kodi Manager 0.7.13 release, including provider-route fixes, improved log
  health and dashboard request/sign-in fixes. Household patches remain excluded.
- Keep future companion versions in packages: the ZIP ignore exception follows the companion
  filename pattern, and wheel/sdist inspection verifies one manifest plus its exact ZIP and hash.
  Release checksums now include the separately downloadable companion ZIP too.
- Explain client requirements, separate credentials, profile changes, manual updates, optional APK
  tooling, connection failures and capabilities unavailable on other skins/platforms.

## 0.4.7 — 2026-10-11 (prerelease)

- `kodi_lifecycle stop`/`restart` and `Shield.quit_kodi` follow the Kodi processes that were running when `Application.Quit` was sent. On the household Shield Kodi exited cleanly after a quit and Android started a new, empty `org.xbmc.kodi` process 2 s later; the package-wide `pidof` mistook it for the old Kodi and reported `exit_hung`. Once the quitting Kodi has gone, such a process is force-stopped while Kodi is not the app in front (`respawned_process_stopped` in the result); a Kodi that is on screen again is left running (`restarted`), as is one whose foreground app cannot be read (`respawned`). The single `pidof` probe now returns process IDs.

## 0.4.6 — 2026-10-11 (prerelease)

- Library API: `nvidia_mcp.Shield(config)` lets other tools on the computer reuse the server's device code instead of duplicating it: `adb`, `shell`, `rpc`, `viewing_state()` (verdict idle/playing/paused/other_app/screensaver/asleep/unknown from the guard's own signals), `kodi_alive()`, `quit_kodi(wait)` and `start_kodi(wait)` (the same guard and quit-then-force-stop rule as `kodi_lifecycle`), `pull`, `push_verified` (temporary file, on-device SHA-256 check, `mv`, check again), `memory()` and `process_deaths()`. Kodi JSON-RPC can go through an `adb forward` (`kodi_route="forward"` or `"auto"`) for processes the OS blocks from the LAN, such as macOS Local Network permission. Documented with a semver promise in docs/library.md; exported from `nvidia_mcp`. MCP tools are unchanged and always use direct HTTP.
- `shield_status` health now includes `SwapTotal`/`SwapFree` in `memory_kb` (a full swap with low MemAvailable is when Android's low-memory killer can end Kodi behind the screensaver).
- ADB file patches and `push_verified` share one temporary-file-then-move helper.
- Replay tests from the reference Shield's own output (tests/fixtures/real, anonymised): seven scenarios (idle on Kodi's home, paused on the OSD, Android screensaver, Projectivy in front, the 2026-10-11 hung exits, a low-memory kill behind the screensaver, Netflix paused) drive every guarded action, clean and hung `kodi_lifecycle` exits (force-stop only with proof of saved settings and a passing guard; `exit_hung` otherwise), the diagnostics tools and the library through a fake ADB/HTTP boundary, so the real parsers run on real dumps.

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
