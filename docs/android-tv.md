# Set up your Fire TV, Shield or Android TV

These steps let an assistant on your computer connect to your TV using **ADB**
(Android Debug Bridge). You use the TV remote; the assistant handles the computer commands.
Kodi must already be installed. Put the TV and computer on the same home network.

**Only want the Kodi Manager browser dashboard?** Use
[its installation guide](https://github.com/glasgowm148/kodi-manager/blob/main/docs/setup.md).
You can skip debugging and this page entirely.

Choose your device:

- [Fire TV / Firestick](#fire-tv--firestick-fire-os)
- [NVIDIA Shield](#nvidia-shield)
- [Android TV / Google TV](#android-tv--google-tv)
- [Apple TV](apple-tv.md) has a separate setup.

## Fire TV / Firestick (Fire OS)

These steps are for **Android-based Fire OS**. Devices using **Vega OS** are unsupported.
If unsure, check your model in [Amazon's device list](https://developer.amazon.com/docs/fire-tv/fire-os-overview.html).

### 1. Enable ADB Debugging

- **Open the device settings.**
  - Press **Home** → **Settings** (gear icon) → **My Fire TV**.
  - Some models call My Fire TV **Device**.
- **Open Developer Options.**
  - If missing, open **About** and highlight your device's name.
  - Press the remote's centre/select button **seven times**, then press **Back**.
- **Turn on ADB Debugging.**
  - Open **Developer Options → ADB Debugging** and set it to **On**.
  - You do not need to change Android's **Install unknown apps** setting for this connection.

### 2. Find the IP address

- **Open the network details.**
  - Go to **Settings → My Fire TV → About → Network**.
  - Use the Network page **inside About**.
- **Write down IP Address.**
  - It looks like `192.168.1.50`. Use the numbers on your TV.

### 3. Continue with Kodi

- **Enable Kodi control.**
  - Continue at [setup step 3](setup.md#3-enable-kodi-remote-control).
  - Fire OS usually uses ADB port **5555**; the assistant checks this.
- **Keep the TV awake.**
  - Later, approve **Allow USB debugging** when the assistant connects.
  - The prompt can say USB even over Wi-Fi.

## NVIDIA Shield

### 1. Enable Network debugging

- **Open About.**
  - Press **Home → Settings → Device Preferences → About**.
  - Older firmware may put About directly under Settings.
- **Unlock developer mode.**
  - Highlight **Build** and press the remote's centre/select button **seven times**.
  - Wait for the developer-mode message. Choose Build, rather than Android or Kernel version.
- **Turn on network debugging.**
  - Press **Back** → **Developer options** → **Debugging**.
  - Turn **Network debugging** on and accept its confirmation. No USB cable is needed.

### 2. Find the IP address

- **Open the network details.**
  - Go to **Settings → Device Preferences → About → Status**.
  - If your menu differs, try **Settings → Network & Internet → your connected network**.
- **Write down IP address.**
  - Use the four numbers separated by dots, such as `192.168.1.50`.
  - Note the debugging port if shown; otherwise the assistant starts with **5555**.

### 3. Continue with Kodi

- **Enable Kodi control.**
  - Continue at [setup step 3](setup.md#3-enable-kodi-remote-control).
- **Keep the TV awake.**
  - You will approve the computer's connection later.

## Android TV / Google TV

Menus vary between manufacturers. These are the usual names; if a named option is missing,
tell the assistant your model and the options you can see.

### 1. Enable network or Wireless debugging

- **Open About.**
  - Press **Home → Settings → System → About**.
  - Some TVs use **Device Preferences → About** instead.
- **Unlock developer mode.**
  - Highlight **Android TV OS build** (sometimes **Build**).
  - Press the remote's centre/select button **seven times** until developer mode is enabled.
  - Press **Back** and open **Developer options** under System or Device Preferences.
- **If Network debugging or ADB over network is available:**
  - Turn it on and note any displayed port.
- **Otherwise, if Wireless debugging is available:**
  - Open it, turn it on and accept the network prompt.
  - Write down **IP address & port**.
  - Example: in `192.168.1.50:37123`, the IP is `192.168.1.50` and the connection port is `37123`.
- **Only USB debugging is available:**
  - Stop here and tell the assistant your model and menu options.
  - USB debugging alone may not allow network access; do not assume port 5555 works.

### 2. Find the IP address

- **Open the network details.**
  - Go to **Settings → Network & Internet → your connected Wi-Fi or Ethernet network**.
  - If missing, try **System → About → Status**, or **Device Preferences → About → Status**.
- **Write down IP address.**
  - Use the address with four numbers separated by dots.
  - If Wireless debugging already showed an IP, use that address.

### 3. Continue with Kodi, then pair if asked

- **Enable Kodi control.**
  - Continue at [setup step 3](setup.md#3-enable-kodi-remote-control).
  - Tell the assistant which debugging option you enabled and the connection port, if shown.

<a id="configure-and-pair"></a>

- **If the assistant asks you to pair:**
  - Open **Developer options → Wireless debugging → Pair device with pairing code**.
  - Leave that screen open. It shows a six-digit code and a **pairing port**.
  - The pairing port differs from the connection port.
  - Enter the code only through private input or the hidden local terminal prompt.
  - The assistant handles the commands for pairing and connecting.

## If something does not work

- **No debugging prompt**
  - Keep the TV awake and tell the assistant. It checks the address and port first.
- **IP changed after restarting**
  - Repeat your device's step 2 and give the assistant the new address.
- **Wireless debugging port changed**
  - Give the assistant the new connection port; this can happen after a restart.
- **Cannot find a menu**
  - Give the assistant your model and the exact options shown.

Shield is the live-tested reference device. Fire OS and other Android/Google TV devices still need
hardware validation; see [compatibility](compatibility.md). For agent commands, storage restrictions
and connection details, see the [Android connection reference](android-tv-connection.md).

Official references: [Amazon Fire TV ADB](https://developer.amazon.com/docs/fire-tv/connecting-adb-to-device.html),
[Android Wireless debugging](https://developer.android.com/tools/adb),
[NVIDIA Shield settings](https://www.nvidia.com/en-us/shield/support/shield-tv-pro/).
