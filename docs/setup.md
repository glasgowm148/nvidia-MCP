# First-time setup

You use **the Shield remote on the TV** for device/Kodi settings, and **your computer** for downloads,
commands and the MCP client. The Shield and computer must be on the same home network; Ethernet and
Wi-Fi can be mixed. Guest networks may block connections between devices.

## 1. Find the Shield's IP address — on the TV

Press **Home** on the Shield remote, then open the **Settings gear**.
Go to **Device Preferences → About → Status → IP address**. Write down the local **IPv4** address:
it looks like `192.168.1.50` or `10.0.0.50`, with four numbers separated by dots. Use the actual address
shown on your TV, not these examples or your computer's IP.

On older Shield firmware, **About** may be directly under Settings. You can also look in
**Settings → Network & Internet** and select the connected Wi-Fi/Ethernet entry for network details.
NVIDIA documents the About screen's network information in its
[Shield user guide](https://www.nvidia.com/en-us/shield/support/shield-tv-pro/).

The address can change after a router restart. If that happens, check it again and update `SHIELD_HOST`.
Optionally use your router's DHCP reservation feature to keep the Shield's address consistent.

## 2. Reveal Developer options and enable network debugging — on the TV

1. Open **Settings → Device Preferences → About**.
2. Scroll to **Build**. Highlight it and press the remote's centre/select button **seven times**, until
   the TV says developer mode is enabled. Select **Build**, not the Android version or kernel version.
3. Press **Back** to return to **Device Preferences**. Scroll down and open **Developer options**.
4. Find the **Debugging** section and switch **Network debugging** on. Accept its confirmation if shown.
5. Keep the TV awake: you will need to approve your computer's connection in step 3.

Android's [Developer options guide](https://developer.android.com/studio/debug/dev-options) explains
the Build-number unlock. The Shield's network-debugging switch is the one used by this project;
the standard Shield connection uses port `5555`. It does not require a USB cable.

## 3. Install ADB and connect — on your computer

**ADB** is the tool the computer uses to communicate with the Shield's Android system.
Download **SDK Platform-Tools** for your operating system from
[Google's official download page](https://developer.android.com/tools/releases/platform-tools).
You only need Platform Tools; Android Studio is optional.

Extract the ZIP. For the commands below, put its inner **`platform-tools` folder in Downloads**,
so that `Downloads/platform-tools` contains `adb` on Mac/Linux or `adb.exe` on Windows. If your unzip
tool creates an extra enclosing folder, move the inner `platform-tools` folder to Downloads, or adjust
the `cd` command to its actual location. Keep the other extracted files alongside ADB.

### Mac

Press **Command–Space**, type **Terminal**, and open it. Paste these commands one at a time,
replacing `192.168.1.50` with your Shield's IP:

```sh
cd "$HOME/Downloads/platform-tools"
./adb version
./adb connect 192.168.1.50:5555
```

### Windows

Open **Start**, type **PowerShell**, and open it. Paste these commands one at a time,
replacing `192.168.1.50` with your Shield's IP:

```powershell
cd "$env:USERPROFILE\Downloads\platform-tools"
.\adb.exe version
.\adb.exe connect 192.168.1.50:5555
```

### Linux

Open your terminal application and run the Mac commands above, adjusting the Downloads directory if
your system uses another name. Alternatively use your distribution's Platform Tools/ADB package and
run `adb` directly once it is on PATH.

### Approve the connection — back on the TV

A debugging permission dialog should appear on the Shield. Choose **Allow**. If this is your own
trusted computer, you can also select **Always allow from this computer**. The dialog may mention
USB debugging even though the connection is over the network.

Back in the computer's terminal, check the connection:

```sh
./adb devices
```

On Windows use `.\adb.exe devices`. You want a line like:

```text
List of devices attached
192.168.1.50:5555    device
```

`device` means the connection is authorized. `unauthorized` means the TV prompt still needs approval;
`offline` means the connection needs reconnecting. See the troubleshooting table below.

Keep the full path to ADB for the MCP configuration. On Mac/Linux, `pwd` in this terminal prints the
folder; append `/adb`. On Windows, `(Get-Item .\adb.exe).FullName` prints the full executable path.
Set **`ADB_PATH`** to that full path. The `./` or `.\` prefix above tells the terminal to use the ADB
file in the current directory; it does not permanently add ADB to PATH.

Google's [ADB reference](https://developer.android.com/tools/adb) covers network connections and the
device list. These commands run **on your computer**, not inside Kodi or a browser.

## 4. Enable Kodi's HTTP connection — inside Kodi on the TV

Open Kodi, then its **Settings** menu (gear icon or the skin's Settings entry).
Open **Services → Control**. If the options are hidden, change the settings level at the bottom/left
to **Standard** or **Expert**.

- Enable **Allow remote control via HTTP**.
- Keep **Require authentication** enabled and choose a **Username** and **Password**.
- Note **Port**; the usual value is `8080`. Use the value shown in your Kodi.

On your computer, open `http://192.168.1.50:8080` in a browser, replacing the IP and port with yours.
Sign in using the username/password you just set. Kodi's web interface should load. Keep Kodi running
when using its HTTP tools. See [Kodi's Control settings](https://kodi.wiki/view/Settings/Services/Control).

## 5. Install the MCP server — on your computer

Install **Python 3.11 or newer** from [python.org](https://www.python.org/downloads/) and
**Git** from [git-scm.com](https://git-scm.com/downloads) if you do not already have them.
Open a **new terminal window** after installing them. Run `git --version` and `python3 --version`
(Windows: `py -3 --version`) to check they are available.

Choose a folder for projects; for example, start in Documents:

### Mac/Linux

```sh
cd "$HOME/Documents"
git clone https://github.com/glasgowm148/nvidia-MCP.git
cd nvidia-MCP
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

### Windows

```powershell
cd "$env:USERPROFILE\Documents"
git clone https://github.com/glasgowm148/nvidia-MCP.git
cd nvidia-MCP
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
```

If you already cloned the repo, use that folder instead of cloning again. You do not need to activate
the virtual environment when using these full executable paths. If Windows has redirected Documents
to OneDrive or your Linux machine has no Documents folder, choose an existing folder instead.

## 6. Configure your MCP client — on your computer

Use the [README's MCP JSON example](../README.md#quick-start) in your client's MCP/server settings.
The exact settings screen/config file depends on the client; the example uses the Claude Desktop /
Cursor `mcpServers` shape. For clients with separate fields, enter the same command and environment
values in their corresponding fields.

| Field | What to put there |
|---|---|
| `command` | Full path to the repo's `.venv/bin/nvidia-mcp`; on Windows `.venv\Scripts\nvidia-mcp.exe` |
| `SHIELD_HOST` | Shield's IPv4 from step 1, with no `http://` or port |
| `ADB_PATH` | Full path to extracted `adb`/`adb.exe` from step 3 |
| `KODI_PORT` | Kodi HTTP port from step 4 |
| `KODI_USERNAME`, `KODI_PASSWORD` | Kodi HTTP credentials from step 4 |

In JSON, Windows backslashes must be doubled, for example
`"ADB_PATH": "C:\\Users\\YOUR_NAME\\Downloads\\platform-tools\\adb.exe"`.
Replace placeholders with your real paths; `~` and `$HOME` in a JSON string are not substitutes for
a full executable path. Keep this config private. Restart your client/MCP server after saving.

Ask the assistant: **“Read the Shield repair playbook and audit Kodi without interrupting anything.”**
Leave write mode off for the first connection check. The optional
[Kodi Manager companion](companion.md) adds live skin/settings APIs and has separate setup.

## Troubleshooting

| Symptom | Next step |
|---|---|
| No Developer options menu | Repeat the seven presses on **About → Build**, then go back to Device Preferences. |
| `adb` not found / not recognized | Use `./adb` on Mac/Linux or `.\adb.exe` on Windows from the extracted folder. Set the absolute `ADB_PATH` for your MCP client. |
| `unauthorized` / no Allow prompt | Wake the Shield and look for the dialog. Run ADB disconnect/connect again. If still missing, use the Shield's revoke-debugging-authorizations option, then reconnect and approve; other authorized computers will also need approval again. |
| `offline` | Disconnect and reconnect the same Shield using the commands below. |
| Connection refused | Check Network debugging is on and the IP/port still match the Shield. |
| Connection timed out | Check both devices are on the same LAN; guest Wi-Fi, a VPN or firewall may block local connections. |
| ADB works, Kodi HTTP fails | Open Kodi and recheck **Services → Control**, the HTTP port and username/password. Test its browser URL from step 4. |
| Kodi HTTP works, MCP cannot find ADB | Set `ADB_PATH` explicitly; GUI clients may have a different PATH from your terminal. |
| MCP server will not start | Check the absolute server executable path, Python version and client's JSON format. |

Reconnect from the `platform-tools` terminal, replacing the example IP:

```sh
./adb disconnect 192.168.1.50:5555
./adb connect 192.168.1.50:5555
./adb devices
```

On Windows replace each `./adb` with `.\adb.exe`.

| Connection | Default port | Where it is enabled |
|---|---|---|
| Shield Android / ADB | `5555` | Shield Developer options → Network debugging |
| Kodi HTTP / JSON-RPC | `8080` | Kodi Settings → Services → Control |
| Optional Kodi Manager | `8765` | Kodi Manager add-on settings |
