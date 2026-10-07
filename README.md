<p align="center">
  <img src="docs/images/banner.svg" alt="nvidia-MCP — Your Shield. Your assistant. Local control." width="100%">
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

**Local MCP tools for NVIDIA Shield TV and Kodi.** Give your assistant the tools to inspect your setup, diagnose playback problems, adjust settings and apply reversible repairs from your computer. Works over your home network on macOS, Windows and Linux, with an MCP client that supports stdio. No cloud account is required for the server.

> [!NOTE]
> **Alpha / prerelease.** Start with read-only access. See [tested compatibility](docs/compatibility.md)
> and [verification evidence](docs/verification.md) before using repair or upgrade tools.

## What you can do

| Task | What the assistant can inspect or do | Connection |
| --- | --- | --- |
| Diagnose the Shield | Connection readiness, installed apps, bounded logs and screenshots | ADB |
| Understand Kodi | Version, skin, active profile, playback state and installed add-ons | Kodi HTTP |
| Investigate playback | Read redacted logs and relevant profile settings | ADB or mounted storage |
| Explore widget sources | Preview one page of an installed add-on's folders | Kodi HTTP; browsing opt-in |
| Repair settings and files | Preview exact changes, check versions/checksums, back up and restore | File access; write mode |
| Upgrade an Android app | Inspect local APKs or split sets, preview installation, save recovery files | ADB + SDK Build Tools; write mode |
| Configure Bingie | Inspect hubs, preview layout changes and apply a reviewed plan | Optional Kodi Manager |

The bundled repair playbook covers profiles, audio, autoplay, source priorities, skin widgets and stale stream URLs. It helps distinguish **installed**, **enabled**, **configured** and **actually used**. It is available as the `nvidia://playbook` resource and `audit_kodi` prompt.

## Quick start

**You prepare the TV. Your agent handles the computer.** Use an agent with terminal/file access; the computer and Shield must be on the same home network.

### 1. Prepare the Shield and Kodi

| On the TV | Where to go | What to do |
| --- | --- | --- |
| Find the Shield IP | **Home → Settings gear → Device Preferences → About → Status → IP address** | Note the local IPv4 address, such as `192.168.1.50`. Use yours. |
| Unlock developer options | **Settings → Device Preferences → About → Build** | Press the remote's centre/select button **seven times**. |
| Enable network debugging | Back to **Device Preferences → Developer options → Debugging** | Turn **Network debugging** on. |
| Enable Kodi control | Inside Kodi: **Settings → Services → Control** | Enable **Allow remote control via HTTP** and **Require authentication**. Set a username/password and note the port, usually `8080`. |

Older firmware may put **About** directly under Settings. If Kodi hides the control options, select the **Standard** or **Expert** settings level. Leave the Shield awake and Kodi open. The [TV preparation guide](docs/setup.md) has full directions and troubleshooting.

### 2. Give this prompt to your agent

Replace the IP and port. Provide Kodi credentials privately when requested.

```text
Set up https://github.com/glasgowm148/nvidia-MCP on this computer.
Read docs/agent-setup.md and complete the computer setup automatically.
Shield network debugging and Kodi HTTP control are enabled.
Shield IP: YOUR_SHIELD_IP
Kodi HTTP port: 8080
Ask privately for the Kodi username/password if needed.
Install missing dependencies, connect ADB, preserve my existing MCP servers,
register nvidia-MCP and verify its read-only tools.
Tell me when to approve the debugging prompt on the TV.
Keep write mode and plugin browsing off; do not interrupt playback.
```
 The [agent setup guide](docs/agent-setup.md) covers dependency installation, private configuration and connection checks. You do not need to run commands or edit JSON yourself.

### 3. Approve the connection on the TV

When the agent connects, select **Allow** on the Shield's debugging prompt. Optionally select **Always allow from this computer** for your trusted computer. Tell the agent you have approved it.

Then try: **“Read the Shield repair playbook and audit Kodi without interrupting anything.”**

## How it connects

```mermaid
flowchart LR
    A[Your assistant] -->|MCP · stdio| B[nvidia-MCP on your computer]
    B -->|ADB + Kodi HTTP| C[NVIDIA Shield / Kodi]
    B -.->|Optional live settings and layout API| D[Kodi Manager inside Kodi]
```
 The server targets **one configured Shield**. Core diagnostics and file repairs work without the companion. Credentials and recovery backups stay in your local configuration/storage.

## Optional Kodi Manager companion

[Kodi Manager](https://github.com/glasgowm148/kodi-manager) adds live add-on settings, playback pipeline inspection, a browser dashboard and supported Bingie layout editing. It also offers a standalone Python client/parser library.

![Kodi Manager dashboard showing add-on installation, enabled states and configuration](docs/images/manager-dashboard.png)

*Optional companion dashboard, captured from the public UI with synthetic demo data. The MCP server itself is a stdio service.*

The MCP distribution includes a pinned **Kodi Manager 0.6.2** ZIP (the public [v0.6.2 release](https://github.com/glasgowm148/kodi-manager/releases/tag/v0.6.2), checksum-verified). Your agent can export it with `nvidia-mcp --export-manager ./companion`, verify it and transfer it to the Shield. Install through Kodi's native **Install from zip file**, then let the agent configure the connection. Follow the [companion setup guide](docs/companion.md).

Kodi Manager 0.4+ is supported; the widget-cache tools need 0.6+. Older installations should be upgraded; back up customized installations before replacing them. Layout writes require reviewed **Bingie 2.0.2 / Skin Shortcuts 2.0.3 source hashes**; unknown variants remain view-only. Installing the Python library alone does not install the TV service.

## Making changes

**Read-only is the default.** Writes and plugin browsing have separate opt-ins. File/configuration changes use backups; disruptive tools check playback, and lifecycle tools also check the foreground Android app. An unknown playback state blocks disruptive changes. Remote-button input still needs permission from anyone using the TV.

Ask the agent to inspect and preview a change before enabling it. Live companion writes also need Manager's own write mode. See [configuration and operation rules](docs/configuration.md), [repair workflows](docs/repairs.md) and [APK upgrades](docs/apk-upgrades.md).

Cloud account signup/OAuth, Trakt history migrations and household provider/skin patches are not bundled. See the [capability boundaries](docs/companion.md#capability-boundaries).

## Documentation

| Guide | Use it for |
| --- | --- |
| [TV preparation](docs/setup.md) | Shield menus, IP address and first connection approval |
| [Agent setup](docs/agent-setup.md) | Computer installation, MCP registration and verification |
| [Configuration](docs/configuration.md) | Environment variables, storage and operation rules |
| [Kodi Manager](docs/companion.md) | Optional live settings, dashboard and Bingie integration |
| [Repairs](docs/repairs.md) · [APK upgrades](docs/apk-upgrades.md) | Preview, apply, verify and recover |
| [Compatibility](docs/compatibility.md) · [Verification](docs/verification.md) | Tested versions and remaining live checks |
| [Contributing](CONTRIBUTING.md) · [Changelog](CHANGELOG.md) | Development, release checks and changes |
| [Security](SECURITY.md) | Credential handling and private vulnerability reports |

Built on the [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk/tree/v1.x), [Android ADB](https://developer.android.com/tools/adb) and [Kodi JSON-RPC](https://kodi.wiki/view/JSON-RPC_API/v13).

---

[MIT license](LICENSE). Independent project; not affiliated with NVIDIA or Kodi.
