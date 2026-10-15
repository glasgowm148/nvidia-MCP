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
  <a href="#one-prompt-for-both">Agent setup prompt</a> ·
  <a href="#what-you-can-do">Features</a> ·
  <a href="#optional-kodi-manager-companion">Kodi Manager</a> ·
  <a href="#documentation">Documentation</a>
</p>

**Local assistant tools for Kodi and your TV.** nvidia-MCP runs on your computer and lets an MCP
assistant inspect Kodi, diagnose playback problems, preview repairs and apply changes with backups.
It uses public ADB and Kodi HTTP interfaces on NVIDIA Shield, Android TV, Google TV and Android-based
Fire TV. Apple TV support is experimental. No cloud account is required for the server.

**Start here:** [Copy the guided setup prompt](#one-prompt-for-both).
You do not need the TV's IP yet; the agent explains where to find it.

> [!NOTE]
> **0.5.10 prerelease.** Read-only by default. Live evidence comes from one customized Shield;
> Fire OS, Google TV and Apple TV hardware validation is pending. See [compatibility](docs/compatibility.md).

## What you can do

- Inspect Kodi's version, profile, skin, add-ons, playback state and redacted logs.
- Diagnose Android apps, connection readiness and native crashes; capture the TV screen.
- Preview configuration repairs, then apply and undo them with checksum checks and private backups.
- Inspect and upgrade local Android APKs with optional SDK tooling and recovery bundles.
- Use optional [Kodi Manager](#optional-kodi-manager-companion) for live settings, playback routing,
  cached rows, configuration checkpoints and reviewed Bingie layouts.

The `nvidia://playbook` resource and `audit_kodi` prompt guide focused audits.
See the [tool reference](docs/tools.md) for each tool's access requirements and limits.

## Quick start

You need a computer, an assistant app that supports **local MCP tools**, and a TV on the same
home network. Your assistant needs permission to run commands and edit files on the computer;
it installs Python 3.11+ and other tools if needed. A browser chat alone cannot do this setup.

1. **Give your agent one prompt.**
   - Copy the [complete setup request](#one-prompt-for-both) below.
   - No IP address or technical checklist is needed before you start.
2. **Answer the agent's questions.**
   - It asks which TV/device you use and gives the matching menu steps.
   - It explains how to find the IP, enable debugging where applicable, and enable Kodi remote control.
   - Reply after each step; the agent waits before continuing.
3. **Approve the connection and let setup finish.**
   - Select **Allow** on the TV when asked, or enter a pairing code through private input.
   - The agent verifies nvidia-MCP, then installs and connects Kodi Manager.
   - Once it confirms both work, ask: **“Read the Kodi repair playbook and audit Kodi without interrupting anything.”**

### One prompt for both

Use an assistant that can run commands, edit files and use local MCP tools on your computer.
Have Kodi installed, keep your TV remote handy, and connect the TV and computer to the same home network.

- **Copy and paste.**
  - Expand **Show the setup prompt to copy** below and copy the whole text box into your agent.
  - No editing is needed. **You do not need to know the TV's IP address yet.**
- **Follow the conversation.**
  - The agent asks which TV you have, then explains the relevant settings and IP-address menus.
  - Reply after each step. It waits for missing details and permission prompts before continuing.
  - One prompt starts the setup; you will still answer questions and use the TV remote when needed.

<details>
<summary><strong>Show the setup prompt to copy</strong></summary>

```text
Help me set up nvidia-MCP on this computer, then install and connect
Kodi Manager on my TV:
https://github.com/glasgowm148/nvidia-MCP
https://github.com/glasgowm148/kodi-manager

Read nvidia-MCP's docs/agent-setup.md and docs/companion.md first.
If not already known, first ask which TV/device I use. Do not assume I
know its IP address or have enabled debugging. Ask one short question
at a time. Explain the exact menus for my device, what to select and
what information to read back. Guide my device's TV preparation, including
debugging where applicable, finding its IP and enabling Kodi HTTP control.
For Apple TV, use the separate tvOS instructions. If a menu differs,
ask what I see. Wait for my reply before moving to the next TV step.
Do not invent connection details or scan my network.

Once TV preparation is ready:
1. Install and configure nvidia-MCP. Verify the actual MCP connection
   can read my TV and Kodi before continuing.
2. Install Kodi Manager from https://glasgowm148.github.io/kodi-manager/
   using Kodi's native installer. Reuse supported existing installations
   and back up customizations before any replacement.
3. Connect the active profile's Manager token privately. Enable dashboard
   LAN access, give me its browser address and verify read-only Manager access.

Handle computer commands, downloads and supported TV navigation yourself.
Ask me for details or TV actions your tools cannot obtain or complete.
Request passwords, tokens and pairing codes only through private input.
Preserve my other MCP servers and settings. Target only my specified TV
and never interrupt playback. Enable only writes needed for setup;
finish with write mode and provider browsing off.
Continue both setup stages in this conversation, waiting for my replies
whenever information or permission is needed.
```

</details>

- **Full instructions**
  - [TV menu steps](docs/setup.md), if you prefer to prepare the TV yourself.
  - [Firestick / Fire TV](docs/android-tv.md#fire-tv--firestick-fire-os),
    [Shield](docs/android-tv.md#nvidia-shield) and
    [Android TV / Google TV](docs/android-tv.md#android-tv--google-tv).
  - [Apple TV setup](docs/apple-tv.md), experimental.
  - [Troubleshooting](docs/troubleshooting.md).

Vega OS Firesticks are unsupported; check the [device guide](docs/android-tv.md).

## How it connects

```mermaid
flowchart LR
    A[Your assistant] -->|MCP · stdio| B[nvidia-MCP on your computer]
    B -->|ADB + Kodi HTTP| C[Android TV or Fire OS / Kodi]
    B -.->|Optional settings and layout API| D[Kodi Manager inside Kodi]
```

Each server instance targets one explicitly configured device. Apple TV uses an opt-in backend and
separate configuration. Credentials and recovery files stay in your private local storage.

## Optional Kodi Manager companion

[Kodi Manager](https://github.com/glasgowm148/kodi-manager) runs inside Kodi and adds a browser dashboard,
live add-on settings, playback pipeline inspection and supported Bingie layout editing.

![Kodi Manager overview with six device and service status cards](docs/images/manager-dashboard.png)

<details>
<summary>Playback setup: routing, scraper connections and integrations</summary>

![Kodi Manager playback setup showing the skin, metadata helper, selected player, routing evidence and account integrations](docs/images/manager-pipeline.png)

</details>

*Current optional companion UI, captured with synthetic demo data in view-only mode. The MCP server itself is a stdio service.*

- **Already using nvidia-MCP?**
  - Ask your agent: **“Install Kodi Manager and connect it to nvidia-MCP.”**
  - Follow [agent-assisted setup](docs/companion.md#ask-your-agent-to-install-kodi-manager).
- **Only want the browser dashboard?**
  - Follow [Kodi Manager's TV remote steps](https://github.com/glasgowm148/kodi-manager/blob/main/docs/setup.md#1-add-the-download-source--inside-kodi).
  - Install from its Kodi repository; no computer file transfer is needed.
- **Need an offline or pinned version?**
  - Use the [bundled ZIP instructions](docs/companion.md#offline-or-pinned-zip-installation).

Repository installations receive preview updates through Kodi's update settings.

## Making changes

**Writes and provider browsing have separate opt-ins.** Inspect and preview before enabling changes.
Disruptive tools check playback and the foreground app; unknown viewing state blocks them. Manager
writes also require its own write mode. Layout editing requires reviewed Bingie / Skin Shortcuts
versions **and source hashes**; unknown variants stay view-only.

Use a trusted LAN and keep credentials, logs and backups private. Repair tools have platform-specific
limits; the optional Android profile-relaunch helper needs separate private deployment.
See [operation rules](docs/configuration.md), [repair workflows](docs/repairs.md),
[APK recovery](docs/apk-upgrades.md) and [Apple TV limits](docs/apple-tv.md).

## Tool reference

The complete [generated tool catalogue](docs/tools.md) lists Android/Shield tools and access gates.
Apple TV has a separate [capability table](docs/apple-tv.md#what-matches-the-shield-workflow).

## Documentation

Start with the [documentation index](docs/README.md), or go directly to:

| I want to… | Guide |
| --- | --- |
| Set up a TV and assistant | [TV preparation](docs/setup.md) · [Agent setup](docs/agent-setup.md) |
| Connect Android / Fire TV or Apple TV | [Android / Fire OS](docs/android-tv.md) · [Apple TV](docs/apple-tv.md) |
| Use the dashboard and live settings | [Kodi Manager companion](docs/companion.md) |
| Configure access or repair a problem | [Configuration](docs/configuration.md) · [Repairs](docs/repairs.md) |
| Check support or reuse the Python code | [Compatibility](docs/compatibility.md) · [Library](docs/library.md) |

[Contributing](CONTRIBUTING.md) · [Changelog](CHANGELOG.md) · [Security](SECURITY.md) · [MIT license](LICENSE).
Independent project; not affiliated with NVIDIA, the Kodi Foundation or any add-on author.
