# Prepare the TV, then hand over to your agent

Your part is the **TV settings and permission prompt**. An agent with terminal/file access handles
downloads, installation, commands and MCP configuration on the computer. Both devices should be on
the same home network; the Shield can use Ethernet while the computer uses Wi-Fi.

## 1. Find the Shield's IP — on the TV

Press **Home** on the Shield remote and open the **Settings gear → Device Preferences → About →
Status → IP address**. Write down the local **IPv4** address: four numbers separated by dots, such as
`192.168.1.50` or `10.0.0.50`. Give the agent the address shown on your TV, not these examples or the
computer's address.

Older Shield firmware may put **About** directly under Settings. You can also check the connected
Wi-Fi/Ethernet entry under **Settings → Network & Internet**. NVIDIA describes the About screen's
network information in its [Shield user guide](https://www.nvidia.com/en-us/shield/support/shield-tv-pro/).

## 2. Enable network debugging — on the TV

1. Open **Settings → Device Preferences → About**.
2. Highlight **Build** and press the remote's centre/select button **seven times**, until developer
   mode is enabled. Choose **Build**, not the Android version or kernel version.
3. Press **Back**, scroll down in **Device Preferences**, and open **Developer options**.
4. Find the **Debugging** section and turn **Network debugging** on. Accept its confirmation if shown.

Android's [Developer options guide](https://developer.android.com/studio/debug/dev-options) explains
the Build-number unlock. A USB cable is unnecessary for the Shield's network-debugging connection.
Keep the TV awake so you can approve the computer later.

## 3. Enable Kodi HTTP control — inside Kodi on the TV

Open **Kodi → Settings** (gear icon or the skin's Settings entry), then **Services → Control**.
If the options are hidden, change the settings level at the bottom/left to **Standard** or **Expert**.

- Turn **Allow remote control via HTTP** on.
- Keep **Require authentication** on and set a **Username** and **Password**.
- Note **Port**; it is usually `8080`, but use the value shown in your Kodi.

Keep Kodi running. Give the agent the port and credentials privately when requested. These are Kodi
HTTP credentials, separate from any Trakt/debrid account. See
[Kodi's Control settings](https://kodi.wiki/view/Settings/Services/Control).

## 4. Send this to your agent

Use an agent that can run commands and edit files on the computer where your MCP client runs.
Replace the IP and port below; the agent can resolve the operating system, paths and installed tools.

```text
Set up https://github.com/glasgowm148/nvidia-MCP on this computer.
Read docs/agent-setup.md and complete the computer setup automatically.
The TV is prepared: Shield network debugging and Kodi HTTP control are enabled.
Shield IP: YOUR_SHIELD_IP
Kodi HTTP port: 8080
Ask privately for the Kodi username/password if needed.
Install any missing dependencies, connect ADB, preserve my existing MCP servers,
register nvidia-MCP and verify its read-only tools.
Tell me when to select Allow on the TV's debugging prompt.
Keep write mode and plugin browsing off; do not interrupt playback.
```

You do not need to install ADB/Python, open a terminal, run commands or fill in JSON yourself.
The [agent setup procedure](agent-setup.md) covers that work. An agent without computer access needs
to hand this task to one that has it; the MCP server cannot bootstrap itself before it is installed.

## 5. Approve the connection when the agent tells you — on the TV

The first computer connection triggers a debugging dialog on the Shield. Select **Allow**. Optionally
select **Always allow from this computer** if it is your own trusted computer. The dialog may say
USB debugging even though the connection is over the network.

Tell the agent you have approved it; the agent checks authorization, Kodi connectivity and MCP tools.
If no prompt appears, keep the Shield awake and let the agent troubleshoot before changing more settings.
An operating-system permission prompt or a client restart may also need your interaction if the agent
cannot handle it through its available tools.

After setup, ask: **“Read the Shield repair playbook and audit Kodi without interrupting anything.”**
The optional [Kodi Manager companion](companion.md) adds live skin/settings APIs; the agent can prepare
it separately if those features are needed.

If the router later changes the Shield's address, find it again using step 1 and tell the agent to update
the saved connection. The agent can explain your router's DHCP reservation option if you want a stable IP.
