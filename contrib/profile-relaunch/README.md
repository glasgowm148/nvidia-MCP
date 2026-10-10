# Kodi account-switch handoff

Small, offline Android helper for this Shield's Kodi 22 beta 2 profile teardown bug. Kodi saves settings and the next startup profile, waits for native jobs, and stops its Python services. At Kodi's logged `Application stopped` checkpoint, a same-UID child ends the process before NVIDIA's final graphics teardown; Android then reopens Kodi. There is no launcher screen, network permission, boot receiver, periodic job or background loop.

`ArmReceiver` accepts an explicit, authenticated ordered broadcast. The sender must receive a successful acknowledgment before quitting Kodi. It schedules one launch of the fixed Kodi Splash component after ten seconds, using Android's alarm-clock exemption so app standby cannot defer the handoff. The system may briefly show a next-alarm indicator during these ten seconds. Cancellation removes that launch. The helper requires Android's **Display over other apps** permission for the background Activity launch; it does not display overlays.

The installation token is a random local asset and is copied privately into Kodi's navigation add-on data. Keep signing keys, APK assets and tokens outside public source control. The receiver cannot change profiles, stop playback, access account credentials or launch arbitrary applications.

Build against Android API 30, min API 26, using Google's SDK build tools and D8. Package the private `handoff-token` asset, compile `ArmReceiver.java`, add classes.dex, align and sign the APK. Compile the native `KodiProfileLauncher.java` client against the same Android SDK. Installation and end-to-end testing are required; source compilation alone is insufficient.

Rollback: restore the original `profile_switch.py` and protected manifest, cancel any pending handoff, then uninstall `org.kodimanager.profileswitch` and remove the private Kodi token. This bypasses one unsafe native teardown path; it does not repair Kodi's native job manager or guarantee against unrelated crashes.

## Integration is opt-in

This source kit is not installed by MCP or Kodi Manager. It applies only to Android Kodi
22.0-BETA2, and accepts exactly two profile names from the user's own profiles.xml.
Do not deploy it to stable Kodi or other builds without reproducing the failure first.

The agent must first confirm the TV is free, take a private backup, and inspect the current
profile names and Kodi build. Build a unique APK/token per device; do not distribute a
preconfigured APK. Copy `kodi/profile_restart.py` and the `kodi/profile_restart/` directory
into the existing navigation add-on `script.kodi.live.tv`. Place the compiled client
`classes.dex` beside `relaunch.sh`. Keep the token at
`special://masterprofile/addon_data/script.kodi.live.tv/profile-handoff-token`.
The navigation action should call `profile_restart.restart(target)` only when
`profile_restart.required()` returns true. The existing navigation add-on itself is
not part of this source kit. Retain its normal path on unaffected Kodi builds.

Install the locally signed helper APK and grant **Display over other apps**. The agent
must verify a successful authenticated arm/cancel acknowledgment before wiring the action.
Test both directions while idle, then an owned paused episode, retaining the original
watched/resume records. A successful process restart does not prove video decoding works.

`build.py` builds and verifies the APK and client without contacting or modifying a TV.
Use a private output directory outside the checkout. It creates and retains a per-device
signing key and token there; keep them for updates and rollback. Supply installed SDK paths:

```sh
python contrib/profile-relaunch/build.py --android-jar /path/to/android.jar \
  --build-tools /path/to/build-tools --r8-jar /path/to/r8.jar \
  --java-home /path/to/jdk --output /private/path/profile-relaunch
```

The tested Shield completed nine repeated switches plus a paused episode switch. Its pause
position was stored exactly; POV playback resumes with its normal short rewind. Typical
switches took 13–22 seconds. Native Kodi teardown remains unfixed; this is a guarded workaround.
No private household logs, profiles, provider patches, signing material or prebuilt APK is shipped.
