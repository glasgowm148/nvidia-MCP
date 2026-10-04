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

Complete [TV preparation](setup.md) and [agent computer setup](agent-setup.md) first. The agent handles
the computer work below; the user only needs TV actions the agent cannot perform through its tools.

1. **Agent:** check for an existing supported Manager before proposing installation/replacement. Back
   up a previous customized installation if an upgrade is requested. Export with the installed server's
   `--export-manager` command, or download/verify the release ZIP and checksum.
2. **Agent:** transfer the ZIP to Kodi-accessible storage, using the configured Shield's authorized ADB
   or mounted share. Tell the user its exact location/name on the TV.
3. **TV:** use **Add-ons → Install from zip file** and select the transferred ZIP. Enable Unknown
   sources in Kodi's add-on settings if required. Do this while the TV is free. Use Kodi's native
   installer; copying an unpacked add-on behind Kodi's database is not the installation procedure.
4. **TV:** in **My add-ons → Services → Kodi Manager → Configure**, enable LAN access and set host
   `0.0.0.0`, port `8765`. Write mode starts off. The agent can perform TV navigation only when its tools
   permit it and the user has authorized that interaction.
5. **Agent:** restart the service/Kodi when viewing is finished and interruption is authorized. Privately
   read `auth_token` from the active profile's `addon_data/service.kodi.addonadmin/settings.xml` using
   available file access. Capture/parse it in a local process without printing it in tool output, then
   write it to private client configuration. It differs from Kodi HTTP credentials; MCP's redacted
   file-read output intentionally cannot supply its raw value.
6. **Agent:** merge `KODI_MANAGER_TOKEN` and optionally `KODI_MANAGER_PORT` into the private MCP client
   configuration, reload the connection and verify layout/pipeline reads. No user JSON editing is needed.
7. For requested changes, enable both the Manager service's write mode and `NVIDIA_MCP_ALLOW_WRITES=1`.
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
