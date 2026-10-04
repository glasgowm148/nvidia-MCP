# nvidia-MCP

A local MCP server for **NVIDIA Shield TV and Kodi**. Give an MCP-compatible assistant the tools to
inspect a Shield, diagnose Kodi problems, preview add-on folders, adjust settings and apply reversible
repairs. It runs on your Mac, Windows PC or Linux computer and connects to your own Shield over your LAN.

Built from real Shield/Kodi troubleshooting: playback interruption guards, separate profile handling,
version checks, redacted diagnostics, exact file patches and rollback backups. No cloud account is needed.

## Quick start

You need Python 3.11+, [Android Platform Tools](https://developer.android.com/tools/releases/platform-tools)
for ADB features, and a Shield on the same trusted LAN.

New to ADB or MCP? Follow the [step-by-step setup guide](docs/setup.md) for Mac, Windows and Linux,
including downloads, where to type commands, connection checks and troubleshooting.

1. **On the TV, find the Shield's IP and enable debugging.** Press **Home** on the Shield remote,
   open the **Settings gear → Device Preferences → About → Status → IP address** and write down
   its local IPv4 address, for example `192.168.1.50`. Use your Shield's address, not your computer's.
   Then return to **About**, highlight **Build**, and press the remote's centre/select button **seven
   times** until developer mode is enabled. Go back to **Device Preferences → Developer options**,
   scroll to **Debugging**, and turn **Network debugging** on. Older firmware may put **About**
   directly under Settings.
2. **On your computer, connect ADB.** Download and extract Google's Platform Tools, then open
   **Terminal** on Mac/Linux or **PowerShell** on Windows. From the extracted `platform-tools` folder,
   run `./adb connect YOUR_SHIELD_IP:5555` on Mac/Linux or
   `.\adb.exe connect YOUR_SHIELD_IP:5555` on Windows. Replace `YOUR_SHIELD_IP` with the address
   from step 1. On the TV, approve the debugging prompt for this computer. Run `./adb devices`
   (Windows: `.\adb.exe devices`); your Shield should appear with status **`device`**.
3. **Inside Kodi on the TV**, open **Settings → Services → Control**. Enable **Allow remote control
   via HTTP** and **Require authentication**, set a username/password, and note the port (usually
   `8080`). Keep Kodi open. On your computer, open `http://YOUR_SHIELD_IP:8080` in a browser and
   sign in with those credentials to check the connection. ADB and Kodi HTTP are separate connections.
4. Install this project **on your computer**, in a new terminal window:

```sh
git clone https://github.com/glasgowm148/nvidia-MCP.git
cd nvidia-MCP
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

On Windows use `py -3 -m venv .venv`, then `.venv\Scripts\python.exe -m pip install -e .`.
ADB must be on the MCP client's PATH, or set `ADB_PATH` to its full executable path.

5. Add a **stdio** MCP server to your client. This is the Claude Desktop / Cursor JSON shape;
   other clients have their own wrapper around the same command, arguments and environment:

```json
{
  "mcpServers": {
    "nvidia-MCP": {
      "command": "/absolute/path/nvidia-MCP/.venv/bin/nvidia-mcp",
      "env": {
        "SHIELD_HOST": "192.168.1.50",
        "ADB_PATH": "/absolute/path/platform-tools/adb",
        "KODI_PORT": "8080",
        "KODI_USERNAME": "kodi",
        "KODI_PASSWORD": "YOUR_LOCAL_KODI_PASSWORD"
      }
    }
  }
}
```

On Windows the command is `C:\\absolute\\path\\nvidia-MCP\\.venv\\Scripts\\nvidia-mcp.exe`.
Replace `SHIELD_HOST` with the Shield IP from step 1, `ADB_PATH` with the full path to your extracted
`adb` (Windows: `adb.exe`), and the Kodi credentials with those from step 3. Do not put `:5555` in
`SHIELD_HOST`. Use the full executable paths; desktop MCP clients may not inherit your terminal's PATH.
The server reads environment variables, **not `.env` automatically**. Keep filled client configs private.
Restart the MCP client/server after changing configuration. See [examples](examples/claude-desktop.json).

6. Ask: **“Read the Shield repair playbook and audit Kodi without interrupting anything.”**

For a terminal connection check, set the same environment variables and run `nvidia-mcp --doctor`.
This prints redacted Kodi connectivity data and exits. ADB can be unavailable while Kodi HTTP works,
and vice versa; `kodi_status` reports partial failures instead of pretending everything is connected.

## Tools

| Area | Tools | Needs |
|---|---|---|
| Shield diagnostics | status, installed packages, logcat, screenshot, connect | ADB |
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

The distribution includes a pinned **Kodi Manager 0.4.0 companion ZIP**. It is optional: core Shield,
Kodi HTTP, file and offline-repair tools work without it. Export it locally (no device connection or
`SHIELD_HOST` configuration required):

```sh
nvidia-mcp --export-manager ./companion
```

This prints the exported ZIP path and verified SHA-256; it does not install or restart anything.
Use Kodi's **Install from zip file** to install the ZIP when the TV is free, then configure the service's
LAN access, bind host and token. Follow the [companion setup guide](docs/companion.md).
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

MCP tools currently cover the table above. APK installation, cloud authorization/history migration
and distributable provider/skin repair recipes still need dedicated tools; the original household work
used scripts and browser flows for those actions. No household accounts or modified third-party
add-ons are included. See the [capability boundaries](docs/companion.md).

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `SHIELD_HOST` | required | Private LAN IP; one device per server instance |
| `SHIELD_ADB_PORT` | `5555` | Shield network debugging port |
| `ADB_PATH` | `adb` | Platform Tools executable |
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
CI tests Python 3.11–3.13 on Linux and Windows. Live validation is documented in
[verification](docs/verification.md). Alpha release: mock tests do not establish compatibility with
every Shield firmware, skin, add-on or MCP client. Contributions should include bounded, reproducible
checks and avoid private logs, credentials, screenshots or full Kodi backups.

Built on the [official MCP Python SDK v1 maintenance line](https://github.com/modelcontextprotocol/python-sdk/tree/v1.x),
[Android ADB](https://developer.android.com/tools/adb) and
[Kodi JSON-RPC](https://kodi.wiki/view/JSON-RPC_API/v13). MIT licensed. Not affiliated with NVIDIA or Kodi.
