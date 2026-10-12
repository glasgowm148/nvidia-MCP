# Apple TV / tvOS

Apple TV support is opt-in and experimental. Android/Shield remains the default backend. This
release has synthetic tests and a check against the installed pyatv SDK; it has **no physical
Apple TV validation**. Use Kodi on Apple TV HD/4K, not Apple TV 2/3. Installing/sideloading Kodi,
signing its IPA and renewing its provisioning are outside this server; follow
[Kodi's tvOS guide](https://kodi.wiki/view/TvOS).

## What matches the Shield workflow

| Workflow | Apple TV behavior |
| --- | --- |
| Kodi inspection | Version, active profile, skin, add-ons, settings and players over authenticated Kodi HTTP |
| Skin management | Manager layout inspect → preview → apply, existing revision/source/version gates, backup and menu rebuild |
| Provider/widget work | Opt-in bounded directory previews, widget-cache inspection and guarded refresh through Kodi/Manager |
| Configuration | Live non-credential add-on settings, core settings with existing protections, Manager checkpoint/add-on backup → restore → undo |
| File diagnostics | Active-profile/add-on text through Manager's VFS, checksum checked; redacted model output and private local per-file snapshots |
| Logs | Manager's bounded redacted **current** Kodi log; no previous-log file reader |
| Remote/lifecycle | Kodi navigation; paired Home, installed-app list, power and launch; graceful Kodi quit/restart |
| Android system access | APK/split installs, screenshots, logcat, arbitrary file patches, offline restores, shell, process/memory telemetry and force-stop unavailable |

Legacy shared tools keep their `shield_*` names. Android-only tools are omitted in Apple TV mode.
`apple_tv_power` is Apple-only and appears with write mode. Core Kodi reads work without pairing
or Manager; skin management, file reads and guarded changes need Manager **0.7.17+**. Layout
writes still require reviewed Bingie 2.0.2 / Skin Shortcuts 2.0.3 source hashes. Installing this
release does not make an unknown or modified skin writable, and does not install a skin for you.

## Prepare the TV

1. Have a working tvOS Kodi installation. Find its private LAN IP; open Kodi and leave it active.
2. Enable Kodi's authenticated HTTP remote control (normally port 8080).
3. Install the exported Manager ZIP through Kodi's **Install from zip file**, using a private
   network share/source Kodi can read. No ADB push or Android storage path is used. The computer
   agent can prepare/export the ZIP; initial installation and security settings use Kodi's UI.
4. In Manager's Kodi settings, enable **Allow LAN access** (normally port 8765). Apple TV requires
   direct HTTP; loopback forwarding is unavailable. Enter Manager's token privately into the
   computer configuration using the token shown in Kodi's settings. The redacted file tool cannot
   recover that token. Tokens belong to the active profile; update privately after switching.
5. When ready for paired controls, keep **Settings → Remotes and Devices → Remote App and Devices**
   open if pairing needs it. Enter each displayed PIN through the agent's private input/hidden
   terminal. Never paste PINs, credentials or an Apple ID into a public log or an MCP tool call.

## Computer setup (agent performs this)

Install the reviewed release with its optional dependency:

Resolve the installed environment's paths; Windows uses `.venv\Scripts\python.exe` and
`.venv\Scripts\nvidia-mcp.exe` instead of `.venv/bin/…`.

```sh
.venv/bin/python -m pip install -e '.[apple-tv]'
```

Merge an **Apple TV server entry** into the client's private configuration without replacing an
existing Shield entry. Each server instance targets one explicit host; do not scan the LAN.

| Variable | Value |
| --- | --- |
| `NVIDIA_MCP_PLATFORM` | `apple_tv` |
| `APPLE_TV_HOST` | The TV's private IPv4 address (pyatv unicast control requires IPv4) |
| `KODI_HTTP_ROUTE` | `direct` |
| `APPLE_TV_CREDENTIALS_FILE` | Absolute private computer path, e.g. inside the server's private state directory |
| `KODI_USERNAME`, `KODI_PASSWORD`, `KODI_PORT` | Existing Kodi HTTP credentials/port |
| `KODI_MANAGER_TOKEN`, `KODI_MANAGER_PORT` | This profile's Manager token/port |
| `APPLE_TV_KODI_APP_ID` | Kodi's actual installed signing bundle ID, needed only for launch/restart |
| `NVIDIA_MCP_ALLOW_WRITES`, `NVIDIA_MCP_ALLOW_PLUGIN_BROWSE` | Initially `0` |

Remove Android/Shield host values from this entry. Conflicting host values and any `forward`/`auto`
route are rejected. No ADB/SDK Build Tools installation is needed. Existing Shield entries should
keep their current environment and backend.

Run both pairing actions sequentially using that private environment, outside MCP:

```sh
nvidia-mcp --pair-apple-tv Companion
nvidia-mcp --pair-apple-tv AirPlay
nvidia-mcp --doctor
```

The CLI reads four-digit PINs with hidden terminal input or private stdin; it merges both secrets
into an atomically saved 0600 file and prints no secret. PINs never go in command arguments. Input runs on the calling terminal thread so Ctrl-C/EOF closes pairing without leaving a blocked executor reader. Pairing
suppresses the pyatv logging namespace during pairing, including PIN/key debug traces, and restores
its previous log levels after success or failure. Pairing does not enable write mode. Both protocols are required for the paired playback/power guard.
`shield_apps` lists installed bundle IDs; confirm Kodi's ID instead of guessing `org.xbmc.kodi`.
Start with `kodi_status`, `shield_connection` and `kodi_manager_inspect(area='layout')`.

## Changes and recovery

Explicitly enable MCP writes and Manager writes only for requested changes. Inspect a layout,
preview its complete section rows, then apply the returned preview ID within ten minutes. Device,
profile path, installed source hashes and layout revision are checked; stale plans require a new
preview. Use `kodi_manager_inspect(area='backups', addon_id='skin.bingie')` to list add-on backups,
or omit `addon_id` for checkpoints. `kodi_configuration_backup` and
`kodi_configuration_restore` reuse Manager's backup/undo implementation.

Before changes, the guard establishes a new paired connection because SDK playback/power getters
are push caches, checks reported system media (paused media counts as busy), confirms Kodi's
native UIApplication state is active, then checks Kodi players. Unknown/unavailable state blocks
changes. SDK idle without a received playback state is treated as unknown; metadata-less paused
players remain busy. The pinned pyatv 0.16 MRP adapter waits up to three seconds for an explicit
state, and its missing/changed internals fail closed. A fresh Home/idle connection may therefore
refuse writes until the device reports a stopped state. Inspect after normal playback has been
stopped; do not bypass the guard.

Another app's playback is never overridden on Apple TV. Starting inactive Kodi needs
both `interrupt_other_app=true` and the human-set `NVIDIA_MCP_ALLOW_INTERRUPT=1`; media must still
be confirmed stopped/idle. An explicit app switch never bypasses Manager authentication, malformed
state or a changed Manager identity. Only offline timeout/unreachability can use the launch opt-in.
Stop/restart use Kodi's graceful quit only. HTTP disappearance is not proof the process
terminated; a launch request is not readiness. Hung exits need manual TV recovery.

Kodi stores tvOS userdata XML in its virtual filesystem/NSUserDefaults. Manager writes each XML
preference in one operation, verifies it and rolls back on failure. POSIX rename/SMB copies of
that userdata XML can read stale physical shadows, so they are not a configuration backup.
Kodi keeps `customcontroller.SiriRemote*.xml` as physical files; Manager 0.7.20 handles that
exception. Non-XML data, directories, cache databases and backup manifests can be purged by tvOS. Manager's
on-device snapshots are useful undo points, **not a durable disaster-recovery backup**. Copy
important text to private computer snapshots before risky work; per-file snapshots cannot be
restored automatically on tvOS, and do not back up the IPA or entire app container.
Never uninstall Kodi to obtain a clean slate without an independent backup.

Manager 0.7.22 preserves translated backup paths for virtual XML under directory aliases and
keeps live access/identity untouched during failed restore rollback. Take a fresh validated
snapshot after updating: older alias-affected physical XML snapshots may fail completeness
checks. Retained files stay intact; keep independent private recovery copies.

The persistent Manager ID binds local snapshots to that Manager instance, not a hardware serial.
Deleting its userdata, reinstalling Kodi or cloning its preferences affects identity; reconnect
and inspect rather than bypassing ownership checks. Active-profile/add-on text reads use simple
ASCII relative paths, reject traversal/symlinks and are limited to 600 KB per file. Manager 0.7.17+ checks requested device/profile ownership and returns it with each file; mismatched/older responses are refused. Kodi profile paths outside the canonical `userdata/profiles/` tree are currently unsupported by this MCP backend. Virtual XML
backup/write readback is limited to 2 MB per file. Large configuration files need separate recovery.

## Protocols and verification limits

The computer uses the public open-source [pyatv library](https://pyatv.dev/documentation/supported_features/)
for Companion controls and AirPlay-tunneled media state. These are reverse-engineered protocols,
not an Apple management API or a proprietary connector. Feature availability is checked at runtime;
tvOS/protocol changes and apps that do not report media state can limit the guard. Playing-app
metadata is not proof of foreground focus; Manager reads Kodi's native application state instead.
There is no background-daemon or jailbreak requirement added by this project.

Before claiming device compatibility, test on a spare/backed-up Apple TV: both private pairings,
Kodi/Manager HTTP auth, active/inactive/background detection, another app's paused/background
media refusal, both Kodi profiles, one reversible setting/layout edit and its undo, widget refresh,
quit/relaunch and sleep/wake. Record model, tvOS, Kodi, skin and helper versions. No such hardware
test was performed for this release; unknown native focus keeps writes disabled.
