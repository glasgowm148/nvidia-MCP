# Optional Kodi Manager companion

**Kodi Manager is the optional dashboard inside Kodi. nvidia-MCP runs on your computer.**
You can use core TV/Kodi diagnostics without Manager. Add it when you want the browser dashboard,
live add-on settings, playback pipeline or supported home-layout tools.

## 1. Install Kodi Manager — on the TV

If Kodi Manager is already installed and working, keep it and continue at step 2.
Back up private modifications before choosing to upgrade a customized installation.

1. Open **Kodi → Settings → File manager → Add source**.
2. Enter `https://glasgowm148.github.io/kodi-manager/` and name it **Kodi Manager**.
3. Enable **Settings → System → Add-ons → Unknown sources** if needed.
4. Return to **Add-ons**, open the **open-box icon**, then select **Install from zip file →
   Kodi Manager → repository.kodi-manager.zip**. Wait for the repository-installed notice.
5. Select **Install from repository → Kodi Manager Repository (preview) → Services → Kodi Manager → Install**.

See [the full Kodi Manager guide](https://github.com/glasgowm148/kodi-manager/blob/main/docs/setup.md)
for every menu step. The repository supplies preview releases and uses Kodi's update settings.
These steps also apply inside Kodi on Apple TV, where support remains experimental.

## 2. Open the dashboard — on the TV, then your browser

1. Open **Settings → Add-ons → My add-ons → Services → Kodi Manager → Configure → Dashboard**.
2. Turn on **Allow LAN access**, leave **Enable writes** off, then select **OK**.
3. Return to Kodi's home screen. Open **Add-ons → Video add-ons → Kodi Manager**.
4. Select **Open the dashboard on another device**. The TV shows an address and access token.
5. Open the address in a browser on your phone/computer and enter the token privately.

Keep Kodi running. If you only see Configure, use the
[token fallback](https://github.com/glasgowm148/kodi-manager/blob/main/docs/setup.md#only-configure-is-available).

## 3. Connect it to your assistant — on the computer

Complete [nvidia-MCP setup](setup.md) first, then tell your assistant:

```text
Connect my existing Kodi Manager installation to nvidia-MCP.
Follow docs/companion.md. Obtain the active profile's token privately,
preserve my existing configuration and verify read-only Manager access.
Keep write mode and provider browsing off.
```

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
outcomes. `shield_support_bundle` negotiates this capability; the pinned 0.7.23 companion remains
supported for its existing APIs and does not provide this optional bundle.
