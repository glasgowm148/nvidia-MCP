# Configuration and operation rules

For Apple TV setup and supported operations, see [tvOS support](apple-tv.md). Apple TV requires direct HTTP; Android forwarding, mounted storage, APK/shell access and offline recovery do not apply. Writes still need both write switches, private pairing and confirmed active Kodi. Apple snapshots are owned by a persistent Manager-instance ID, not a hardware serial.

For Android TV, Google TV and Fire OS menus, pairing codes and OS limits, see [device setup](android-tv.md).

The [agent setup guide](agent-setup.md) explains where to put these values in your MCP client's
private server configuration. The server does **not** load `.env` automatically. Never commit a
filled configuration or print account credentials into diagnostic output.

## Environment variables

| Variable | Default | Meaning |
| --- | --- | --- |
| `NVIDIA_MCP_PLATFORM` | `android` | `android` or opt-in `apple_tv`; existing Shield settings keep the default |
| `APPLE_TV_HOST` | required in Apple mode | One private Apple TV IP; conflicting Android host settings rejected |
| `APPLE_TV_CREDENTIALS_FILE` | unset | Private computer file containing paired Companion/AirPlay credentials; CLI pairing only |
| `APPLE_TV_KODI_APP_ID` | empty | Actual installed Kodi signing bundle ID for launch/restart; inspect `shield_list_apps` |
| `ANDROID_TV_HOST` / `SHIELD_HOST` | required | Private LAN IP; one Android TV / Fire OS device per instance; conflicting aliases are rejected |
| `ANDROID_TV_ADB_PORT` / `SHIELD_ADB_PORT` | `5555` | ADB connection port; paired Wireless debugging can use a dynamic port; conflicting aliases are rejected |
| `ADB_PATH` | `adb` | Platform Tools executable |
| `AAPT2_PATH` | `aapt2` | Optional SDK Build Tools metadata executable; needed for APK tools |
| `APKSIGNER_PATH` | `apksigner` | Optional SDK signature verifier or `lib/apksigner.jar` |
| `JAVA_PATH` | `java` | Java executable used with the signature verifier JAR |
| `KODI_PORT` | `8080` | Kodi HTTP port |
| `KODI_HTTP_ROUTE` | `direct` | `direct`: LAN HTTP; `forward`: authorized ADB forwarding to localhost; `auto`: try direct, forward only on connection failure. Applies independently to Kodi HTTP and Manager |
| `KODI_USERNAME`, `KODI_PASSWORD` | empty | Kodi HTTP credentials, separate from ADB authorization |
| `KODI_MOUNT` | unset | Absolute mounted `.kodi` path; otherwise ADB files |
| `KODI_REMOTE_ROOT` | `/sdcard/Android/data/org.xbmc.kodi/files/.kodi` | Shared-storage root for ADB |
| `KODI_MANAGER_PORT`, `KODI_MANAGER_TOKEN` | `8765`, empty | Optional Manager connection |
| `NVIDIA_MCP_TOOL_PROFILE` | `standard` | Discovery: everyday tools plus configured Manager features; `full` adds file repair, Android diagnostics and APK tools. Reload server after changing; does not grant permissions or disable legacy calls |
| `NVIDIA_MCP_ALLOW_WRITES` | `0` | Register and allow write/disruptive tools. With `0` they are not listed at all |
| `NVIDIA_MCP_ALLOW_PLUGIN_BROWSE` | `0` | Allow executing directory previews |
| `NVIDIA_MCP_ALLOW_INTERRUPT` | `0` | Honour the model-supplied `allow_during_playback` (remote) / `interrupt_other_app` (lifecycle: other apps only, never Kodi playback) flags. Without it those flags are refused |
| `NVIDIA_MCP_ALLOW_OFFLINE_RECOVERY` | `0` | Honour `kodi_control_lifecycle`'s model-supplied `allow_offline_recovery` flag (stop/restart a Kodi whose HTTP server is unreachable). Without it the flag is refused |
| `NVIDIA_MCP_EXTRA_LAUNCHERS` | empty | Comma-separated home-screen package names treated like the built-in launchers |
| `NVIDIA_MCP_ALLOW_SETTINGS` | empty | Comma-separated **exact** protected Kodi setting ids that `kodi_set_setting` may change |
| `NVIDIA_MCP_TRUSTED_SIGNERS` | empty | Comma-separated SHA-256 APK signer fingerprints trusted for **new** app installs |
| `NVIDIA_MCP_TRUSTED_SIGNERS_FILE` | unset | File with one fingerprint per line (`#` comments), merged with the variable above |
| `NVIDIA_MCP_STATE_DIR` | OS user app-data directory | Private snapshots and value-free audit records. Snapshots are tied to the Shield's `ro.serialno` (older ones, or ones taken without ADB, to `SHIELD_HOST:SHIELD_ADB_PORT`), so a new DHCP address keeps them usable |
| `NVIDIA_MCP_RETENTION_DAYS` | `90` | On start, prune backups older than this beyond the kept count; `0` disables pruning |
| `NVIDIA_MCP_KEEP_FILE_BACKUPS` | `50` | Newest per-file snapshots always kept |
| `NVIDIA_MCP_KEEP_APK_BACKUPS` | `3` | Newest *verified* APK recovery bundles always kept. Bundles from attempts that failed before any APK was transferred are pruned after the retention window; a bundle whose install started but did not verify is never pruned |

ADB authorization, Kodi HTTP credentials and the Manager bearer token are separate. Use
`shield_check_connection` and `--doctor` as described in [agent setup](agent-setup.md) to check readiness.

`forward` is useful when the host application's LAN connection is blocked, including macOS Local
Network permissions, or Manager is intentionally listening only on the TV's loopback interface.
It requires the configured Shield to be connected and authorized in ADB; it does not connect or
authorize a new device automatically. Authentication and write guards still apply. `auto` keeps
authentication, invalid-response and service failures visible instead of trying another route.
Forwards are created once per service per process and removed when that process exits normally.
Force-killing the process can leave a forward in the local ADB server; the agent can remove that
specific local port. Forwarding serves the MCP/library connection, not a browser on another device.

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

Every disruptive tool (remote buttons, Kodi lifecycle, Kodi and add-on setting changes, hub layout
apply, widget-cache refresh, skin-menu rebuild, plugin browsing and APK install) uses one guard. File
patches and restores instead require Kodi to be stopped. The guard refuses active or paused Kodi
playback and fails closed if playback state is unknown. It refuses while any Android app's media
session is playing or paused (Spotify in the background, a film paused under the screensaver),
because a button or app launch can take audio focus from it. It checks the foreground Android app
against one launcher set (Google TV/Android TV launchers and Projectivy, plus
`NVIDIA_MCP_EXTRA_LAUNCHERS`): with Netflix, YouTube or SmartTube in front, a Home or Back press
would go to that app, so it is refused. Kodi in front is always checked for playback, even when the
process probe misses it. A screensaver (Android's `DreamActivity`) or a sleeping display counts as
nobody watching, after the same playback checks; remote buttons are still refused while the Shield
sleeps, because a key press wakes it and can switch the TV on through HDMI-CEC. `play_pause` and
`stop` are refused when nothing is playing (they would only wake the last app that handled media
buttons); with `allow_during_playback` they are sent to Kodi's player over JSON-RPC when Kodi is
playing. Offline recovery (`allow_offline_recovery`) needs the tool flag *and* the user's own
`NVIDIA_MCP_ALLOW_OFFLINE_RECOVERY=1`, applies only when Kodi's HTTP server is unreachable or times
out (not on authentication or protocol errors), and is refused while Android's media session for
Kodi reports playing or paused. Without HTTP the server cannot ask Kodi what it is doing, so the
decision rests on Android's media session and foreground app alone; that is why a person, not the
model, has to enable it.
The model-supplied override flags also need `NVIDIA_MCP_ALLOW_INTERRUPT=1`; get permission from the
person viewing as well. `shield_send_button`'s `allow_during_playback` skips the viewing checks (to pause
or stop what is on screen). `kodi_control_lifecycle`'s `interrupt_other_app` only covers *another* app in
front or playing: Kodi's own playback is always refused.

The guard checks the TV once, just before the action. A skin-menu rebuild (`kodi_rebuild_layout`)
reloads the skin a few seconds later, and an APK install can take minutes after its last check, so
somebody who starts watching in that window can still be interrupted.

A Kodi that froze mid-film usually still looks like playback (Android's media session stays at
playing or paused, and HTTP may still answer with an error), so no tool flag will stop it. Ask the
viewer to close Kodi on the TV (Settings → Apps → Kodi → Force stop) or restart the Shield. This
is deliberate: a frozen Kodi and a film somebody has paused look the same from here (audit R2-05).

`kodi_control_lifecycle` stop/restart asks Kodi to quit over JSON-RPC (`Application.Quit`, so it saves its
settings) and waits up to 30 seconds for the process to end. Kodi 22 on the Shield can hang after
"Stopping all" for minutes. In that case the tool force-stops it only when the current `kodi.log`
shows the whole save sequence ("Stopping the application...", "Saving settings", "Saving skin
settings", "Stopping all") *and* the TV guard still passes on Android's own signals (no media
playing or paused, no other app in front). Otherwise it reports `exit_hung`, does not start Kodi
again, and leaves the stuck Kodi for the person at the TV. Force-stop without a quit is used only for
permitted offline recovery, when Kodi's HTTP server cannot take the request.
Write mode is a capability switch, not a substitute for an agent's approval policy.

### Protected Kodi settings

`kodi_set_setting` refuses settings that weaken security or expose services: `services.*` (web
server, its authentication and port, event server, Zeroconf, UPnP, AirPlay, SMB...), `masterlock.*`,
`system.*`, `debug.*` (except the harmless `debug.showloginfo` overlay), `pvrparental.*`, the HTTP
proxy settings, `addons.unknownsources`, `addons.updatemode` and `lookandfeel.skin`. It also refuses
settings where a wrong value can leave the TV blank, silent or unreadable with no way back from the
remote: `videoscreen.*` (resolution, screen, refresh-rate whitelist...), `audiooutput.audiodevice`,
`audiooutput.passthroughdevice`, `videoplayer.adjustrefreshrate` and `locale.language`. Change these
on the TV. An advanced user who really wants an agent to change one can list its exact id in
`NVIDIA_MCP_ALLOW_SETTINGS`; wildcards are not accepted. Credential settings are always refused.

### Plugin browsing

`kodi_browse_directory` refuses any `plugin://` route whose path segments, query parameter names or values
contain an action word such as play, resolve, toggle, refresh, clear, delete, remove, (un)install,
settings, auth, sign in/out, logout, maintenance, manager, rescan, reset, update, input, keyboard,
dialog or context. Ordinary listing routes (e.g. YouTube `/special/popular_right_now/`, Fen
`mode=build_movie_list`) keep working. Display-only values (`name`, `title`, `label`, `plot`) are not
treated as routing.

For file repairs, read the original/checksum, preview exact replacements with `kodi_preview_file_patch`
(it returns a redacted unified diff), stop Kodi, apply with `kodi_apply_file_patch`, restart and verify.
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

Hardware identity is read again for each backup operation. A snapshot with a recorded `device_id`
requires that exact current `ro.serialno`; an unavailable or placeholder serial never falls back
to the same IP address. Older snapshots without `device_id`, and file snapshots created without
ADB identity, still use their recorded host/port. APK previews always require a verified serial.

## HTTP response failures

From 0.5.5, HTTP exchanges have a 60-second socket deadline, including response headers and
body streaming. Socket reads still time out after 20 seconds and connections after 3 seconds.
Connections are not reused, so a deadline cannot shut down a later request.
`response_timeout` means the service answered or connected but stalled; partial/malformed
responses use `invalid_response`. These do not authorize Apple TV's offline launch opt-in.
A timeout does not prove a change failed: inspect state before retrying.
