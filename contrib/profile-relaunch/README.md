# Kodi account-switch handoff

Optional source kit for the profile-switch teardown failure observed on one NVIDIA Shield with
Kodi **22.0-BETA2 / 22.0-RC1**. It waits for Kodi's `Application stopped` checkpoint, ends the old
process before final graphics teardown and schedules one automatic reopen. Native teardown remains
unfixed; unrelated crashes are outside this workaround.

## Requirements

- Android API 26+, with builds compiled against API 30 and Google's SDK/D8 tooling.
- Helper **1.4 / versionCode 5**, matching client DEX and script, deployed together (1.2 added
  `WATCH`, 1.3 `ARMWATCH`, 1.4 a one-second `READY` delay; see INTEGRATION.md).
- A unique private signing key/token and **Display over other apps** permission.
- The existing private navigation add-on integration; it is not included in this kit.

MCP and Kodi Manager do not install this helper automatically. Stable Kodi, RC2 and later builds
are outside its current gate. No APK, credentials, profiles or household patches are shipped.

## Build

This builds locally without contacting a TV. Keep the output directory, key and token private;
retain them for signed updates and rollback.

```sh
python contrib/profile-relaunch/build.py --android-jar /path/to/android.jar \
  --build-tools /path/to/build-tools --r8-jar /path/to/r8.jar \
  --java-home /path/to/jdk --output /private/path/profile-relaunch
```

Run from the repository root.

## Integration is opt-in

Follow [integration and rollback](INTEGRATION.md) for the protocol,
version gates, deployment paths and required end-to-end checks. Deployment needs an idle TV and
a private backup.

## Verification limits

Helper 1.1 automatically reopened after both RC1 profile switches on the reference Shield
(29.1 / 23.5 s); see [compatibility evidence](../../docs/compatibility.md).
If Kodi dies before the saved shutdown checkpoint, automatic launch is not scheduled; inspect
retained state and reopen manually. The two-minute readiness lease is consumed once, and cancellation
clears pending work.
