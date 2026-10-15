# Set up nvidia-MCP with your TV remote

You change a few TV settings. An assistant with access to your computer installs the tools and
connects them. You do not need to open a terminal or edit configuration files yourself.

Before starting:

- Have **Kodi already installed** on the TV.
- Connect the TV and computer to the **same home network**. Ethernet and Wi-Fi can be used together.
- Finish watching first and keep the TV awake during setup.
- Use an assistant that can run commands and edit files on your computer. A browser chat alone
  cannot install this server.

**Only want Kodi Manager's browser dashboard?** Follow
[Kodi Manager setup](https://github.com/glasgowm148/kodi-manager/blob/main/docs/setup.md) instead.

**Apple TV?** Follow [the Apple TV guide](apple-tv.md). The debugging steps below are for Android devices.

## 1. Enable debugging on the TV

Open the instructions for your device and complete **step 1** there:

- [Fire TV / Firestick: enable ADB Debugging](android-tv.md#fire-tv--firestick-fire-os).
- [NVIDIA Shield: enable Network debugging](android-tv.md#nvidia-shield).
- [Android TV / Google TV: enable network or Wireless debugging](android-tv.md#android-tv--google-tv).

**ADB** means Android Debug Bridge. Debugging lets your computer connect to the TV.
Android-based Fire OS is supported; Vega OS is not.

## 2. Find the TV's IP address

Complete **step 2** in [your device's instructions](android-tv.md).
Write down the address shown on the TV. It looks like `192.168.1.50` or `10.0.0.50`;
use your own address, rather than those examples or your computer's address.

If the debugging screen shows a **port** (the number after a colon), write that down too.
If it does not show a port, leave that detail for the assistant to check.

## 3. Enable Kodi remote control

These steps happen **inside Kodi**, using the TV remote:

1. Open **Kodi** → **Settings** (gear icon) → **Services** → **Control**.
2. If the options below are missing, select the settings level at the bottom left until it says
   **Standard** or **Expert**.
3. Turn on **Allow remote control via HTTP**.
4. Keep **Require authentication** on, if shown. Set a **Username** and **Password** and keep them private.
5. Write down **Port**, usually **8080**. Leave it as shown unless there is a reason to change it.
6. Return to Kodi's home screen and leave Kodi open.

This password is for Kodi remote control. It is separate from your streaming accounts and
Kodi Manager's access token. Give it to the assistant through private input when asked.
[Kodi's settings reference](https://kodi.wiki/view/Settings/Services/Control).

## 4. Give this message to your assistant — on the computer

Replace `YOUR_TV_MODEL` and `YOUR_TV_IP` before sending. If you noted a debugging port,
include it too. The assistant handles downloads, installation and computer configuration.

```text
Set up https://github.com/glasgowm148/nvidia-MCP on this computer.
Read docs/agent-setup.md and complete the computer steps for me.
TV model: YOUR_TV_MODEL
TV IP address: YOUR_TV_IP
I have enabled debugging and Kodi remote control.
Ask which debugging option/port I see if needed, and ask privately for Kodi credentials.
Install missing tools, preserve existing MCP servers and verify read-only access.
Tell me when to approve a connection or enter a pairing code on the TV.
Keep write mode and plugin browsing off. Do not interrupt playback.
```

You do not need to know Python, ADB commands or the MCP configuration format.
The assistant follows its [computer setup procedure](agent-setup.md).

## 5. Approve the connection — on the TV

When the assistant asks, look for **Allow USB debugging?** or a similar prompt on the TV.
Select **Allow** or **OK**. “USB” is normal wording even when connected over Wi-Fi.
You can select **Always allow from this computer** for your own trusted computer.
Tell the assistant when you have approved it.

For **Wireless debugging**, the assistant may instead ask you to open **Pair device with pairing code**.
Follow [the pairing steps](android-tv.md#configure-and-pair) and use private input for the code.
Already approved or paired devices may not show another prompt.

If nothing appears, keep the TV awake and tell the assistant. It should check the connection
before asking you to change more settings. Your computer may also ask for Local Network permission
or your assistant app may need a reload; the assistant will explain any necessary action.

## 6. Ask for your first check

Wait for the assistant to confirm it can read the TV and Kodi. Then ask:

> Read the Kodi repair playbook and audit Kodi without interrupting anything.

Setup starts in read-only mode. To add the optional browser dashboard and live settings tools,
follow [Kodi Manager companion setup](companion.md).

If the TV's IP changes later, repeat step 2 and ask the assistant to update the connection.
For connection problems, see [troubleshooting](troubleshooting.md).
