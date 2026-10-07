# Compatibility and verification

| Component | Evidence | Limit |
| --- | --- | --- |
| Computer runtime | Python 3.11+; Linux/Windows CI on 3.11–3.13; macOS local Python 3.14 | Read actual CI for the release; broader systems unverified |
| MCP interface | Real stdio initialization, 23 read-only tools (34 with writes enabled), resource/prompt discovery; mcp 1.28 and latest in CI; fresh-wheel local HTTP fixture | Client approval behavior depends on your MCP client |
| Shield ADB | Prior release: live read-only device/source/log diagnostics | No current live mutation/installation verification |
| Kodi HTTP | Synthetic authenticated JSON-RPC, response bounds and failure/refusal tests | Earlier live check had HTTP unavailable |
| Official Kodi APKs | Local SDK inspection of 21.3/22 beta 2 arm64, signer/version/SDK/ABI and corruption refusal | Metadata/signature checks are not runtime testing |
| APK install/recovery | Synthetic transfer/session/backup/readback and refusal tests | Live Shield upgrade and recovery unverified; no automatic/guaranteed downgrade |
| Optional Manager | Pinned 0.6.2 ZIP/export (supports 0.4+; widget cache 0.6+); separate library tests/CI | Portable companion not yet deployed/tested on a live TV |
| Layout writes | Reviewed Bingie 2.0.2 / Skin Shortcuts 2.0.3 source hashes | Other/forked/modified versions stay view-only |

Start with [TV preparation](setup.md), then give your agent the IP for [computer setup](agent-setup.md).
Use `shield_connection` to distinguish ADB authorization, Kodi HTTP and Manager readiness. A ready
connection or foreground app name does not by itself establish that nobody is watching.

Before broad promotion, use a spare/backed-up Shield to verify an authorized install, startup, both
profiles, settings/provider playback and recovery. Do not downgrade/uninstall the household's Kodi
merely to obtain a test result. Record model/Android/Kodi/skin versions and outcomes.

See [detailed verification](verification.md), [APK recovery](apk-upgrades.md),
[file recovery](repairs.md) and [companion configuration recovery](https://github.com/glasgowm148/kodi-manager/blob/main/docs/recovery.md).
