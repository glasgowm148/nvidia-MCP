# Profile-handoff integration

Small, offline Android helper for this Shield's Kodi 22 beta 2 / RC1 profile teardown bug. Kodi saves settings and the next startup profile, waits for native jobs, and stops its Python services. At Kodi's logged `Application stopped` checkpoint, a same-UID child ends the process before NVIDIA's final graphics teardown; Android then reopens Kodi. There is no launcher screen, network permission, boot receiver, periodic job or background loop.

## Handoff protocol

`ArmReceiver` accepts explicit, authenticated ordered broadcasts. `ARM` checks relaunch permission and records a two-minute readiness lease; it schedules no launch. The sender must receive the versioned acknowledgment before quitting Kodi. Only after Kodi logs `Application stopped` does the child send `READY`, receive confirmation that Android scheduled the fixed Kodi Splash component one second later (two seconds before helper 1.4), and end the old Kodi process. This avoids consuming the launch while a slow shutdown is still running. Cancellation clears both the lease and any pending launch. Repeated or expired `READY` requests refuse.

`ARMWATCH` (1.3) is `ARM` plus a late reopen 75 seconds out; the script sends it alone (one helper start, about a second, while Kodi waits to quit) and sends `ARM` only if it is refused. `READY` reuses the same pending launch, so a clean shutdown replaces the late reopen with the prompt one. If Android kills Kodi during shutdown (the low-memory killer can take a large Kodi once its activity has finished, and the child goes with it), `READY` never comes and the late reopen brings Kodi back. If the child outlives Kodi it sends `READY` itself instead of cancelling. Helpers before 1.3 refuse `ARMWATCH` without changing anything, and the plain `ARM` that follows applies. `WATCH` (1.2) schedules the same late reopen without a lease, for callers that switch profiles natively and cancel it once the destination profile has loaded.

The one-shot launch uses Android's alarm-clock exemption so app standby cannot defer it. The system may briefly show a next-alarm indicator. The helper requires Android's **Display over other apps** permission for the background Activity launch; it does not display overlays. If Kodi dies before the shutdown checkpoint, only the late `ARMWATCH` reopen applies (helper 1.3): Kodi returns after about 75 seconds without having saved its settings; the retained status shows how far shutdown got.

Helper **1.4 / versionCode 5** (1.3 plus the shorter `READY` delay), the `KodiProfileLauncher` client DEX and `relaunch.sh` must be deployed together while Kodi is stopped. The client rejects the old APK's unversioned acknowledgment before asking Kodi to quit. Retain the installed signing key and private token when rebuilding; an APK replacement with the same signature keeps the existing permission and data.

The installation token is a random local asset and is copied privately into Kodi's navigation add-on data. Keep signing keys, APK assets and tokens outside public source control. The receiver cannot change profiles, stop playback, access account credentials or launch arbitrary applications.

## Build and rollback

Build against Android API 30, min API 26, using Google's SDK build tools and D8. Package the private `handoff-token` asset, compile the receiver and its `Handoff.java` readiness policy, add classes.dex, align and sign the APK. Compile the native `KodiProfileLauncher.java` client against the same Android SDK. Installation and end-to-end testing are required; source compilation alone is insufficient.

Rollback: restore the original `profile_switch.py` and protected manifest, cancel any pending handoff, then uninstall `org.kodimanager.profileswitch` and remove the private Kodi token. This bypasses one unsafe native teardown path; it does not repair Kodi's native job manager or guarantee against unrelated crashes.

## Integration is opt-in

This source kit is not installed by MCP or Kodi Manager. It applies only to Android Kodi
22.0-BETA2 and 22.0-RC1 (`System.BuildVersion` starting `22.0-BETA2` or `22.0-RC1`, for
example `22.0-RC1 (21.90.901) Git:20260927-28ea2eac1e`; RC2, RC10 and final builds are not
matched), and accepts exactly two profile names from the user's own profiles.xml.
Do not deploy it to stable Kodi or other builds without reproducing the failure first, then
add that exact build to `AFFECTED_BUILD` in `profile_restart.py`.

`relaunch.sh` validates the Kodi pid, profile index and log offset individually before arming.
When Android backgrounds Kodi (`XBMCApp: Finishing the activity` in the log) it writes the
destination `<lastloaded>` early, keeping a private copy of the original profiles.xml, so the
switch survives Android reclaiming the process before Kodi's own settings save; it rewrites
the destination after that save as before.

This directory is the canonical source. A copy deployed before 0.4.3 (for example in a
private Kodi Manager `device_fixes` bundle) may have the RC1 gate but not the per-number
validation: compare `sha256sum` of the deployed `relaunch.sh` and `profile_restart.py` with
these files and redeploy them together if they differ.

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

## Verification evidence

Earlier helpers completed nine repeated beta 2 switches and a paused-episode test; those results
do not establish the timing or playback behavior of helper 1.1. The current 1.1 helper completed
Adults → Kids in 29.1 s and Kids → Adults in 23.5 s on the reference Shield / Kodi 22 RC1
(2026-10-12), automatically reopening at Home with both profiles' channel counts checked.
Native Kodi teardown remains unfixed; this is a guarded workaround.
No private household logs, profiles, provider patches, signing material or prebuilt APK is shipped.
