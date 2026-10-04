# nvidia-MCP

A local MCP server for **NVIDIA Shield TV and Kodi**. Give an MCP-compatible assistant the tools to
inspect a Shield, diagnose Kodi problems, preview add-on folders, adjust settings and apply reversible
repairs. It runs on your Mac, Windows PC or Linux computer and connects to your own Shield over your LAN.

Built from real Shield/Kodi troubleshooting: playback interruption guards, separate profile handling,
version checks, redacted diagnostics, exact file patches and rollback backups. No cloud account is needed.

## Quick start

You need Python 3.11+, [Android Platform Tools](https://developer.android.com/tools/releases/platform-tools)
for ADB features, and a Shield on the same trusted LAN.

1. Enable **network debugging** in the Shield's developer options. Connect once with
   `adb connect YOUR_SHIELD_IP:5555` and approve the debugging prompt on the TV.
2. In Kodi, enable **Settings → Services → Control → Allow remote control via HTTP**.
   Set a username/password and note the port (usually 8080). ADB and Kodi HTTP are separate connections.
3. Install on your computer:

```sh
git clone https://github.com/glasgowm148/nvidia-MCP.git
cd nvidia-MCP
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

On Windows use `py -3 -m venv .venv`, then `.venv\Scripts\python.exe -m pip install -e .`.
ADB must be on the MCP client's PATH, or set `ADB_PATH` to its full executable path.

4. Add a **stdio** MCP server to your client. This is the Claude Desktop / Cursor JSON shape;
   other clients have their own wrapper around the same command, arguments and environment:

```json
{
  "mcpServers": {
    "nvidia-MCP": {
      "command": "/absolute/path/nvidia-MCP/.venv/bin/nvidia-mcp",
      "env": {
        "SHIELD_HOST": "192.168.1.50",
        "KODI_PORT": "8080",
        "KODI_USERNAME": "kodi",
        "KODI_PASSWORD": "YOUR_LOCAL_KODI_PASSWORD"
      }
    }
  }
}
```

On Windows the command is `C:\\absolute\\path\\nvidia-MCP\\.venv\\Scripts\\nvidia-mcp.exe`.
The server reads environment variables, **not `.env` automatically**. Keep filled client configs private.
Restart the MCP client/server after changing configuration. See [examples](examples/claude-desktop.json).

5. Ask: **“Read the Shield repair playbook and audit Kodi without interrupting anything.”**

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
| Bingie | saved layout/sources, preview, apply, rebuild | optional existing Kodi Manager 0.3.9 |

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

If you **already run Kodi Manager 0.3.9** (`service.kodi.addonadmin`), configure:

```json
"KODI_MANAGER_PORT": "8765",
"KODI_MANAGER_TOKEN": "YOUR_EXISTING_LOCAL_MANAGER_TOKEN"
```

Use its authenticated layout endpoint to read the actual menu/hub mapping, preview a complete section
plan, then apply the returned preview ID. The preview expires after 10 minutes and cannot be edited
between preview and apply. Manager creates its own backup and checks the expected layout revision.
The adapter supports the Manager's reviewed **Bingie 2.0.2 / Skin Shortcuts 2.0.3** sources; unknown
versions/forks remain view-only. Enable Manager's own write mode for live writes.

**Kodi Manager is optional and is not bundled or installed by this repository.** Without it, all core
Shield/Kodi diagnostics, profile-aware file access, offline repairs/settings and directory previews
work. Direct live Bingie layout editing and pipeline inspection require that separate existing service.
This initial release does not install APKs/add-ons, manage Trakt/debrid accounts or migrate cloud
history. It also does not automatically apply household-specific settings or provider/skin patches.

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
