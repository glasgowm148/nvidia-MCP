# Setting up nvidia-MCP

You need an agent that can run commands and edit files on the person's computer, and a client that
supports local (stdio) MCP servers. A browser-only chat cannot install this. The server is free and
MIT-licensed.

The repository's [`docs/agent-setup.md`](https://github.com/glasgowm148/nvidia-MCP/blob/main/docs/agent-setup.md)
is the authoritative procedure. Read it and follow it. In summary:

## Split the work

- **You (on the computer):** check or install Python 3.11+, Git and Android Platform Tools. Clone the
  reviewed release tag, create a virtual environment, `pip install -e .`, write the client config and
  verify.
- **The person (on the TV):** the menus. Enable network/ADB debugging, find the IP address, turn on
  Kodi's web-server control, and select **Allow** on the debugging prompt. See the repository's
  `docs/setup.md` and `docs/android-tv.md` for each device's menus.

## Conversation rules

1. Ask which TV or streaming device they use first. Then give that device's menu steps one at a time
   and wait for each reply.
2. Ask for the IP address on its own. Ask about each port (ADB connection, Wireless-debugging
   pairing, Kodi HTTP) in a separate message. Never guess one, and never scan the network.
3. Collect the Kodi password and any pairing code only through the client's private input. Never put
   them in commands, arguments, logs or chat.
4. Don't continue past a prompt on the TV until the person confirms they accepted it, and
   `adb -s IP:PORT get-state` returns `device`.

## Configure

Environment for the server (keep it private, outside the repository):

```text
ANDROID_TV_HOST=<TV IP>          ANDROID_TV_ADB_PORT=5555 (or the supplied port)
ADB_PATH=<absolute adb path>     KODI_PORT=8080 (or the supplied port)
KODI_USERNAME / KODI_PASSWORD    (private input)
NVIDIA_MCP_ALLOW_WRITES=0        NVIDIA_MCP_ALLOW_PLUGIN_BROWSE=0
```

- Run the absolute `nvidia-mcp` executable with `--doctor` and this environment, and check its
  redacted report.
- Merge **one** `nvidia-MCP` entry into the client's MCP config and keep every other server. The
  repository's `examples/claude-desktop.json` shows the Claude Desktop / Cursor shape; other clients
  use different formats.
- Reload the client.

## Verify

Through the registered MCP connection, read `nvidia://playbook`, then call `shield_check_connection`,
`shield_get_status` and `kodi_get_status`. Report the install location, the client, the connection
status and anything still to do. Never include credentials.

## Optional companion

[Kodi Manager](https://github.com/glasgowm148/kodi-manager) runs inside Kodi. It adds a browser
dashboard, live add-on settings, configuration checkpoints and Bingie layout editing. Install it only
if the person wants it, following the repository's `docs/companion.md`.

Supported: NVIDIA Shield (live-tested), Android TV / Google TV and Android-based Fire OS (supported,
but so far tested only with synthetic fixtures).
Apple TV support is experimental (`docs/apple-tv.md`). Vega OS Fire TV is not supported.
