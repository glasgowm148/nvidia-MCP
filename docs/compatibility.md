# Compatibility and verification

| Component | Evidence | Limit |
| --- | --- | --- |
| Computer runtime | Python 3.11+; Linux/Windows CI on 3.11–3.13; macOS local Python 3.14 | Read actual CI for the release; broader systems unverified |
| MCP interface | Real stdio initialization, 23 read-only tools (34 with writes enabled), resource/prompt discovery; mcp 1.28 and latest in CI; fresh-wheel local HTTP fixture | Client approval behavior depends on your MCP client |
| Shield ADB | Android 11 `dumpsys media_session` / `activity` / `power`, kodi.log exits and memory captures from the reference Shield (2026-10-10/11) replayed in tests (tests/fixtures/real); earlier live read-only diagnostics | Tool calls through this server not re-run live for 0.4.4–0.4.6; no live mutation/installation verification; sleeping display unobserved |
| Kodi HTTP | Synthetic authenticated JSON-RPC, response bounds and failure/refusal tests | Earlier live check had HTTP unavailable |
| Kodi build | The reference Shield moved from Kodi 22 beta 2 to 22.0 RC1 (`22.0-RC1 (21.90.901)`) on 2026-10-10; tools use version-independent JSON-RPC and ADB calls | 0.4.3/0.4.4 fixes are tested offline against real RC1 dumps and logs, not yet called live; see [verification](verification.md) |
| Official Kodi APKs | Local SDK inspection of 21.3/22 beta 2 arm64, signer/version/SDK/ABI and corruption refusal | Metadata/signature checks are not runtime testing |
| APK install/recovery | Synthetic transfer/session/backup/readback and refusal tests | Live Shield upgrade and recovery unverified; no automatic/guaranteed downgrade |
| Optional Manager | Pinned 0.7.10 ZIP/export (supports 0.4+; widget cache 0.6+), built deterministically from the public release commit; separate library tests/CI | Generic 0.7.10 package validated locally, not yet installed on the Shield; household patches are separate |
| Optional profile handoff | Source compiled; private variant tested on one Shield with Kodi 22 beta 2 and 22.0 RC1, two profiles; the current contrib `relaunch.sh` deployed and switched profiles on RC1 (2026-10-11) | Source-only, opt-in; gated to 22.0-BETA2/RC1; native crash workaround, not a general Kodi fix |
| Library API | `nvidia_mcp.Shield` (docs/library.md), tested against the same replayed captures; direct and `adb forward` JSON-RPC routes | Forward route not yet exercised against the Shield |
| Layout writes | Reviewed Bingie 2.0.2 / Skin Shortcuts 2.0.3 source hashes | Other/forked/modified versions stay view-only |

Start with [TV preparation](setup.md), then give your agent the IP for [computer setup](agent-setup.md).
Use `shield_connection` to distinguish ADB authorization, Kodi HTTP and Manager readiness. A ready
connection or foreground app name does not by itself establish that nobody is watching.

Before broad promotion, use a spare/backed-up Shield to verify an authorized install, startup, both
profiles, settings/provider playback and recovery. Do not downgrade/uninstall the household's Kodi
merely to obtain a test result. Record model/Android/Kodi/skin versions and outcomes.

See [detailed verification](verification.md), [APK recovery](apk-upgrades.md),
[file recovery](repairs.md) and [companion configuration recovery](https://github.com/glasgowm148/kodi-manager/blob/main/docs/recovery.md).
