# nvidia-MCP

A local MCP server for **NVIDIA Shield TV and Kodi**. Give an MCP-compatible assistant the tools to
inspect a Shield, diagnose Kodi problems, preview add-on folders, adjust settings and apply reversible
repairs. It runs on your Mac, Windows PC or Linux computer and connects to your own Shield over your LAN.

Built from real Shield/Kodi troubleshooting: playback interruption guards, separate profile handling,
version checks, redacted diagnostics, exact file patches and rollback backups. No cloud account is needed.

**Prerelease:** see [compatibility and remaining live checks](docs/compatibility.md),
[verification](docs/verification.md) and the [changelog](CHANGELOG.md).

## Quick start

**You prepare the TV; your agent handles the computer setup.** Use an agent with terminal/file access
on the computer that will run MCP. The computer and Shield should be on the same home network.

1. **Find the Shield's IP.** Press **Home** on the Shield remote, then open the
   **Settings gear → Device Preferences → About → Status → IP address**. Note the local IPv4 address
   (four numbers like `192.168.1.50`). Use the address shown on your Shield.
2. **Enable network debugging.** In **Settings → Device Preferences → About**, highlight **Build**
   and press the remote's centre/select button **seven times**. Go back to
   **Device Preferences → Developer options → Debugging** and turn **Network debugging** on.
   Older firmware may put **About** directly under Settings.
3. **Enable Kodi HTTP control.** Open Kodi's **Settings → Services → Control**. Enable **Allow remote
   control via HTTP** and **Require authentication**; set a username/password and note the port
   (usually `8080`). Keep Kodi open. If these settings are hidden, select the **Standard** or **Expert**
   settings level.
4. **Hand over to the agent.** Send the prompt below with your actual Shield IP and Kodi port.
   Provide the Kodi credentials privately when requested. The agent installs the computer tools,
   connects the Shield, configures your MCP client and checks the connection.

```text
Set up https://github.com/glasgowm148/nvidia-MCP on this computer.
Read docs/agent-setup.md and carry out the setup, including dependencies,
ADB connection, MCP client configuration and read-only verification.
I have enabled Shield network debugging and Kodi HTTP control.
Shield IP: YOUR_SHIELD_IP
Kodi HTTP port: 8080
Ask privately for the Kodi username/password if you need them.
Tell me when to approve the debugging prompt on the TV.
Keep write mode and plugin browsing off during setup; do not interrupt playback.
```

When the agent connects, a permission prompt appears **on the TV**: select **Allow** (and optionally
**Always allow from this computer** for your trusted computer). This is the one follow-up TV action;
there is no need to download tools, type commands or edit MCP configuration yourself.

See the [TV preparation guide](docs/setup.md) for detailed menu directions, or the
[agent setup instructions](docs/agent-setup.md) for the computer procedure and configuration example.
After setup, ask: **“Read the Shield repair playbook and audit Kodi without interrupting anything.”**

## Tools

| Area | Tools | Needs |
|---|---|---|
| Shield diagnostics | status, installed packages, logcat, screenshot, connect | ADB |
| Connection readiness | independent ADB/Kodi HTTP/Manager states and suggested fixes | configured services; no TV changes |
| Android APK upgrades | preview local APKs/splits, apply, list recovery bundles | ADB, official SDK Build Tools; apply needs write mode and idle TV |
| Kodi diagnostics | version, skin, profile, playback, add-ons, allowlisted RPC | Kodi HTTP |
| Logs and files | redacted read, log tail, per-file backup list/snapshot | ADB or mounted storage |
| Controls | explicit remote buttons, Kodi start/stop/restart | ADB, write mode, playback guard |
| Repairs | exact text patch, restore with checksum, syntax validation | file access, ADB to prove Kodi stopped, write mode |
| Kodi settings | runtime setting change with backup and readback | Kodi HTTP, file access, write mode |
| Add-on settings | profile-aware reads; version-checked primitive changes | file access; optional Manager for live writes |
| Discovery | one page of a real provider/library folder | Kodi HTTP, opt-in plugin browsing, idle Kodi |
| Bingie | saved layout/sources, preview, apply, rebuild | optional Kodi Manager companion |

The `nvidia://playbook` resource and `audit_kodi` prompt teach the assistant the lessons behind these
tools: account separation, audio hardware, autoplay/progress, source priorities, skin hubs, stale
stream URLs and distinguishing installed/enabled/configured/authenticated/used.

## Enable changes deliberately

Default operation is read-only. Add these environment variables to your client when needed:

```json
"NVIDIA_MCP_ALLOW_WRITES": "1",
"NVIDIA_MCP_ALLOW_PLUGIN_BROWSE": "1"
```

Plugin browsing is separate because `Files.GetDirectory` executes installed add-on code and can make
network requests; it is not just reading a static folder. Preview one page at a time. No whole-tree
crawls, random remote input, arbitrary shell commands or unrestricted JSON-RPC are exposed.

Disruptive tools refuse active Kodi playback and fail closed if playback state is unknown.
Kodi lifecycle changes also inspect the foreground Android app, so an idle Kodi does not imply an idle
TV. Offline recovery and interrupting another app require explicit tool flags **and permission from the
person viewing**. Remote button tools cannot infer whether another app is playing; obtain permission.
Write mode is a coarse capability switch, not a replacement for your assistant's approval policies.

For source/file repairs: read the original file/checksum, preview exact replacements, stop Kodi, apply,
restart and verify. Every write takes a private backup first. Stale checksums and ambiguous anchors are
rejected. Unknown add-on versions must be investigated rather than blindly applying a known patch.
See [repair examples](docs/repairs.md) and [security/recovery details](SECURITY.md).

## Optional live Bingie / Kodi Manager adapter

The distribution includes a pinned **Kodi Manager 0.4.1 companion ZIP**. It is optional: core Shield,
Kodi HTTP, file and offline-repair tools work without it. The agent can export it locally (no device
connection or `SHIELD_HOST` configuration required):

```sh
nvidia-mcp --export-manager ./companion
```

This prints the exported ZIP path and verified SHA-256; it does not install or restart anything.
The agent prepares/transfers the ZIP; use Kodi's **Install from zip file** when the TV is free, then
set its service permissions on the TV. The agent reads the token and configures the MCP connection.
Follow the [companion setup guide](docs/companion.md).
The same ZIP is attached to this project's release for users who prefer downloading it directly.

If you already run Manager 0.3.9, it remains supported; do not replace a customized installation just
to use MCP. For either version (`service.kodi.addonadmin`), configure:

```json
"KODI_MANAGER_PORT": "8765",
"KODI_MANAGER_TOKEN": "YOUR_EXISTING_LOCAL_MANAGER_TOKEN"
```

Use its authenticated layout endpoint to read the actual menu/hub mapping, preview a complete section
plan, then apply the returned preview ID. The preview expires after 10 minutes and cannot be edited
between preview and apply. Manager creates its own backup and checks the expected layout revision.
The adapter supports the Manager's reviewed **Bingie 2.0.2 / Skin Shortcuts 2.0.3** sources; unknown
versions/forks remain view-only. Enable Manager's own write mode for live writes.

The companion has its own [repository and installable Python library](https://github.com/glasgowm148/kodi-manager).
It adds a browser UI, live settings/account controls, local add-on ZIP installation and configuration
backup/restore as well as the MCP layout/pipeline adapter. The Python library alone does not install
the on-device service. Both are MIT licensed, versioned separately and usable independently.

MCP supports verified local APK installation/upgrades, including explicit split APK sets.
Use [the agent APK workflow](docs/apk-upgrades.md): preview before applying; originals are saved and
Kodi upgrades also require a validated addons/userdata snapshot. No automated downloads, uninstall,
downgrade or automatic rollback. Cloud authorization/history migration, native Android TV remote
pairing and distributable provider/skin repair recipes remain follow-up work. No household accounts
or modified third-party add-ons are included. See the [capability boundaries](docs/companion.md).

## Configuration

| Variable | Default | Meaning |
|---|---|---|
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
| `KODI_MANAGER_PORT`, `KODI_MANAGER_TOKEN` | `8765`, empty | Optional Manager |
| `NVIDIA_MCP_ALLOW_WRITES` | `0` | Explicitly allow mutation tools |
| `NVIDIA_MCP_ALLOW_PLUGIN_BROWSE` | `0` | Explicitly allow executing directory previews |
| `NVIDIA_MCP_STATE_DIR` | OS user app-data directory | Private snapshots and value-free audit records |

Android scoped storage can deny ADB file access on some firmware. Use a mounted Shield storage share
with `KODI_MOUNT` when available; the server reports failures instead of trying to bypass permissions.
Some firmware paths or APK package/activity names may differ; this release targets official
`org.xbmc.kodi`. File access remains constrained to that configured Kodi root.

## Development and verification

```sh
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/python -m build
```

Tests exercise real MCP stdio discovery/calls, HTTP auth/limits, redaction, busy/offline guards, active
profile resolution, patch conflict handling, backup integrity/restore and staged layout expiry.
APK tests cover mismatched signatures/CPU/SDK, stale previews, split-install sessions, failed
readback, interrupted transfers and Kodi snapshot refusal. APK inspection uses official SDK tools;
Android still performs its own verification when installing. `shield_connection` and `--doctor`
distinguish ADB authorization from Kodi HTTP/Manager credentials and service availability.
CI tests Python 3.11–3.13 on Linux and Windows. Live validation is documented in
[verification](docs/verification.md). Alpha release: mock tests do not establish compatibility with
every Shield firmware, skin, add-on or MCP client. Contributions should include bounded, reproducible
checks and avoid private logs, credentials, screenshots or full Kodi backups.

Built on the [official MCP Python SDK v1 maintenance line](https://github.com/modelcontextprotocol/python-sdk/tree/v1.x),
[Android ADB](https://developer.android.com/tools/adb) and
[Kodi JSON-RPC](https://kodi.wiki/view/JSON-RPC_API/v13). MIT licensed. Not affiliated with NVIDIA or Kodi.
