# Android TV, Google TV and Fire TV

nvidia-MCP uses **public Android ADB and Kodi JSON-RPC**, not an NVIDIA connector. The
server runs on your computer and targets one explicitly configured device. The repository,
package, command, `shield_*` MCP tool names and `nvidia://` resources keep their existing names
so current clients continue to work. Python users can import `AndroidTV` or the original `Shield`.

| Device | Connection | Support boundary |
| --- | --- | --- |
| NVIDIA Shield | Network debugging, normally port 5555 | Reference device tested live |
| Android TV / Google TV boxes | Vendor network debugging or Android Wireless debugging | Synthetic protocol/guard tests; hardware validation still needed |
| Android-based Fire TV / Firestick (Fire OS) | ADB Debugging, normally port 5555 | Fire launcher, legacy foreground and older process probes covered by synthetic tests |
| Vega OS Fire TV / Firestick | Different OS and developer tooling | Unsupported by this Android/ADB server; no Kodi Android APK compatibility claim |

Check the OS rather than relying on the product name. Amazon lists both Android-based Fire OS
and Vega devices in its [official device/OS table](https://developer.amazon.com/docs/fire-tv/fire-os-overview.html).
This release does not implement a Vega connector or port Kodi to Vega.

## Prepare your device

Use the [TV setup guide](setup.md) for the shared Kodi HTTP settings and these device-specific steps.

**Fire OS:** find the IP under **Settings → My Fire TV → About → Network** (some models call
the menu Device). Open **My Fire TV → Developer Options → ADB Debugging**. If Developer Options
is hidden, select the device entry under About seven times. Approve the computer's debugging
dialog on the TV after connecting. Unknown-source app installation is only needed when installing
an APK; it is not required for read-only ADB diagnostics. See
[Amazon's ADB guide](https://developer.amazon.com/docs/fire-tv/connecting-adb-to-device.html).

**Android TV / Google TV:** find the IP in About/Status or the connected Network & Internet
entry. Unlock Developer options with seven presses on Build (often **System → About →
Android TV OS build**). Menu names vary by vendor. If a vendor offers **Network debugging**,
use its displayed port; enabling USB debugging alone does not necessarily open port 5555.

If **Wireless debugging → Pair device with pairing code** is available, keep that dialog open.
Android documents wireless debugging for Android 13+ TV devices; vendors can differ. It shows
a six-digit secret and a **pairing port**. The main Wireless debugging screen shows a separate
**connection port**. Use current [Google Platform Tools and ADB instructions](https://developer.android.com/tools/adb).

## Configure and pair

Set `ANDROID_TV_HOST` to the device's private IP and `ANDROID_TV_ADB_PORT` to its **connection
port** (5555 for typical Fire OS/vendor network debugging). The legacy `SHIELD_HOST` and
`SHIELD_ADB_PORT` work on every supported Android device too. If both names are set, they must
agree; conflicting targets are rejected. Preserve the remaining [configuration](configuration.md).
Set `ADB_PATH` to the installed ADB executable. Run the CLI using its virtual environment's absolute
`nvidia-mcp` path (`nvidia-mcp.exe` on Windows); neither executable needs a global PATH edit.
Pass these environment values to the CLI too: it does not load `.env` or your MCP client's config.

For code-based Wireless debugging, first run the installed executable with:

```text
nvidia-mcp --pair-adb PAIRING_PORT
```

Replace `PAIRING_PORT` with the port from the open pairing dialog. A local terminal prompts for
the code without echoing it. An agent with a private input mechanism can instead send the code
plus a newline through subprocess **stdin**. Never put it in a command argument, MCP call, chat
transcript or saved configuration. Pairing is a computer setup CLI action, not an MCP tool; it
works with write mode off and does not launch or restart Kodi.

Then connect ADB to **IP:CONNECTION_PORT**, verify targeted `get-state` returns `device`, and run
`nvidia-mcp --doctor`. Pairing success alone is not connection readiness. Wireless debugging
ports can change after a reboot/toggle; update the connection port and reconnect. Re-pair only
if authorization was revoked. Do not use discovery or connect to additional devices.

## Limits and troubleshooting

- Official Android Kodi uses package `org.xbmc.kodi`. Forks such as SPMC or vendor-renamed
  packages are not supported by the file/lifecycle tools. Do not point the storage root at a fork
  and expect those tools to target it.
- File tools need authorized ADB access to Kodi's shared storage, or an explicitly configured
  mounted path. Firmware storage restrictions may still block access; HTTP diagnostics can work
  independently. No root or permission bypass is attempted.
- Known Fire/Google/Android home launchers are recognized. A custom launcher needs its exact
  package in `NVIDIA_MCP_EXTRA_LAUNCHERS`; do not allowlist a video app as a launcher. Unknown
  foreground, process or active media state blocks disruptive work. Paused/background audio
  blocks it too.
- APK previews check the device's reported SDK, ABIs and signer. A 64-bit CPU can still run a
  32-bit Android userspace, so CPU marketing alone does not choose the APK. Firmware install
  restrictions remain possible; live Fire TV APK install/recovery is unverified.
- Shield-specific profile relaunch patches in `contrib/` are not general Android/Fire TV setup.
  Kodi Manager's NVIDIA exit workaround remains disabled without NVIDIA's driver.
- On low-memory sticks, start with a few cached rows/pages and manual refresh in Manager.
  Background provider refreshes still use CPU, memory and network; hardware performance is
  unverified. See [compatibility evidence](compatibility.md) and [troubleshooting](troubleshooting.md).
