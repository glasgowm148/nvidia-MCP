# Configuration and operation rules

The [agent setup guide](agent-setup.md) explains where to put these values in your MCP client's
private server configuration. The server does **not** load `.env` automatically. Never commit a
filled configuration or print account credentials into diagnostic output.

## Environment variables

| Variable | Default | Meaning |
| --- | --- | --- |
| `SHIELD_HOST` | required | Private LAN IP; one device per server instance |
| `SHIELD_ADB_PORT` | `5555` | Shield network debugging port |
| `ADB_PATH` | `adb` | Platform Tools executable |
| `AAPT2_PATH` | `aapt2` | Optional SDK Build Tools metadata executable; needed for APK tools |
| `APKSIGNER_PATH` | `apksigner` | Optional SDK signature verifier or `lib/apksigner.jar` |
| `JAVA_PATH` | `java` | Java executable used with the signature verifier JAR |
| `KODI_PORT` | `8080` | Kodi HTTP port |
| `KODI_USERNAME`, `KODI_PASSWORD` | empty | Kodi HTTP credentials, separate from ADB authorization |
| `KODI_MOUNT` | unset | Absolute mounted `.kodi` path; otherwise ADB files |
| `KODI_REMOTE_ROOT` | `/sdcard/Android/data/org.xbmc.kodi/files/.kodi` | Shared-storage root for ADB |
| `KODI_MANAGER_PORT`, `KODI_MANAGER_TOKEN` | `8765`, empty | Optional Manager connection |
| `NVIDIA_MCP_ALLOW_WRITES` | `0` | Allow mutation tools |
| `NVIDIA_MCP_ALLOW_PLUGIN_BROWSE` | `0` | Allow executing directory previews |
| `NVIDIA_MCP_STATE_DIR` | OS user app-data directory | Private snapshots and value-free audit records |

ADB authorization, Kodi HTTP credentials and the Manager bearer token are separate. Use
`shield_connection` and `--doctor` as described in [agent setup](agent-setup.md) to check readiness.

## Enable changes deliberately

In the MCP client's environment object, enable only the capabilities needed for the requested work:

```json
{
  "NVIDIA_MCP_ALLOW_WRITES": "1",
  "NVIDIA_MCP_ALLOW_PLUGIN_BROWSE": "1"
}
```

These are independent switches. Plugin browsing uses `Files.GetDirectory`, which executes installed
add-on code and can make network requests. Preview one bounded page at a time. The server does not
expose whole-tree crawls, arbitrary shell commands or unrestricted JSON-RPC.

Disruptive tools refuse active Kodi playback and fail closed if playback state is unknown. Kodi
lifecycle changes also inspect the foreground Android app: idle Kodi does not establish that the
TV is free. Offline recovery and interrupting another app require explicit tool flags **and permission
from the person viewing**. Remote buttons cannot infer whether another app is playing; obtain
permission first. Write mode is a capability switch, not a substitute for an agent's approval policy.

For file repairs, read the original/checksum, preview exact replacements, stop Kodi, apply, restart
and verify. Writes to repair files/settings take private backups. Stale checksums and ambiguous
anchors are rejected; unknown add-on versions need investigation. See [repairs](repairs.md).

For live Bingie writes, enable Manager's own write mode as well. MCP stages an immutable preview
that expires after **10 minutes**. Apply that preview ID; changing the plan requires a new preview.
Manager checks the profile, layout revision and reviewed source hashes, and creates a backup.
See [companion setup](companion.md) and [security](../SECURITY.md).

## Storage and platform limits

Android scoped storage can deny ADB file access on some firmware. Use a mounted Shield storage share
with `KODI_MOUNT` when available; the server reports failures instead of bypassing permissions.
File access stays within the configured Kodi root. This release targets the official `org.xbmc.kodi`
package; firmware paths and other package/activity names may differ.

APK operations use official SDK tools and explicit local APKs/split sets. They do not download,
uninstall, downgrade or automatically roll back apps. Kodi upgrades require a validated add-ons/
userdata snapshot as well as original APK recovery files. See [the APK workflow](apk-upgrades.md).

Use a trusted LAN. Manager's bearer-authenticated HTTP service should not be exposed to the internet.
Backups and account/log diagnostics are private and can contain credentials.
