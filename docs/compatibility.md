# Compatibility and verification

| Component | Evidence | Limit |
| --- | --- | --- |
| Computer runtime | Python 3.11+; Linux/Windows CI on 3.11–3.13; macOS local Python 3.14 | Read actual CI for the release; broader systems unverified |
| MCP interface | Real stdio initialization, Android: 24 default tools (37 with writes enabled); Apple TV: 18/28, resource/prompt discovery; mcp 1.28 and latest in CI; fresh-wheel local HTTP fixture | Client approval behavior depends on your MCP client |
| Shield ADB | Reference Android 11 captures replayed in tests; 0.4.8 source checked live for authorization and viewing state on 2026-10-12 | One Shield; no new live mutations/installation checks; sleeping display unobserved |
| Android TV / Google TV / Fire OS | 0.4.9 synthetic tests for Fire home launcher, legacy/modern foreground, background/paused media, missing-pidof process guards, config aliases and private ADB pairing | No physical Firestick/Google TV validation; vendor restrictions vary; Vega OS unsupported; see [device guide](android-tv.md) |
| Apple TV / tvOS | 0.5.5 synthetic paired-protocol, private PIN/error/debug-log, profile/device, VFS file checksum, layout/backup, capability and viewing-refusal tests; real pyatv uninitialized/metadata-less-paused state regression and API check in CI | Experimental; no physical Apple TV tests. Needs Manager 0.7.17+ for skin/files/guarded changes; no ADB/offline recovery. See [Apple TV guide](apple-tv.md) |
| Kodi HTTP | Live read-only 0.4.8 source on Kodi 22 RC1 through ADB forwarding: version, profile resolution, 104 add-ons / 100 enabled; synthetic authenticated JSON-RPC and failure/refusal tests | Direct LAN HTTP from this host application is blocked; other devices unverified |
| Kodi build | The reference Shield moved from Kodi 22 beta 2 to 22.0 RC1 (`22.0-RC1 (21.90.901)`) on 2026-10-10; tools use version-independent JSON-RPC and ADB calls | 0.4.3/0.4.4 fixes are tested offline against real RC1 dumps and logs, not yet called live; see [verification](verification.md) |
| Official Kodi APKs | Local SDK inspection of 21.3/22 beta 2 arm64, signer/version/SDK/ABI and corruption refusal | Metadata/signature checks are not runtime testing |
| APK install/recovery | Synthetic transfer/session/backup/readback, changing hardware identity and recovery-storage failure tests | Stable hardware serial required; live Shield upgrade and recovery unverified; no automatic/guaranteed downgrade |
| Optional Manager | Pinned public 0.7.23 ZIP/export (supports 0.4+; widget cache 0.6+), checksum-verified from its release; live authenticated health/status via the new forwarding route against household Manager 0.7.12 | Public 0.7.23 ZIP not installed on the Shield; household patches are separate |
| Optional profile handoff | Helper 1.1 with the matching client/script compiled and privately deployed on the reference Shield / Kodi 22 RC1; automatic Adults → Kids → Adults in 29.1 / 23.5 seconds, Home and channel counts verified (2026-10-12); actual Java readiness-policy tests | Source-only, opt-in; gated to 22.0-BETA2/RC1; no automatic reopen if Kodi dies before the saved shutdown checkpoint |
| Library API | `nvidia_mcp.Shield` (docs/library.md), replay tests plus live read-only Kodi/Manager forwarding on the reference Shield (2026-10-12) | Other hosts/firmware still rely on CI and synthetic checks |
| Layout writes | Reviewed Bingie 2.0.2 / Skin Shortcuts 2.0.3 source hashes | Other/forked/modified versions stay view-only |

Start with [TV preparation](setup.md), then give your agent the IP for [computer setup](agent-setup.md).
Use `shield_connection` to distinguish ADB authorization, Kodi HTTP and Manager readiness. A ready
connection or foreground app name does not by itself establish that nobody is watching.

Before broad promotion, use a spare/backed-up Shield to verify an authorized install, startup, both
profiles, settings/provider playback and recovery. Do not downgrade/uninstall the household's Kodi
merely to obtain a test result. Record model/Android/Kodi/skin versions and outcomes.

See [detailed verification](verification.md), [APK recovery](apk-upgrades.md),
[file recovery](repairs.md) and [companion configuration recovery](https://github.com/glasgowm148/kodi-manager/blob/main/docs/recovery.md).
