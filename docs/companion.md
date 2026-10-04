# Optional Kodi Manager companion

## Two runtimes

**nvidia-MCP runs on your computer** and offers bounded tools to your assistant. **Kodi Manager runs
inside Kodi** and supplies the live profile, settings, pipeline and skin APIs. Core MCP diagnostics and
offline repairs do not require it. Kodi Manager also has a Python client/parser library for applications
that want these APIs without MCP.

The bundled version is **0.4.0**, from the
[Kodi Manager repository](https://github.com/glasgowm148/kodi-manager). Its ZIP is present in the MCP
wheel/source distribution and as a separate release asset. `--export-manager DIRECTORY` checks the
pinned SHA-256, refuses to overwrite a different existing file and never connects to the Shield.

## Setup

1. Export with `nvidia-mcp --export-manager ./companion`, or download the ZIP/checksum from the release.
2. Copy the ZIP to Kodi-accessible storage; use **Add-ons → Install from zip file**. Enable Unknown
   sources in Kodi's add-on settings if required. Back up a previous customized Manager first.
3. In **My add-ons → Services → Kodi Manager → Configure**, enable LAN access and set host `0.0.0.0`,
   port `8765`. Default access is loopback only and write mode is off.
4. Restart the service/Kodi when viewing is finished. Open `http://YOUR_SHIELD_IP:8765` if you want
   the dashboard. Read the generated `auth_token` privately from the active profile's
   `addon_data/service.kodi.addonadmin/settings.xml`. This differs from Kodi HTTP credentials.
5. Add `KODI_MANAGER_TOKEN` and optionally `KODI_MANAGER_PORT` to your MCP client's environment;
   restart the MCP server. Ask it to inspect the actual skin layout and pipeline.
6. For changes, enable both the Manager service's write mode and `NVIDIA_MCP_ALLOW_WRITES=1`.
   Inspect a layout preview before applying its immutable preview ID. Plugin browsing has its own opt-in.

Do not expose this bearer-authenticated HTTP service outside a trusted LAN. Filled client configs,
account data and backups stay private. Existing Manager 0.3.9 installations are supported; a bundled
ZIP is not an instruction to overwrite them or remove their separately installed custom fixes.

## Capability boundaries

| Capability | Where it is available |
|---|---|
| ADB diagnostics/control and Kodi file repairs | MCP core |
| Live Bingie layout/pipeline and schema settings | MCP with the companion |
| Browser dashboard, account/settings inspection and editing | Companion UI/API |
| User-selected local add-on ZIP install; config backup/restore | Companion UI/API; service write mode required |
| Offline schema parsing and an authenticated client | Kodi Manager Python library |
| APK deployment, cloud account OAuth/history migrations | Follow-up tools; not yet exposed by MCP |
| Household provider/skin patches | Not shipped; require separately reviewed, version-checked recipes |

Account setting controls are not cloud-account signup/OAuth. Installing a provider is not authorization
to access content/accounts. The public companion does not reproduce the original household settings.
Unknown Bingie/Shortcuts source versions stay view-only; source fingerprints gate actual layout writes.

## Updating the bundle

Release Kodi Manager first, then verify its companion ZIP checksum and review its changes. Copy that
exact release artifact into `src/nvidia_mcp/companion/`, update `manifest.json` version/source/SHA-256,
and run the export/integrity tests and wheel/sdist builds. Include the companion ZIP, checksum and
optional library wheel with the MCP release. Do not edit the bundled ZIP as a second source tree.
