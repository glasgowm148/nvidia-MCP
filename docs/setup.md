# Set up nvidia-MCP with your TV remote

You change a few TV settings. An assistant with access to your computer installs the tools and
connects them. You do not need to open a terminal or edit configuration files yourself.

Before starting:

- **TV and network**
  - Have **Kodi already installed**.
  - Put the TV and computer on the **same home network**. Ethernet and Wi-Fi can be used together.
  - Finish watching and keep the TV awake during setup.
- **Computer assistant**
  - Use an assistant that can run commands and edit files on your computer.
  - A browser chat alone cannot install this server.
- **A different setup?**
  - Browser dashboard only: use [Kodi Manager setup](https://github.com/glasgowm148/kodi-manager/blob/main/docs/setup.md#1-add-the-download-source--inside-kodi).
  - Apple TV: use [its separate guide](apple-tv.md).

Want both? The prompt in step 4 covers the complete setup: nvidia-MCP first, then Kodi Manager.
You can also give it to your agent before these TV steps; it will guide you through them.

## 1. Enable debugging on the TV

- **Choose your device and complete its step 1:**
  - [Fire TV / Firestick: ADB Debugging](android-tv.md#fire-tv--firestick-fire-os).
  - [NVIDIA Shield: Network debugging](android-tv.md#nvidia-shield).
  - [Android TV / Google TV: network or Wireless debugging](android-tv.md#android-tv--google-tv).
- **What this does:**
  - ADB (Android Debug Bridge) lets your computer connect to the TV.
  - Android-based Fire OS is supported; Vega OS is not.

## 2. Find the TV's IP address

- **Find the address.**
  - Complete step 2 in [your device's instructions](android-tv.md).
  - Write down the address shown on your TV, such as `192.168.1.50`.
  - Use your own address, rather than that example or your computer's address.
- **If a debugging port is shown:**
  - Note the number after the colon, such as `37123` in `192.168.1.50:37123`.
  - If no port is shown, leave that detail for the assistant to check.

## 3. Enable Kodi remote control

Use the TV remote inside Kodi:

- **Open the control settings.**
  - Go to **Kodi → Settings** (gear icon) → **Services → Control**.
  - If options are missing, change the bottom-left settings level to **Standard** or **Expert**.
- **Enable access and authentication.**
  - Turn on **Allow remote control via HTTP**.
  - Keep **Require authentication** on, if shown.
  - Set a **Username** and **Password**. Give them to the agent through private input when asked.
- **Note the connection details.**
  - Write down **Port**, usually **8080**. Leave it unchanged unless necessary.
  - Return to Kodi's home screen and leave Kodi open.

This password is for Kodi remote control, separate from streaming accounts and Kodi Manager's token.
[Kodi's settings reference](https://kodi.wiki/view/Settings/Services/Control).

## 4. Give this message to your assistant — on the computer

Copy the whole prompt below. No editing is needed. The agent asks for any missing details,
sets up nvidia-MCP, then installs and connects Kodi Manager as part of the same request.

```text
Set up nvidia-MCP and Kodi Manager for my TV:
https://github.com/glasgowm148/nvidia-MCP
https://github.com/glasgowm148/kodi-manager

Read nvidia-MCP's docs/agent-setup.md and docs/companion.md first.
Ask for missing device/connection details and guide me through any TV preparation.

1. Install and configure nvidia-MCP on this computer. Verify the actual MCP
   connection can read my TV and Kodi before continuing.
2. Install Kodi Manager from https://glasgowm148.github.io/kodi-manager/
   using Kodi's native installer. Reuse supported existing installations and
   back up customizations before any replacement.
3. Connect the active profile's Manager token privately. Enable dashboard LAN
   access, give me its browser address, and verify read-only Manager access.

Handle computer commands, downloads and supported TV navigation yourself.
Ask me only for private credentials, pairing/permission prompts or TV steps
that your tools cannot complete. Keep passwords, tokens and pairing codes private.
Preserve my other MCP servers and settings. Target only my specified TV and
never interrupt playback. Enable only writes needed for setup; finish with
write mode and provider browsing off.
Complete both stages without asking me to send a second setup prompt.
```

You do not need to know Python, ADB commands or the MCP configuration format.
The assistant follows its [computer setup procedure](agent-setup.md).

## 5. Approve the connection — on the TV

- **A debugging prompt appears:**
  - Select **Allow** or **OK** when the assistant asks.
  - It may say **Allow USB debugging?** even over Wi-Fi.
  - For your own trusted computer, you can select **Always allow from this computer**.
  - Tell the assistant once approved.
- **Wireless debugging needs pairing:**
  - Follow [the pairing steps](android-tv.md#configure-and-pair).
  - Enter the code through private input when asked.
  - Already approved or paired devices may not show another prompt.
- **Nothing appears:**
  - Keep the TV awake and tell the assistant; it checks the connection first.
  - If a computer permission prompt or app reload is needed, the assistant explains that action.

## 6. Ask for your first check

- **Wait for connection checks.**
  - The assistant should confirm it can read both the TV and Kodi.
  - Setup starts in read-only mode.
- **Let the combined setup finish.**
  - The step 4 prompt already asks the agent to install and connect Kodi Manager next.
  - You do not need to send another setup message. The agent may still need TV permission input.
- **Ask for your first audit.**
  - **“Read the Kodi repair playbook and audit Kodi without interrupting anything.”**

If the TV's IP changes later, repeat step 2 and ask the assistant to update the connection.
For connection problems, see [troubleshooting](troubleshooting.md).
