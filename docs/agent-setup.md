# Agent setup procedure

These instructions are **for the agent on the computer**. The user completes [TV preparation](setup.md)
first. Handle downloads, installation, commands, paths, client configuration and verification yourself;
do not give the user a terminal/JSON checklist. You need local file/terminal access and network access.
Ask for missing information or an unavoidable TV/OS/client interaction, then continue the remaining work.

For **Apple TV**, follow [Apple TV computer setup](apple-tv.md#computer-setup-agent-performs-this) instead of the ADB steps below. Preserve an existing Shield server entry; configure Apple TV as a separate instance. Install the optional dependency, pair both protocols privately, merge credentials and verify read-only tools. The user handles Kodi installation/security settings and private PIN/token entry.

## 1. Resolve the environment and connection details

- Identify the OS/architecture, the MCP client to configure and its existing installation/configuration.
  Use the current client if known; ask which client only if it cannot be determined.
- Obtain the device model/OS, ADB mode/connection port and private LAN IP and Kodi HTTP port from the user. Request Kodi credentials through
  the client's private/secret mechanism where available. Do not log, echo or commit credentials.
- Check existing Python, Git and ADB installations before downloading replacements. Use Python **3.11+**
  and a dedicated virtual environment; preserve the user's system Python and other projects.
- Reuse an existing suitable nvidia-MCP checkout. Inspect its state before updating; preserve local
  changes. Otherwise clone this repo to an appropriate user-owned workspace.
  For a released install, prefer tag **v0.5.1** (or a newer reviewed release) rather than an
  unreviewed moving `main`. Downloading GitHub's Source code ZIP alone does not register an MCP server.

Use the [official Python downloads](https://www.python.org/downloads/),
[Git downloads](https://git-scm.com/downloads) and
[Google Platform Tools](https://developer.android.com/tools/releases/platform-tools) for missing tools,
or an existing trusted package manager. Select the appropriate OS package and keep Platform Tools'
companion files together. If an OS installer requires interaction you cannot perform, explain that
specific action; resume installation/verification afterward. Avoid reinstalling tools that already work.

## 2. Install the local server

Run from the checkout. Resolve the commands to the actual installed Python/executable paths.

Mac/Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

Windows:

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
```

Verify the selected interpreter is 3.11+ before creating the environment. If `.venv` already exists,
inspect/reuse it rather than blindly recreating it. Use absolute executable paths for subsequent calls;
activation and global PATH edits are unnecessary. Record the actual MCP executable and ADB paths.

## 3. Connect ADB and handle the TV prompt

Use the resolved ADB executable, targeting only the IP/port supplied by the user:

```text
ADB_EXECUTABLE version
ADB_EXECUTABLE connect TV_IP:CONNECTION_PORT
ADB_EXECUTABLE -s TV_IP:CONNECTION_PORT get-state
```

These are argument patterns, not literal commands. Pass the actual path/arguments through your command
tool with proper quoting; do not scan the LAN. Fire OS/Shield network debugging normally uses `5555`; use the supplied connection port and
set `ANDROID_TV_ADB_PORT`. Confirm Android-based Fire OS rather than Vega OS.

For code-based Android Wireless debugging, obtain the separate pairing port from the open TV
pairing dialog. Run the installed `nvidia-mcp --pair-adb PAIRING_PORT` with `ANDROID_TV_HOST`
in the subprocess environment, sending the six-digit code plus newline via private stdin. A
local terminal can use the hidden prompt. Never put the code in arguments, logs, saved config or
an MCP tool call. Then `adb connect` the connection port; do not use the pairing port for normal
commands. See [Android TV / Fire TV setup](android-tv.md).

If `get-state` already returns `device`, reuse that authorization without asking again. When a new
authorization is needed, tell the user to select **Allow** on the TV, wait for their reply and verify
`get-state` returns `device`. `adb connect` saying connected is not proof of authorization. If the
state is `unauthorized`, approval is still pending; `offline` needs a targeted disconnect/reconnect.
If the prompt is absent, ask the user to keep the TV awake and check its debugging mode/connection port before
suggesting revoking authorizations (which also affects other computers). See
[Google's ADB reference](https://developer.android.com/tools/adb).

## 4. Build private configuration and verify Kodi HTTP

Construct environment values using the user's actual connection details:

| Variable | Value |
|---|---|
| `ANDROID_TV_HOST` | Private TV IP, no URL prefix or port (`SHIELD_HOST` remains compatible) |
| `ANDROID_TV_ADB_PORT` | ADB connection port; legacy `SHIELD_ADB_PORT` also works |
| `ADB_PATH` | Absolute ADB executable path, including `adb.exe` on Windows |
| `KODI_PORT` | HTTP port from Kodi, normally `8080` |
| `KODI_USERNAME`, `KODI_PASSWORD` | Private Kodi HTTP credentials |
| `NVIDIA_MCP_ALLOW_WRITES` | `0` |
| `NVIDIA_MCP_ALLOW_PLUGIN_BROWSE` | `0` |

Inject this environment into a subprocess running the **absolute MCP executable** with `--doctor`.
Use your tool's environment support or a local process API; avoid embedding passwords in shell
commands, command-line arguments or visible output. The server does **not** load `.env` automatically.
Inspect the redacted result; doctor checks ADB, Kodi HTTP and optional Manager independently.
The explicit step 3 check handles the TV authorization prompt before doctor runs.

If HTTP fails, check whether Kodi is open, the port/auth details are correct, and the computer can reach
the same LAN. Ask for a specific TV correction only if needed. Do not restart/stop playback to get a
successful connectivity check. Report partial connectivity honestly.
If authorized ADB works but the host application cannot reach the LAN, inspect OS Local Network
permissions, VPN/firewall rules and guest-network isolation. An explicit `KODI_HTTP_ROUTE=forward`
uses that ADB connection for both HTTP services; `auto` falls back only on connection failures.
Keep Kodi credentials and the optional Manager token configured. Verify again and record the route.

## 5. Register the MCP server automatically

Use the client's supported server-registration command/API if available. Otherwise locate and edit its
documented MCP configuration. Consult current official client instructions when the format/location
is unclear. Back up the existing configuration privately and merge **one** `nvidia-MCP` entry; preserve
other servers and unrelated settings. Do not overwrite the entire client configuration with a template.

[examples/claude-desktop.json](../examples/claude-desktop.json) is a Claude Desktop/Cursor-shaped example:

```json
{
  "mcpServers": {
    "nvidia-MCP": {
      "command": "/absolute/path/nvidia-MCP/.venv/bin/nvidia-mcp",
      "env": {
        "ANDROID_TV_HOST": "192.168.1.50",
        "ANDROID_TV_ADB_PORT": "5555",
        "ADB_PATH": "/absolute/path/platform-tools/adb",
        "KODI_PORT": "8080",
        "KODI_USERNAME": "kodi",
        "KODI_PASSWORD": "REPLACE_PRIVATELY",
        "NVIDIA_MCP_ALLOW_WRITES": "0",
        "NVIDIA_MCP_ALLOW_PLUGIN_BROWSE": "0"
      }
    }
  }
}
```

Generate the actual configuration with a JSON/config serializer and resolved values. Other clients
have different formats; do not assume every client accepts `mcpServers`. Windows uses the absolute
`.venv\Scripts\nvidia-mcp.exe` and `adb.exe` paths; the serializer handles backslash escaping. Keep
filled configuration/backups outside this repository with restrictive permissions where supported.

Reload the server using the client's supported mechanism. Handle it yourself when possible. If an
application restart must be performed by the user, explain that single remaining action and resume
verification afterward; do not claim registration alone proves the tools work.

## 6. Verify through MCP and hand back a working connection

Read `nvidia://playbook`, discover the tools and call **`shield_connection`**, **`shield_status`** and **`kodi_status`** through
the actual registered MCP connection. Confirm authorization, Kodi application/profile/skin information
and read-only defaults. Keep reads bounded. Do not execute plugin previews, playback tests, remote
buttons or lifecycle/repair tools as a setup test.

If the current agent cannot refresh its available tools until the client restarts, verify stdio
initialization/tool discovery with an MCP client locally and clearly identify the pending client-side
check. Do not mark full client setup complete until its registered connection can use the tools.

Give the user a short result: installed location, configured client, ADB/Kodi/MCP connection status and
any genuine remaining action. Include no credentials. The user can now ask for a focused Kodi audit.
Set up the optional [Kodi Manager companion](companion.md) only when its extra functionality is wanted;
reuse an existing supported installation instead of automatically replacing it.

APK tooling is optional and is not part of ordinary onboarding. When the person requests an APK
install/upgrade, follow [the agent APK workflow](apk-upgrades.md) and configure official SDK Build
Tools yourself. ADB Wireless debugging code pairing is supported by the setup CLI. The separate Android TV
Remote protocol is not implemented; all remote controls here use ADB.
