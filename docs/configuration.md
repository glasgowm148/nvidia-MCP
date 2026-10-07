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
| `NVIDIA_MCP_ALLOW_WRITES` | `0` | Register and allow write/disruptive tools. With `0` they are not listed at all |
| `NVIDIA_MCP_ALLOW_PLUGIN_BROWSE` | `0` | Allow executing directory previews |
| `NVIDIA_MCP_ALLOW_INTERRUPT` | `0` | Honour the model-supplied `allow_during_playback` / `interrupt_other_app` flags. Without it those flags are refused |
| `NVIDIA_MCP_EXTRA_LAUNCHERS` | empty | Comma-separated home-screen package names treated like the built-in launchers |
| `NVIDIA_MCP_ALLOW_SETTINGS` | empty | Comma-separated **exact** protected Kodi setting ids that `kodi_set_setting` may change |
| `NVIDIA_MCP_TRUSTED_SIGNERS` | empty | Comma-separated SHA-256 APK signer fingerprints trusted for **new** app installs |
| `NVIDIA_MCP_TRUSTED_SIGNERS_FILE` | unset | File with one fingerprint per line (`#` comments), merged with the variable above |
| `NVIDIA_MCP_STATE_DIR` | OS user app-data directory | Private snapshots and value-free audit records |
| `NVIDIA_MCP_RETENTION_DAYS` | `90` | On start, prune backups older than this beyond the kept count; `0` disables pruning |
| `NVIDIA_MCP_KEEP_FILE_BACKUPS` | `50` | Newest per-file snapshots always kept |
| `NVIDIA_MCP_KEEP_APK_BACKUPS` | `3` | Newest *verified* APK recovery bundles always kept; unverified bundles are never pruned |

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

Every disruptive tool (remote buttons, Kodi lifecycle, skin-menu rebuild, plugin browsing and APK
install) uses one guard. It refuses active Kodi playback, fails closed if playback state is unknown,
and checks the foreground Android app against one launcher set (Google TV/Android TV launchers and
Projectivy, plus `NVIDIA_MCP_EXTRA_LAUNCHERS`): with Netflix, YouTube or SmartTube in front, a Home or
Back press would go to that app, so it is refused. Offline recovery needs an explicit tool flag.
Interrupting playback or another app needs the tool flag **and** `NVIDIA_MCP_ALLOW_INTERRUPT=1`,
because tool arguments are chosen by the model; get permission from the person viewing as well.
Write mode is a capability switch, not a substitute for an agent's approval policy.

### Protected Kodi settings

`kodi_set_setting` refuses settings that weaken security or expose services: `services.*` (web
server, its authentication and port, event server, Zeroconf, UPnP, AirPlay, SMB...), `masterlock.*`,
`system.*`, `debug.*` (except the harmless `debug.showloginfo` overlay), `pvrparental.*`, the HTTP
proxy settings, `addons.unknownsources`, `addons.updatemode` and `lookandfeel.skin`. Change these on
the TV. An advanced user who really wants an agent to change one can list its exact id in
`NVIDIA_MCP_ALLOW_SETTINGS`; wildcards are not accepted. Credential settings are always refused.

### Plugin browsing

`kodi_browse` refuses any `plugin://` route whose path segments, query parameter names or values
contain an action word such as play, resolve, toggle, refresh, clear, delete, remove, (un)install,
settings, auth, sign in/out, logout, maintenance, manager, rescan, reset, update, input, keyboard,
dialog or context. Ordinary listing routes (e.g. YouTube `/special/popular_right_now/`, Fen
`mode=build_movie_list`) keep working. Display-only values (`name`, `title`, `label`, `plot`) are not
treated as routing.

For file repairs, read the original/checksum, preview exact replacements with `kodi_patch_preview`
(it returns a redacted unified diff), stop Kodi, apply with `kodi_patch_apply`, restart and verify.
`kodi_patch_file` remains as a deprecated alias that dispatches on `dry_run`. Patches that touch
credential settings or values, and edits to add-on Python (`addons/**.py`), are refused. Writes to repair files/settings take private backups. Stale checksums and ambiguous
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
