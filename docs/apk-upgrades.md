# Agent workflow: verified APK installs and upgrades

The person using the TV only needs the [existing TV preparation](setup.md), permission for the
specific app change, and a free TV. The agent performs computer setup, preview, backups and verification.
Do not ask the person to download APKs, install SDK tools or enter terminal commands.

## Prepare the computer

Use `shield_connection` to check ADB and Kodi HTTP separately. ADB authorization, Kodi's HTTP password
and Manager's token are separate. `nvidia-mcp --doctor` now reports all configured services; an absent
optional Manager is not a failure. Neither readiness nor a foreground-app name proves idle playback.

For APK operations only, install/reuse official
[Android SDK Build Tools](https://developer.android.com/tools/releases/build-tools) and Java.
Resolve `AAPT2_PATH` to the SDK's `aapt2`/`aapt2.exe`, `APKSIGNER_PATH` to `lib/apksigner.jar`, and
`JAVA_PATH` to the Java executable. Merge these values into the existing private MCP configuration
and reload it. JAR invocation avoids Windows batch wrappers; `.bat`/`.cmd` wrappers are refused.
The SDK/JAR is not bundled. Existing diagnostic/repair tools do not need these dependencies.

Choose a local APK from the application's official distribution. For split applications pass the
base APK plus all required feature/configuration splits, matching this device's CPU. This release
does not expand `.apkm`, `.apks` or `.xapk` archives or choose/download updates automatically.
Keep downloads outside the repository. Do not use code, signer certificates or account credentials
embedded in an unrelated project's APK.

## Preview and apply

1. Call `shield_apk_preview` with `apk_paths` containing 1–20 local `.apk` files. The agent verifies
   metadata and signatures using `aapt2` and `apksigner`, checks Android/CPU requirements, and saves
   private staged copies plus verified originals. No Shield files are changed.
2. Review package, installed/candidate versionCode, signer fingerprints and APK count. Updates must
   increase versionCode and preserve the complete signer set. New installs need `trusted_signers`
   containing independently trusted SHA-256 certificate fingerprints; simply copying a fingerprint
   from the candidate is not independent verification. Key rotation is conservatively refused.
3. Confirm viewing has finished. Stop the target app using an authorized, app-appropriate route and
   verify the foreground state. For Kodi use `kodi_lifecycle` after its playback guard allows it.
   The APK tool does not stop apps or press Home automatically.
4. Enable MCP write mode only for the authorized change, then call `shield_apk_apply(preview_id)`.
   Previews expire after ten minutes; they are immutable and tied to this server/configured Shield.
   Re-preview after expiry, a changed app/device, or server restart.
5. Before copying anything to the TV, apply verifies the preview, originals and current installation.
   For an existing Kodi installation it also takes a validated, private archive of `addons` and
   `userdata`, including every profile. It uses `KODI_MOUNT` when configured, otherwise ADB tar.
   Missing data/access, links, unsupported entries or a backup over 2 GB/100,000 entries abort the
   upgrade. No root access or permission bypass is attempted.
6. The agent uploads/checksums APKs, installs the set in one Android package-manager operation/session,
   then reads back installed versionCode and APK hashes. Apply does not start the app. Inspect its
   startup and essential functionality separately; an installed version is not runtime validation.
   Disable write mode when finished.

## Recover from a failed change

Use `shield_apk_backups` to find this Shield's latest recovery bundles and their status. The bundle
is stored under `NVIDIA_MCP_STATE_DIR/apk_backups/<backup_id>` (the default OS-private state directory
is described in `config.py`). It includes original APK files, a manifest with hashes/versions/device,
and `kodi-data.tar` for an existing Kodi upgrade. Backups contain credentials; never upload them.

Apply failures identify the recovery bundle and retain it. A failed transfer/install/readback does
not cause retries or uninstall. Once a transfer starts, the preview is consumed even if installation
fails. Temporary APKs are removed where the device remains reachable. Status distinguishes preparation,
installation and verification; inspect the actual installed state before deciding recovery steps.

APK recovery is deliberately a reviewed manual action in this release. Check all backup hashes and
the target device. Android may reject a production-app downgrade even with the original signed APK;
do not uninstall merely to bypass that restriction, because uninstall can erase app data. Kodi database
migrations may require the saved addons/userdata to accompany the old APK. Keep Kodi stopped, preserve
the failed/current data separately, validate archive paths, and follow an explicitly authorized recovery
plan. There is no claim of guaranteed or automatic rollback, nor a backup of other apps' private data.

## Inspiration

Design review of [Shield Manager](https://github.com/GitJaxder/shield-manager) informed the APK/split,
compatibility and installed-version checks. [Home Control](https://github.com/Yukuhu/home-control)
informed independent connection states; [Shield Control Suite](https://github.com/Smeagol69/shield-control-suite)
informed thermal diagnostics. Implementation here is original; no third-party source was copied.
