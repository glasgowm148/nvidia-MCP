# First-run troubleshooting

Follow [TV preparation](setup.md), then let an agent with computer access perform
[agent setup](agent-setup.md). The MCP server runs on the computer; Kodi Manager runs inside Kodi.

| Symptom | Likely cause and next step |
| --- | --- |
| “Can I paste this into any AI chat?” | Your client must support local stdio MCP servers. A browser chat alone cannot start this process. The server is free; your chosen AI client/model may have its own charges. |
| MCP server exits at startup | Verify Python 3.11+, installation into the intended virtual environment and `ANDROID_TV_HOST` (or legacy `SHIELD_HOST`) in the client's environment. The server does not load `.env` automatically. Use absolute executable paths; GUI apps often have a different PATH from your terminal. |
| ADB missing or permission denied | Install official Platform Tools, keep its companion files together, and set `ADB_PATH` to the executable. APK SDK tools are optional and unnecessary for ordinary Kodi diagnostics. |
| Android TV needs a pairing code | Follow [device pairing](android-tv.md#configure-and-pair); use `--pair-adb PAIRING_PORT` with the secret via private stdin, then connect the separate connection port. Enabling USB debugging alone does not open network ADB. |
| Firestick does not accept Android ADB/APKs | Check [Amazon’s OS table](https://developer.amazon.com/docs/fire-tv/fire-os-overview.html). Android-based Fire OS is in scope; Vega OS is unsupported. |
| ADB says connected, but tools report unauthorized | Keep the TV awake and select **Allow** on its debugging prompt. Verify targeted `adb -s IP:PORT get-state` returns `device`; “connected” alone does not prove authorization. |
| ADB is offline/unreachable after reboot | Check the TV’s debugging mode, current IP and connection port. Paired Wireless debugging ports can change. Reconnect only that configured device. A DHCP reservation can keep its address stable; backups are normally tied to its hardware serial. |
| ADB works; Kodi HTTP fails | Keep Kodi open and verify HTTP control, port, username/password. ADB and Kodi HTTP are independent. Check LAN permissions, VPN/firewall rules and guest-network isolation. Use `KODI_HTTP_ROUTE=forward` when an authorized ADB route works but direct HTTP is blocked. |
| Authentication denied | Kodi HTTP uses its username/password; Manager uses a separate bearer token from its active profile. `auto` does not hide auth errors by switching routes. |
| Manager tools say not configured | Core diagnostics work without the companion. For Manager APIs, install its service ZIP through Kodi and configure `KODI_MANAGER_TOKEN`; exporting its ZIP does not install it. See [companion](companion.md). |
| Manager stops working after a profile switch | Its token may have changed. Privately read the active profile's token, update the client environment and reload. Do not substitute the previous profile's settings. |
| Agent cannot find write tools | By default those tools are not registered. Set `NVIDIA_MCP_ALLOW_WRITES=1` only for requested changes and reload the MCP server. Manager also needs its own write mode. Browsing uses a separate opt-in. |
| Writes/browsing refuse even with permissions | Playing or paused media, another foreground app, unknown viewing state, or an action route can block the call. Check `shield_connection` and the bounded status. Do not override a viewer's playback merely to finish setup. |
| Layout is absent or view-only | Only reviewed Bingie / Skin Shortcuts source versions and hashes support writes. Other skins do not gain a generic layout editor. Settings and other diagnostics remain available. |
| Android denies Kodi file access | Scoped storage may restrict ADB on some firmware. Use an available mounted share via `KODI_MOUNT`; HTTP connectivity does not prove filesystem access. Alternative Kodi package names and other TV boxes are unverified. |
| Timed-out change | Inspect the current device state before retrying; the action may have completed. Never repeat a write automatically. |

`nvidia-mcp --doctor` reports ADB, Kodi HTTP and optional Manager separately. It probes the
configured device and services; it does not approve a TV prompt, scan for devices or fix credentials.
Keep the environment private and inspect only its redacted output.

Updates are manual: review a release, update the installed package/checkout in its existing virtual
environment, reload the client and verify read-only calls. Preserve existing MCP configuration and
private backups. Update an installed Manager separately through Kodi's native ZIP installer; the
bundled companion is a verified artifact, not an automatic replacement.

If it still fails, [open an issue](https://github.com/glasgowm148/nvidia-MCP/issues/new/choose) with
server version, client, OS/Python, TV model/OS/Android/Kodi versions, HTTP route, error category and brief
steps. Share only inspected, redacted snippets. Never include passwords, tokens, filled client
configuration, settings exports, backups, screenshots or raw logs.
