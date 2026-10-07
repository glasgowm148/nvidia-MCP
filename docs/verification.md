# Verification

## 0.3.1 release preparation

70 MCP tests pass locally, plus clean-wheel stdio/tool/resource/prompt and disabled-write checks
against a synthetic local HTTP service. The pinned Manager 0.4.1 fixes same-second backup collisions;
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
