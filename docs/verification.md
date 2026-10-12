# Verification

## 0.5.4 backup audit (2026-10-12)

Manager 0.7.22 regressions reproduce failed self-restore rollback after a concurrent access
change on POSIX and virtual storage, for both add-on and checkpoint restore. Aliased backup
paths keep XML in virtual storage across backup/restore/undo. Missing virtual backup keys
refuse physical shadows before any live change. No live TV mutations or physical Apple TV
validation. Existing pairing, guard and tool-count tests remain required; inspect actual CI
for the full Windows matrix. Local checks passed 784 Manager Python tests (one environment
skip), 98 UI tests and 608 MCP tests plus 5 subtests with the optional SDK installed.
Release checks verify the exact public Manager ZIP and isolated wheel behavior.

## 0.5.3 additional audit pass (2026-10-12)

Synthetic regressions cover private pairing with explicit SDK debug levels, new SDK loggers,
leading-zero PINs and failed authentication. Installed pyatv 0.16.1 Companion/AirPlay
PIN methods also verify that the actual SDK debug trace is hidden without losing PIN padding. PIN/key traces are suppressed; unrelated logs and
previous SDK logger levels survive. Manager 0.7.21 tests configured nested-profile boundaries and
Siri Remote XML physical read/write/backup/delete routing, including aliased master userdata
paths for virtual profile configuration. Release checks verify the exact public
Manager ZIP embedded in the MCP wheel. Physical Apple TV validation remains pending; no live TV
mutations were performed. Local validation passed 608 MCP tests plus 5 subtests with the
optional SDK installed; Manager passed 778 Python tests (one environment skip), 98 UI tests,
Python 3.8 types and deterministic ZIP/isolated wheel recovery checks. Inspect actual release
CI before claiming a complete Windows matrix.

## 0.5.2 final audit follow-up (2026-10-12)

Private PIN tests verify calling-thread input and Ctrl-C cleanup without saving credentials. The full MCP suite passes 604 tests plus 5 subtests with the optional SDK installed.

Manager 0.7.19 bounds parent traversal, recognizes Windows short-path/case aliases and confines nonstandard profiles against the canonical master path. Local Manager validation: 773 Python tests passed (one environment skip), 98 UI tests, Python 3.8 types and deterministic ZIP/wheel recovery checks. The companion/export and platform tool contracts remain unchanged; this package pins the exact released Manager ZIP. GitHub runner jobs stalled during this audit despite local validation of the exact CI command; inspect this tag's actual checks before claiming the remote matrix passed.

## 0.5.1 Apple TV follow-up audit (2026-10-12)

New regressions use the installed pyatv 0.16 MRP state manager and facade: an uninitialized or
metadata-less paused player reports public `Idle`, and this backend now preserves `unknown`/`paused`.
Synthetic tests cover launch authentication/device failures, response ownership despite returning
profile state, cached partial pairing and shutdown during pending work.

Manager 0.7.18 verifies VFS existence/stat/read lengths, refuses unsafe virtual writes/missing-directory snapshots,
confines nonstandard profiles and keeps live identity/access untouched during self-restore.
Locally, 601 MCP Python tests plus 5 subtests passed with the optional SDK installed. Manager passed
769 Python tests (one environment skip) and 98 UI tests; Python 3.8 types, wheel recovery/stdio/export
and deterministic release checks remain required. No hardware or live TV mutations were performed.

## 0.5.0 experimental Apple TV support (2026-10-12)

Synthetic tests cover private Companion/AirPlay pairing, explicit-host-only discovery, partial
pairing refusal, cancellation/secret-safe SDK failures, fresh paired-state connections, device/profile
changes, file checksum and size validation, immutable layout previews, backup/restore routes,
launch preflight, interruption opt-ins and absence of Android-only tools. Installed pyatv 0.16 API
checks run without network access; CI installs the optional dependency in a dedicated job.

Android retains 23 read-only tools and has 36 with writes; Apple TV has 17/27. New shared backup
write tools are included in the foreground/playback guard matrix. Existing Shield replay, APK,
stdio, progress/concurrency and privacy suites remain required. Ruff, generated tool docs,
clean-wheel stdio/export and archive/checksum checks cover both releases.

Manager 0.7.16 adds virtual XML write/readback/rollback, backup/restore/undo, identity preservation,
widget auto-routing, pipeline discovery, active-profile confinement, authenticated bounded file
reads and native-active action/background-work refusal. Its full Python suite, 98 Node tests,
Python 3.8 types, fresh-wheel recovery and deterministic ZIP checks pass.

**No physical Apple TV or live TV mutations were tested.** Native UIKit access, actual Companion/
AirPlay reporting, signing renewal, background suspension, tvOS purging and real skin/helper
performance require device validation. Unknown native focus blocks writes. The household Shield
configuration and installed Manager were not replaced. Older live evidence below retains its scope.

## 0.4.10 deeper reliability audit (2026-10-12)

Locally, 551 Python tests plus 5 subtests passed. New synthetic regressions cover hardware-ID
loss/change and placeholder serials, bounded file-backup reads, APK plans on a replacement TV,
device changes during split-session staging/commit/cleanup, recovery metadata disk failures,
atomic phase preservation, malformed resumed-app entries and active-media flags. The existing
MCP progress/concurrent-tool scenario still completes with the stricter APK identity contract.
Ruff and generated tool documentation checks passed.

Manager 0.7.15 passed 740 Python tests (one environment skip), 98 Node UI tests and Python 3.8
static typing. New cases exercise truncated/dripping request bodies, body-free action handlers,
damaged/undeclared checkpoint folders, corrupt restore manifests, malformed HTTP responses and
bearer-token echoes. Fresh-wheel backup/restore/undo and identical add-on ZIP rebuilds passed.

MCP's clean-wheel stdio/export and release archives are checked separately, including the exact
Manager 0.7.15 companion and its checksum. No live TV mutations or physical Firestick/Google TV
tests were performed; older live evidence below retains its stated version/device scope.

## 0.4.9 Android TV / Fire OS support (2026-10-12)

Locally, 532 Python tests plus 5 subtests passed. New synthetic cases cover Amazon’s home
launcher, legacy/modern foreground precedence, paused/background media, unreadable active
media, SDK-appropriate process fallback, alias conflicts and pairing secrets via stdin. Pairing
failure/timeout output cannot expose the code; CLI setup does not initialize MCP/write mode.
Ruff, real stdio discovery and a clean-wheel install/export passed. Archive inspection verifies
the pinned companion and checksum; public Manager 0.7.14 bytes match the bundled ZIP.

Manager’s separate checks passed: 728 Python tests (one environment skip), 98 Node UI tests,
Python 3.8 static types, fresh-wheel backup/restore/undo and deterministic add-on ZIP builds.

No physical Firestick, Google TV box or code-pairing session was tested. Firmware storage/APK
restrictions and small-device performance remain unverified. Vega OS is unsupported. Existing
live evidence below applies to the reference Shield and the stated older source versions.

## 0.4.8 public onboarding audit (2026-10-12)

Locally, 498 Python tests plus 5 subtests passed, including JSON-RPC add-on field validation,
concurrent Kodi/Manager forwarding, auth/protocol failures that must not trigger fallback, server
cleanup, real stdio tool discovery and missing/mismatched packaged companion rejection. Ruff,
fresh-wheel installation/export and wheel/source archive checks passed for the release.

Live read-only checks used the 0.4.8 source on the reference Shield (Android 11, Kodi 22.0 RC1),
with writes and plugin browsing off. Authorization, viewing-state inspection, version and active
profile resolution worked. `kodi_addons` returned 104 add-ons and 100 with `enabled_only=True`.
Kodi HTTP and the installed household Manager 0.7.12 both reported ready through separate ADB
forwards; both forwards were removed on close. Tokens/profile data stayed private.

The public Manager 0.7.13 bundle is checked separately; it was not installed on the TV for this
audit. New mutations, APK installs, other devices and client-specific setup remain unverified live.

## 0.4.6 replay fixtures (offline)

The day's `adb` output from the reference Shield (Android 11, Kodi 22.0 RC1, Projectivy as the
home app after the Google TV launcher was disabled) is now a set of anonymised replay scenarios in
`tests/fixtures/real` (provenance in `tests/replay.py`). They newly cover, from real lines:

- the Backdrop screensaver in front (`com.google.android.backdrop/android.service.dreams.DreamActivity`,
  `mWakefulness=Dreaming`): recognised as a screensaver, so nobody counts as watching;
- Kodi's two hung exits (14:07 after playback, 17:45 idle), and a clean exit on the same Shield
  the day before (Kodi 22 beta 2) that continues past "Stopping all" to "Application stopped";
- Kodi ended by Android's low-memory killer (`am_proc_died [0,10785,org.xbmc.kodi,200,2]`) about
  2 s after the screensaver pushed it to the background, with MemAvailable 467 MB and swap 96% used;
  Kodi's PSS after an hour of a film was 1.5 GB, almost all native heap (2026-10-10 capture);
- `Application.GetProperties` reporting `tag: releasecandidate`, `tagversion: "1"` (a string).

Automated: 470 tests and 5 shell subtests pass; no Shield or Kodi was contacted. Still pending on
the device: the items listed for 0.4.4 below, apart from screensaver recognition, which the
2026-10-11 dumps now confirm. The sleeping-display path (`isSleeping=true`, `mWakefulness=Asleep`)
remains unobserved.

## 0.4.4 on the reference Shield (2026-10-11)

Reference Shield today: Android 11, Kodi 22.0 RC1 (`22.0-RC1 (21.90.901)`), Kodi Manager 0.7.6
(household build), skin.bingie 2.0.2.2, Projectivy launcher. The observations below are `adb`
output captured on that Shield during the day's deployment, not calls through this server's tools.
Their exact lines are now test fixtures (`tests/test_live_fixtures.py`, `tests/test_lifecycle_exit.py`).

Confirmed against the real device output:

- `dumpsys media_session` parsing. Kodi with a film paused reported `package=org.xbmc.kodi`,
  `active=true`, `state=PlaybackState {state=2, position=2971175, ..., speed=0.0, ...,
  actions=-1, ...}`: the guard reads this as "Kodi paused" and refuses. After Kodi stopped, its
  session stayed listed as active with `state=1` (STOPPED): the guard reads this as idle, so a
  lingering session does not block anything.
- Foreground parsing of `mResumedActivity` lines on Android 11, for Projectivy
  (`com.spocky.projengmenu/.ui.home.MainActivity`, a built-in launcher: nobody watching) and Kodi
  (`org.xbmc.kodi/.Main`).
- `dumpsys power` while in use: `mWakefulness=Awake`, `Display Power: state=ON`. Nothing asleep was
  observed, so the sleeping-display path is still unconfirmed (below).
- Kodi's exit hang. Quitting Kodi with a paused video, `kodi.log` showed "Stopping the
  application...", "Saving settings", "Saving skin settings", "Stopping all" and then nothing for
  more than 90 s; a force-stop was needed. `kodi_lifecycle` now handles exactly this sequence.
- The contrib profile-relaunch `relaunch.sh` (sha256 `d24b0bbc…`, with per-number validation) was
  deployed into the household's profile-switch add-on; an Adults→Kids→Adults switch took about
  18 s each way and Kodi's PID changed.

Automated: 378 tests and 5 shell subtests pass with synthetic fixtures on mcp 2.3, 1.30 and 1.28;
ruff, the README tool table check, the package build and release-archive inspection pass.

Still to confirm on the Shield, read-only first:

- `kodi_lifecycle stop` through the server: that `Application.Quit` gets an answer or a dropped
  connection (both are treated as sent), that a normal exit finishes within the 30 s wait, and how
  a hung exit is reported (`exit_hung`, or a force-stop with the `kodi.log` evidence in the result);
- whether Kodi's media session during a hung exit is already at `state=1` (needed for the
  force-stop) or still at `state=2` (then the tool leaves Kodi for the person at the TV);
- the screensaver (`DreamActivity`) and sleeping-display (`isSleeping=true` / `mSleeping=true`)
  recognition (fails closed with `foreground_unknown` if the dump differs);
- `getprop ro.serialno` for backup ownership (otherwise backups fall back to `host:port`);
- profile resolution against the household's own `profiles.xml` (`kodi_status`,
  `kodi_addon_settings`);
- Kodi Manager 0.7.6 error codes as surfaced by `kodi_manager_inspect` / widget-cache tools;
- `shield_apk_preview` refusing while something plays (only synthetic so far), and any APK
  install or recovery.

## 0.4.3 guard, profile and privacy fixes (offline only)

353 automated tests and 5 shell subtests pass locally with synthetic fixtures on mcp 1.28, 1.30
and 2.3; ruff, the README tool table check and release-archive inspection pass. No Shield or Kodi
was contacted. A subprocess regression test reproduces the mcp 1.x hang (a tool waiting for the
operations lock while an APK preview reports progress) and now finishes.

Not yet confirmed on a live Shield, all read-only to check before using writes:

- the `dumpsys media_session` parsing used by every guard (it fails closed if the dump is
  unreadable);
- the screensaver (`DreamActivity`) and sleeping-display (`isSleeping=true` / `mSleeping=true` in
  `dumpsys activity activities`) recognition, which lets settings, layout and lifecycle tools run
  while the Shield is idle in standby; if the dump differs, they fail closed with
  `foreground_unknown` as before;
- `getprop ro.serialno` for backup ownership (without it, backups fall back to `host:port`);
- profile resolution against the household's own `profiles.xml` (`kodi_status`,
  `kodi_addon_settings`);
- Kodi Manager 0.7.x error codes as surfaced by `kodi_manager_inspect` / widget-cache tools.

## 0.3.1 release preparation

70 MCP tests pass locally, plus clean-wheel stdio/tool/resource/prompt and disabled-write checks
against a synthetic local HTTP service. The pinned Manager 0.7.5 also preserves completed backups on failure and fixes shared-file repair;
its 158 Python and 47 UI tests include restore/undo and distinct add-on/stack/pipeline checkpoints.

Git-history and published-archive secret scans found no matches. Resolved fresh-wheel dependencies
passed pip-audit; archive inspection/checksums and explicit household-marker checks passed. These
checks do not guarantee that every possible sensitive value or vulnerability can be detected.
CI now checks dependencies/history, current-version wheel installation and release archives. Read
the release's actual Linux/Windows CI results. Live Shield installation/recovery remains pending;
see [compatibility](compatibility.md) and [contributing/release checks](../CONTRIBUTING.md).

## 0.3.0 APK upgrades and connection diagnostics

70 automated tests pass locally. New coverage includes independent ADB authorization/Kodi HTTP
readiness, sanitized failure categories, unknown foreground refusal, SDK metadata compatibility,
signer mismatch, explicit trust for new apps, staged/source tampering, stale/expired previews,
split APK sessions and abandonment, failed install/readback, corrupt transfers, viewing starting
during transfer, bounded/time-limited downloads, and private Kodi data archives through ADB/mounted
storage with corrupt archive and symlink refusal. Without write mode, real MCP stdio discovery
lists 23 tools and no write tools; with `NVIDIA_MCP_ALLOW_WRITES=1` it lists 34. The suite runs against
mcp 1.28 and the latest mcp 2.x.

Official Android Build Tools 36.0.0 were downloaded locally from Google's SDK repository and checked
against its published archive checksum. Using its `aapt2` and `apksigner.jar` with Java 21, local
inspection of official Kodi 21.3 and 22 beta 2 arm64 APKs confirmed package, versionCode, min SDK,
CPU architecture and matching verified signer fingerprints. A one-byte-modified Kodi APK was rejected.
SDK files and APKs are private development artifacts, not bundled in the distribution.

No Shield commands, app installation, restart or TV navigation were used to validate this release.
Actual Android installation and recovery remain unverified on a live Shield through these new tools;
the installer/session and backup workflows are tested with synthetic device responses. APK bundles
are rollback preparation, not a guarantee of downgrade permission or automatic recovery. Read actual
CI status before claiming Linux/Windows verification for this release.

## 0.2.0 optional companion bundle

38 MCP tests pass locally, including exporting the verified Manager ZIP without device configuration,
refusing overwrite of an unrelated file, and refusing a tampered bundle. Python wheel and source
distribution include the same companion ZIP and manifest. No TV changes were made for this extraction.

The separate Kodi Manager 0.4.0 library/companion passes 155 Python and 47 Node UI tests. Tests cover
existing layout/catalogue/schema behavior and the new client, redirect refusal, read-only defaults,
mutation gates, absent third-party patch payloads, backup path traversal and deterministic packaging.
The original 0.3.9 live integration remains the runtime evidence below; 0.4.0 is an offline-tested
portable extraction, not a newly live-tested TV deployment.

## Initial 0.1.0 release

35 automated tests passed locally on macOS / Python 3.14:

- MCP SDK 1.30.0: real stdio subprocess initialization, 25-tool discovery, structured tool output,
  resource/prompt discovery and explicit refusal of disabled writes/unrestricted RPC.
- Local HTTP server and mock HTTP transport: request/auth plumbing, redirects refused, response bounds,
  and error bodies withheld.
- Synthetic Kodi storage: exact patch preview/application, conflicting hashes/anchors, invalid syntax,
  preserved backups, integrity checks, restore/undo, and symlink/traversal refusal.
- Fake device/service responses: busy/unknown playback refusal, other-app interruption refusal,
  active-profile selection, add-on version checks, and immutable/expiring/profile-bound layout previews.
- Wheel and source distribution build; no credentials, backups or device logs in package contents.

Real Shield checks during packaging:

- ADB authorization and device access worked; the Kodi process was present.
- Real MCP stdio calls for Shield diagnostics, bounded redacted Android Kodi logs, and Kodi source-file
  reads passed. A disabled remote-control call was refused without sending input.
- No remote input, app launch, restart, source edit or configuration change was performed.
- Kodi's HTTP endpoint was unavailable during this check. Live JSON-RPC/provider previews and live
  Manager layout changes therefore **were not verified through this new MCP server** in this session.
  Their protocol/adapter behaviour is tested with synthetic services; broader firmware/client testing
  is still needed. Existing Manager behaviour was developed and exercised separately before this repo.

Linux/Windows Python 3.11–3.13 checks run in the repository's GitHub Actions matrix.
Read the actual CI result before claiming a particular platform is verified. Tests deliberately do not
connect to household devices in CI. An alpha release is not a universal Kodi compatibility guarantee.
