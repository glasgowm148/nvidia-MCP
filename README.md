<p align="center">
  <img src="docs/images/banner.svg" alt="nvidia-MCP — Your TV. Your assistant. Local control." width="100%">
</p>

<p align="center">
  <a href="https://github.com/glasgowm148/nvidia-MCP/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/glasgowm148/nvidia-MCP/ci.yml?branch=main&amp;style=flat-square&amp;label=CI" alt="CI status"></a>
  <a href="https://github.com/glasgowm148/nvidia-MCP/releases"><img src="https://img.shields.io/github/v/release/glasgowm148/nvidia-MCP?include_prereleases&amp;style=flat-square&amp;color=6ee7b7" alt="Latest release, including prereleases"></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/Python-3.11%2B-7dd3fc?style=flat-square" alt="Python 3.11 or newer"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-c4b5fd?style=flat-square" alt="MIT license"></a>
</p>

<p align="center">
  <a href="#quick-start">Quick start</a> ·
  <a href="#what-you-can-do">Features</a> ·
  <a href="#optional-kodi-manager-companion">Kodi Manager</a> ·
  <a href="#documentation">Documentation</a>
</p>

**Local MCP tools for Kodi on NVIDIA Shield, Android TV, Google TV and Android-based Fire TV.** Give your assistant the tools to inspect your setup, diagnose playback problems, adjust settings and apply reversible repairs from your computer. Works over your home network on macOS, Windows and Linux, with an MCP client that supports stdio. No cloud account is required for the server.

> [!NOTE]
> **Alpha / prerelease (0.4.9).** Start with read-only access. See [tested compatibility](docs/compatibility.md)
> and [verification evidence](docs/verification.md) before using repair or upgrade tools.

## What you can do

| Task | What the assistant can inspect or do | Connection |
| --- | --- | --- |
| Diagnose the TV | Connection readiness, installed apps, bounded logs and screenshots | ADB |
| Understand Kodi | Version, skin, active profile, playback state and installed add-ons | Kodi HTTP |
| Investigate playback | Read redacted logs and relevant profile settings | ADB or mounted storage |
| Explore widget sources | Preview one page of an installed add-on's folders | Kodi HTTP; browsing opt-in |
| Repair settings and files | Preview exact changes, check versions/checksums, back up and restore | File access; write mode |
| Upgrade an Android app | Inspect local APKs or split sets, preview installation, save recovery files | ADB + SDK Build Tools; write mode |
| Configure Bingie | Inspect hubs, preview layout changes and apply a reviewed plan | Optional Kodi Manager |

The bundled repair playbook covers profiles, audio, autoplay, source priorities, skin widgets and stale stream URLs. It helps distinguish **installed**, **enabled**, **configured** and **actually used**. It is available as the `nvidia://playbook` resource and `audit_kodi` prompt.

## Quick start

**You prepare the TV. Your agent handles the computer.** Use an agent with terminal/file access; the computer and TV must be on the same home network.

### 1. Prepare your TV and Kodi

| Device | ADB preparation |
| --- | --- |
| NVIDIA Shield | Unlock Build with seven presses; enable Network debugging, normally port 5555 |
| Android TV / Google TV | Vendor Network debugging or paired Wireless debugging; use the displayed connection port |
| Fire TV / Firestick running Fire OS | My Fire TV → Developer Options → ADB Debugging, normally port 5555 |

Find the TV’s private IP, then inside Kodi enable **Settings → Services → Control → Allow remote
control via HTTP**, require authentication and note the port (usually 8080). Leave Kodi open.
The [TV preparation guide](docs/setup.md) and [Android TV / Fire TV guide](docs/android-tv.md) give
menu steps and pairing instructions. **Vega OS Firesticks are unsupported**: check
[Amazon’s OS table](https://developer.amazon.com/docs/fire-tv/fire-os-overview.html).

### 2. Give this prompt to your agent

Replace the IP and port. Provide Kodi credentials privately when requested.

```text
Set up https://github.com/glasgowm148/nvidia-MCP on this computer.
Read docs/agent-setup.md and complete the computer setup automatically.
TV model / OS: YOUR_MODEL_AND_OS
ADB mode: network debugging or paired Wireless debugging
TV IP: YOUR_TV_IP
ADB connection port: YOUR_ADB_PORT
Kodi HTTP control is enabled.
Kodi HTTP port: 8080
Ask privately for the Kodi username/password if needed.
Install missing dependencies, connect ADB, preserve my existing MCP servers,
register nvidia-MCP and verify its read-only tools.
Tell me when to approve the debugging prompt on the TV.
Keep write mode and plugin browsing off; do not interrupt playback.
```
 The [agent setup guide](docs/agent-setup.md) covers dependency installation, private configuration and connection checks. You do not need to run commands or edit JSON yourself.

### 3. Approve the connection on the TV

When the agent connects, select **Allow** on the TV's debugging prompt. Optionally select **Always allow from this computer** for your trusted computer. Tell the agent you have approved it.

Then try: **“Read the Kodi repair playbook and audit Kodi without interrupting anything.”**

Use a computer-side MCP client that supports **local stdio servers** and an agent with computer
access for installation. A normal browser chat cannot launch this server by itself. No Python or
MCP server is installed on the TV. See [first-run troubleshooting](docs/troubleshooting.md) for
client, authorization, network and missing-tool problems.

## How it connects

```mermaid
flowchart LR
    A[Your assistant] -->|MCP · stdio| B[nvidia-MCP on your computer]
    B -->|ADB + Kodi HTTP| C[Android TV or Fire OS / Kodi]
    B -.->|Optional live settings and layout API| D[Kodi Manager inside Kodi]
```
 The server targets **one configured Android device**. The public ADB/Kodi interfaces need no proprietary connector. Legacy `shield_*` tool names remain
compatible; `ANDROID_TV_HOST` / `ANDROID_TV_ADB_PORT` also accept existing `SHIELD_*` names.
See [device support and evidence](docs/android-tv.md). Core diagnostics and file repairs work without the companion. Credentials and recovery backups stay in your local configuration/storage.

## Optional Kodi Manager companion

[Kodi Manager](https://github.com/glasgowm148/kodi-manager) adds live add-on settings, playback pipeline inspection, a browser dashboard and supported Bingie layout editing. It also offers a standalone Python client/parser library.

![Kodi Manager dashboard showing add-on installation, enabled states and configuration](docs/images/manager-dashboard.png)

*Optional companion dashboard, captured from the public UI with synthetic demo data. The MCP server itself is a stdio service.*

The MCP distribution includes a pinned **Kodi Manager 0.7.14** ZIP (built from the source commit pinned in the bundled manifest, checksum-verified). Your agent can export it with `nvidia-mcp --export-manager ./companion`, verify it and transfer it to the TV. Install through Kodi's native **Install from zip file**, then let the agent configure the connection. Follow the [companion setup guide](docs/companion.md).

Kodi Manager 0.4+ is supported; the widget-cache tools need 0.6+. Older installations should be upgraded; back up customized installations before replacing them. Layout writes require reviewed **Bingie 2.0.2 / Skin Shortcuts 2.0.3 source hashes**; unknown variants remain view-only. Installing the Python library alone does not install the TV service.

## Making changes

**Read-only is the default.** Writes and plugin browsing have separate opt-ins; without write mode the write tools are not even listed. File/configuration changes use backups. Every disruptive tool checks Kodi playback, Android media sessions (background audio too) and the foreground Android app, so a Home press is refused while Netflix or SmartTube is in front; an unknown state blocks the change. "Interrupt anyway" flags also need `NVIDIA_MCP_ALLOW_INTERRUPT=1`, and stopping a Kodi whose HTTP server does not answer needs `NVIDIA_MCP_ALLOW_OFFLINE_RECOVERY=1`. Security and service settings (web server, unknown sources, master lock...) cannot be changed by an agent, and new APK signers must be trusted in your own configuration.

Ask the agent to inspect and preview a change before enabling it. Live companion writes also need Manager's own write mode. See [configuration and operation rules](docs/configuration.md), [repair workflows](docs/repairs.md) and [APK upgrades](docs/apk-upgrades.md).

Cloud account signup/OAuth, Trakt history migrations and household provider/skin patches are not bundled. See the [capability boundaries](docs/companion.md#capability-boundaries).

## Tool reference

*Write mode* tools exist only when `NVIDIA_MCP_ALLOW_WRITES=1`; without it the server lists 23
tools. *No TV changes* tools write only private local state or run opt-in, idle-only reads.

<!-- tools:start (generated by scripts/gen_tool_docs.py; do not edit) -->
| Tool | Title | Access | What it does |
| --- | --- | --- | --- |
| `kodi_addon_settings` | Add-on settings | read-only | Search/page redacted settings in the active profile; Manager includes schema/defaults, otherwise saved XML only. |
| `kodi_addons` | Kodi add-ons | read-only | List installed add-on IDs, versions and enabled states; enabled is not proof of use/authentication. |
| `kodi_backup_file` | Back up Kodi file | read-only | Save a private local rollback snapshot of one Kodi file. Does not modify the TV. |
| `kodi_backups` | Kodi file backups | read-only | List the latest 50 private per-file snapshots without exposing their contents. |
| `kodi_browse` | Browse Kodi folder | no TV changes | Preview one page of actual provider/library folders; opt-in, idle-only. Runs the add-on's own code, which contacts its provider and can show notifications or dialogs on the TV. Routes with play/auth/settings/maintenance verbs are refused. |
| `kodi_layout_apply` | Apply hub layout | write mode | Optional Manager: apply the exact staged plan within 10 minutes, changing the household's home-screen rows; Manager backs up and rejects stale revisions. |
| `kodi_layout_preview` | Preview hub layout | no TV changes | Optional Manager: stage existing section rows with section_id and expected_revision; no layout write. |
| `kodi_layout_rebuild` | Rebuild skin menus | write mode | Optional Manager: request one skin-menu rebuild while Kodi is idle and in front. The skin reloads visibly on the TV a few seconds later (after the only check). Inspect TV after it finishes. |
| `kodi_lifecycle` | Start/stop Kodi | write mode | Start/stop/restart Kodi (closes Kodi on the TV). Stop asks Kodi to quit and waits up to 30 s; a hung exit is force-stopped only after kodi.log shows settings saved and the TV guard passes, otherwise reported as exit_hung. Always refuses while Kodi plays or is paused; offline recovery (HTTP unreachable, Android shows no Kodi media) needs allow_offline_recovery plus the user's NVIDIA_MCP_ALLOW_OFFLINE_RECOVERY=1. interrupt_other_app overrides only another app in front or playing and needs NVIDIA_MCP_ALLOW_INTERRUPT=1. |
| `kodi_logs` | Kodi log tail | read-only | Inspect redacted Kodi log tail and crash/stream/storage signals; safe while viewing. |
| `kodi_manager_inspect` | Kodi Manager inspect | read-only | Optional Kodi Manager 0.4+: inspect saved skin hubs/rows, sources, pipeline, health or fix status. |
| `kodi_manager_widget_cache` | Kodi Manager widget cache | read-only | Optional Kodi Manager 0.6+: widget-cache status and cached rows for faster rows on any skin. |
| `kodi_manager_widget_cache_refresh` | Refresh widget cache | write mode | Optional Kodi Manager 0.6+: queue a refresh of every cached widget row while Kodi is idle and no other app is in front. Runs each row's add-on in the background on the TV (CPU and network load for a while). |
| `kodi_patch_apply` | Apply Kodi file patch | write mode | Apply the edits from kodi_patch_preview. Needs Kodi stopped and a matching SHA; creates an automatic backup. |
| `kodi_patch_file` | Patch Kodi file (deprecated) | write mode | Deprecated: use kodi_patch_preview and kodi_patch_apply. dry_run=true previews, false applies. |
| `kodi_patch_preview` | Preview Kodi file patch | read-only | Validate exact before/after replacements and return a redacted unified diff. Credential edits and add-on .py files are refused. No write. |
| `kodi_read` | Kodi JSON-RPC read | read-only | Run an allowlisted diagnostic JSON-RPC query (library reads default to 50 items, max 500, and shrink the page to fit 250 KB; other results over 250 KB are refused). No arbitrary RPC, executebuiltin or playback calls. |
| `kodi_read_file` | Read Kodi file | read-only | Read a Kodi-relative text file (600 KB max) with redaction and original SHA-256. |
| `kodi_restore_file` | Restore Kodi file | write mode | Restore one snapshot while Kodi is stopped; rejects stale checksums and creates an undo snapshot. |
| `kodi_set_addon_setting` | Change add-on setting | write mode | Change a non-credential setting on a verified add-on version; backed up. Without Manager, stop Kodi first. |
| `kodi_set_setting` | Change Kodi setting | write mode | Change one ordinary Kodi setting through its runtime API (takes effect on the TV at once), with a guisettings.xml rollback snapshot. Credential, security/service, display, audio-device, refresh-rate and language settings are refused, as is any change during playback or with another app in front. |
| `kodi_settings` | Kodi settings | read-only | Search/page Kodi's expert settings with current/default values, avoiding a whole-schema dump. |
| `kodi_status` | Kodi status | read-only | Inspect Kodi version, skin, current profile/window and active players; no playback changes. |
| `shield_apk_apply` | Install previewed APK | write mode | Install an exact unexpired APK preview, replacing the installed app. Stopped target/idle TV, backup and readback required; reports progress. The install can take minutes after the last TV check, and an app opened meanwhile is closed by Android. Never uninstalls/downgrades/retries. |
| `shield_apk_backups` | APK recovery bundles | read-only | List private APK recovery bundles for this TV, with phases and Kodi data snapshot checksums. |
| `shield_apk_preview` | Preview APK upgrade | no TV changes | Stage 1–20 local APKs, verify SDK/ABI/signers and save the installed originals (pulls up to 1 GB from the TV over the network; refused while any media is playing or paused). New apps need signers configured in NVIDIA_MCP_TRUSTED_SIGNERS; trusted_signers can only narrow that set. No TV changes. |
| `shield_apk_status` | APK recovery bundle status | read-only | Report one recovery bundle's phase, saved files and the version now installed on the TV. |
| `shield_apps` | Installed Android apps | read-only | List installed Android package names (no app/account data). |
| `shield_connect` | Connect ADB | no TV changes | Connect ADB to the configured TV only. A new or revoked authorization shows Android's debugging prompt on the TV over whatever is playing; someone at the TV must accept it. |
| `shield_connection` | TV connection check | read-only | Probe ADB, Kodi HTTP and optional Manager separately; explain authorization/readiness failures. |
| `shield_logcat` | Android log tail | read-only | Read a bounded Android log tail for native crashes. Redaction is best effort. |
| `shield_remote` | Remote button | write mode | Send one remote button while nothing plays (Kodi or any app's media) and Kodi, the home screen or a screensaver is in front; refused while the TV sleeps. play_pause/stop need allow_during_playback (plus the user's NVIDIA_MCP_ALLOW_INTERRUPT=1) and go to Kodi's player when it is playing. |
| `shield_screenshot` | TV screenshot | read-only | Capture the current TV screen without navigation. Screens can contain private information. |
| `shield_status` | Android TV status | read-only | Inspect device model, Android, memory/storage, uptime, thermal/throttling and Kodi process. |
<!-- tools:end -->

## Documentation

| Guide | Use it for |
| --- | --- |
| [TV preparation](docs/setup.md) | Device menus, IP address and first connection approval |
| [Agent setup](docs/agent-setup.md) | Computer installation, MCP registration and verification |
| [Configuration](docs/configuration.md) | Environment variables, storage and operation rules |
| [Kodi Manager](docs/companion.md) | Optional live settings, dashboard and Bingie integration |
| [Repairs](docs/repairs.md) · [APK upgrades](docs/apk-upgrades.md) | Preview, apply, verify and recover |
| [Compatibility](docs/compatibility.md) · [Verification](docs/verification.md) | Tested versions and remaining live checks |
| [Library API](docs/library.md) | Reusing the Shield/Kodi device code from your own Python tools |
| [Contributing](CONTRIBUTING.md) · [Changelog](CHANGELOG.md) | Development, release checks and changes |
| [Security](SECURITY.md) | Credential handling and private vulnerability reports |

Built on the [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk/tree/v1.x), [Android ADB](https://developer.android.com/tools/adb) and [Kodi JSON-RPC](https://kodi.wiki/view/JSON-RPC_API/v13).

---

[MIT license](LICENSE). Independent project; not affiliated with NVIDIA or Kodi.

The [optional account-switch source kit](contrib/profile-relaunch/README.md) preserves the tested Kodi 22 beta 2 / RC1 workaround. It requires a private per-device build and explicit installation; MCP does not deploy it automatically.
