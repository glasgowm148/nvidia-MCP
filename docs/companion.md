# Optional Kodi Manager companion

**Kodi Manager is the optional dashboard inside Kodi. nvidia-MCP runs on your computer.**
You can use core TV/Kodi diagnostics without Manager. Add it when you want the browser dashboard,
live add-on settings, playback pipeline or supported home-layout tools.

## Ask your agent to install Kodi Manager

- **Starting from scratch?**
  - Use [one prompt for both](setup.md#4-give-this-message-to-your-assistant--on-the-computer).
  - The agent sets up nvidia-MCP, verifies it, then continues with installing and connecting Manager.
- **Already have a working nvidia-MCP connection?**
  - Use the Manager-only request below.

- **Give the agent this request.**
  - It handles preparation, supported TV navigation and connection checks.
  - You may still need to select Kodi installer options or approve permission screens on the TV.

```text
Install Kodi Manager and connect it to my working nvidia-MCP setup.
Follow docs/companion.md. Check for an existing installation and preserve customizations.
Use the Kodi Manager repository and Kodi's native installer.
Handle downloads and supported TV navigation; ask me only for TV steps you cannot complete.
Obtain the active profile's token privately and verify read-only Manager access.
Leave write mode and provider browsing off when finished. Do not interrupt playback.
```

Already have Kodi Manager? The agent should connect it and avoid replacing a working installation.
If you only want the browser dashboard, use [the remote-control steps](https://github.com/glasgowm148/kodi-manager/blob/main/docs/setup.md#1-add-the-download-source--inside-kodi).

## 1. Install Kodi Manager — on the TV

For manual installation, or any TV steps your agent asks you to complete:

- **Add the source.**
  - Open **Kodi → Settings → File manager → Add source**.
  - **Address:** `https://glasgowm148.github.io/kodi-manager/`
  - **Name:** `Kodi Manager`
- **Install the repository.**
  - Enable **Settings → System → Add-ons → Unknown sources** if needed.
  - Open **Add-ons → open-box icon → Install from zip file**.
  - Select **Kodi Manager → repository.kodi-manager.zip** and wait for the installed notice.
- **Install Kodi Manager.**
  - Select **Install from repository → Kodi Manager Repository (preview)**.
  - Open **Services → Kodi Manager → Install**.

The [full remote-control guide](https://github.com/glasgowm148/kodi-manager/blob/main/docs/setup.md)
explains every screen. The repository supplies preview releases using Kodi's update settings.
Apple TV uses the same Kodi installation steps; its support remains experimental.

## 2. Open the dashboard — on the TV, then your browser

- **Enable dashboard access.**
  - Open **Settings → Add-ons → My add-ons → Services**.
  - Select **Kodi Manager → Configure → Dashboard**.
  - Turn on **Allow LAN access**, leave **Enable writes** off, then select **OK**.
- **Display the address and token.**
  - Return home. Open **Add-ons → Video add-ons → Kodi Manager**.
  - Select **Open the dashboard on another device**.
- **Sign in.**
  - Open the displayed address in a browser on your phone or computer.
  - Enter the token privately. Keep Kodi running.

If you only see Configure, use the
[token fallback](https://github.com/glasgowm148/kodi-manager/blob/main/docs/setup.md#only-configure-is-available).

## 3. Connect it to your assistant — on the computer

- **If the agent installed Manager:**
  - It should complete the connection checks below as part of the same request.
- **If Manager was already installed:**
  - Ask: **“Connect my existing Kodi Manager to nvidia-MCP and verify read-only access.”**
  - Give the token through private input if asked.

### Agent installation procedure

- **Inspect before installing.**
  - Reuse a supported existing Manager. Back up customizations before any requested replacement.
  - Check playback and foreground state before TV navigation; preserve the viewing guards.
- **Use Kodi's repository installer.**
  - Prefer the repository steps above so future updates stay inside Kodi.
  - On Android, an agent with authorized terminal/ADB access can download the repository installer
    from `https://glasgowm148.github.io/kodi-manager/repository.kodi-manager.zip` and stage it in
    Kodi-accessible storage, such as Downloads. This avoids asking the user to transfer the file.
  - Have Kodi install the repository ZIP, then install Manager from that repository. Use supported
    guarded navigation where available; otherwise give the user the exact file/menu to select.
  - Apple TV uses Kodi's network source; ADB transfer does not apply.
  - Do not copy an unpacked add-on behind Kodi's database or claim installation from a file copy alone.
- **Connect and verify.**
  - Complete the connection procedure below and confirm the active profile/version.
  - Only enable the write controls needed for authorized installation/navigation; leave write mode
    and provider browsing off when finished, as requested in the setup prompt.
  - Report any remaining TV action explicitly. Do not describe a staged ZIP as an installed service.

### Agent connection procedure

1. Reuse an existing supported Manager. MCP supports Manager 0.4+; widget-cache tools need 0.6+;
   Apple TV needs 0.7.17+. An older bundled ZIP is not an instruction to downgrade a working install.
2. Privately read `auth_token` from the active profile's
   `addon_data/service.kodi.addonadmin/settings.xml` through authorized storage access, without
   printing it. If unavailable, use the displayed token via private input. The redacted file tool
   cannot supply the raw token. Do not bypass Android storage permissions.
3. Merge `KODI_MANAGER_TOKEN` and, if changed, `KODI_MANAGER_PORT` into private client configuration.
   The default Manager port is `8765`. Preserve other servers/settings and reload the connection.
4. Verify read-only layout/pipeline access. LAN access changes apply without a Kodi restart.
   Android's `KODI_HTTP_ROUTE=forward` can keep Manager loopback-only for MCP access;
   Apple TV needs direct LAN access. A browser on another device needs LAN access enabled.
5. For requested writes, enable both Manager's **Enable writes** and `NVIDIA_MCP_ALLOW_WRITES=1`.
   Preview layouts before applying; provider browsing has its own opt-in.

## Offline or pinned ZIP installation

The MCP distribution bundles **Manager 0.7.23**, verified against its pinned SHA-256.
`nvidia-mcp --export-manager DIRECTORY` exports it on the computer without contacting the TV
and refuses to overwrite a different file. The agent can transfer it using authorized ADB
(Android only) or a Kodi-readable share, then identify the exact file for the TV installer.
Use **Add-ons → Install from zip file** to install it. Apple TV uses a network source.
Do not copy unpacked add-on files behind Kodi's database. Standalone ZIP updates are manual
unless the user also adds the repository; keep auto-update off when deliberately pinning a version.

Manager's token and write mode belong to the active Kodi profile. After switching profiles on the TV,
read that profile's token privately, update the client configuration and reload if necessary. A valid
Kodi HTTP password does not authenticate Manager. Never attach the token to a bug report.

Do not expose this bearer-authenticated HTTP service outside a trusted LAN. Filled client configs,
account data and backups stay private. Kodi Manager 0.4+ installations are supported (widget-cache tools need 0.6+); a
bundled ZIP is not an instruction to overwrite them or remove their separately installed custom fixes.

## Capability boundaries

| Capability | Where it is available |
|---|---|
| ADB diagnostics/control and Kodi file repairs | MCP core |
| Live Bingie layout/pipeline and schema settings | MCP with the companion |
| Browser dashboard, account/settings inspection and editing | Companion UI/API |
| User-selected local add-on ZIP install; config backup/restore | Companion UI/API; service write mode required |
| Offline schema parsing and an authenticated client | Kodi Manager Python library |
| Verified local APK preview/install and private recovery bundles | MCP core; optional official SDK Build Tools required |
| Cloud account OAuth/history migrations; native TV-code remote pairing | Follow-up tools; not yet exposed by MCP |
| Household provider/skin patches | Not shipped; require separately reviewed, version-checked recipes |

Account setting controls are not cloud-account signup/OAuth. Installing a provider is not authorization
to access content/accounts. The public companion does not reproduce the original household settings.
Layout writes require reviewed **Bingie 2.0.2 / Skin Shortcuts 2.0.3 source hashes**.
Unknown Bingie/Shortcuts source versions stay view-only; source fingerprints gate actual layout writes.

## Updating the bundle

Release Kodi Manager first, then verify its companion ZIP checksum and review its changes. Copy that
exact release artifact into `src/nvidia_mcp/companion/`, update `manifest.json` version/source/SHA-256,
and run the export/integrity tests and wheel/sdist builds. Include the companion ZIP, checksum and
optional library wheel with the MCP release. Do not edit the bundled ZIP as a second source tree.

## Optional diagnostics capability

Development Manager builds can advertise operation-record/support-bundle v1. See
[operation diagnostics](operation-records.md) for correlation, redaction and ambiguous write
outcomes. `shield_get_support_bundle` negotiates this capability; the pinned 0.7.23 companion remains
supported for its existing APIs and does not provide this optional bundle.
