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

1. Press **Home** on the remote and open **Settings** (gear icon).
2. Open **My Fire TV** → **Developer Options**. Some models call My Fire TV **Device**.
3. If Developer Options is missing, open **My Fire TV** → **About**, highlight your device's name
   and press the remote's centre/select button **seven times**. Press **Back**; Developer Options should appear.
4. Open **Developer Options** and turn **ADB Debugging** **On**.

You do not need to change Android's **Install unknown apps** setting for this connection.

### 2. Find the IP address

1. Open **Settings** → **My Fire TV** → **About** → **Network**.
2. Write down **IP Address**. It looks like `192.168.1.50`; use the numbers on your TV.

Use the Network page **inside About**, rather than the main Settings → Network page.
Keep the TV awake. When the assistant connects later, approve **Allow USB debugging**;
the wording can say USB even over Wi-Fi.

### 3. Continue with Kodi

Go to [step 3: enable Kodi remote control](setup.md#3-enable-kodi-remote-control).
Fire OS usually uses ADB port **5555**; the assistant checks this.

## NVIDIA Shield

### 1. Enable Network debugging

1. Press **Home** and open **Settings** → **Device Preferences** → **About**.
   Older firmware may put About directly under Settings.
2. Highlight **Build** and press the remote's centre/select button **seven times**,
   until a message says developer mode is enabled.
3. Press **Back** and open **Developer options** under Device Preferences.
4. Scroll to **Debugging** and turn on **Network debugging**. Accept its confirmation.

Choose **Build**, rather than Android version or Kernel version. No USB cable is needed.

### 2. Find the IP address

1. Open **Settings** → **Device Preferences** → **About** → **Status**.
2. Write down **IP address**: four numbers separated by dots, such as `192.168.1.50`.

If your menu differs, check **Settings** → **Network & Internet** → your connected network.
Note the debugging port if one is shown; otherwise the assistant starts with **5555**.

### 3. Continue with Kodi

Go to [step 3: enable Kodi remote control](setup.md#3-enable-kodi-remote-control).
Keep the TV awake so you can approve the computer's connection later.

## Android TV / Google TV

Menus vary between manufacturers. These are the usual names; if a named option is missing,
tell the assistant your model and the options you can see.

### 1. Enable network or Wireless debugging

1. Press **Home** and open **Settings** → **System** → **About**.
   Some TVs use **Device Preferences** → **About** instead.
2. Highlight **Android TV OS build** (sometimes **Build**) and press the remote's centre/select
   button **seven times**, until developer mode is enabled.
3. Press **Back** and open **Developer options** under System or Device Preferences.
4. If you see **Network debugging** or **ADB over network**, turn it on and note any displayed port.
5. Otherwise, if you see **Wireless debugging**, open it, turn it on and accept the network prompt.
   Write down its **IP address & port**. In `192.168.1.50:37123`, the IP is `192.168.1.50`
   and the connection port is `37123`.

**Only USB debugging is available?** Enabling it alone may not allow a network connection.
Stop here and tell the assistant your model and menu options; do not assume port 5555 works.

### 2. Find the IP address

1. Open **Settings** → **Network & Internet** → your connected Wi-Fi or Ethernet network.
2. Write down **IP address**. If it is missing, look under **System** → **About** → **Status**.
   Some TVs use **Device Preferences** → **About** → **Status**.

If Wireless debugging already showed an IP, use that address. Prefer the address with four
numbers separated by dots rather than a longer address with colons.

### 3. Continue with Kodi, then pair if asked

Go to [step 3: enable Kodi remote control](setup.md#3-enable-kodi-remote-control).
Tell the assistant whether you enabled Network debugging or Wireless debugging and give it
the connection port, if shown.

<a id="configure-and-pair"></a>

If pairing is needed, the assistant will ask you to return to **Developer options** →
**Wireless debugging** → **Pair device with pairing code**. Leave that screen open.
It shows a six-digit code and a **pairing port**, different from the connection port.
Enter the code only through the assistant's private input or hidden local terminal prompt.
The assistant handles pairing and connecting; you do not need to run commands.

## If something does not work

- **No debugging prompt:** keep the TV awake and tell the assistant. It checks the address/port first.
- **IP changed after restarting:** find it again using your device's step 2 and give the assistant the new value.
- **Wireless debugging port changed:** give the assistant the new connection port; this can happen after a restart.
- **Cannot find a menu:** give the assistant the model and exact options shown; avoid changing unrelated settings.

Shield is the live-tested reference device. Fire OS and other Android/Google TV devices still need
hardware validation; see [compatibility](compatibility.md). For agent commands, storage restrictions
and connection details, see the [Android connection reference](android-tv-connection.md).

Official references: [Amazon Fire TV ADB](https://developer.amazon.com/docs/fire-tv/connecting-adb-to-device.html),
[Android Wireless debugging](https://developer.android.com/tools/adb),
[NVIDIA Shield settings](https://www.nvidia.com/en-us/shield/support/shield-tv-pro/).
