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
   increase versionCode and preserve the complete signer set. New installs need signer
   fingerprints the **user** configured in `NVIDIA_MCP_TRUSTED_SIGNERS` (comma-separated SHA-256,
   colons allowed) or `NVIDIA_MCP_TRUSTED_SIGNERS_FILE`. A fingerprint passed by the agent in
   `trusted_signers` is not trust on its own: it can only narrow the configured set, and anything
   outside it is refused. Copying a fingerprint from the candidate APK is not independent
   verification. Key rotation is conservatively refused.
3. Confirm viewing has finished. Stop the target app using an authorized, app-appropriate route and
   verify the foreground state. For Kodi use `kodi_lifecycle` after its playback guard allows it.
   The APK tool does not stop apps or press Home automatically.
4. Enable MCP write mode only for the authorized change, then call `shield_apk_apply(preview_id)`.
   Preview and apply report progress per stage (save originals, Kodi data tar, push, install, verify)
   to MCP clients that request it.
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

Use `shield_apk_backups` to find this Shield's latest recovery bundles and `shield_apk_status(backup_id)`
for one bundle's phase, saved files (optionally re-checked against their SHA-256) and the version now
installed on the Shield. The bundle
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

### Manual recovery

There is no `shield_apk_restore` tool: reinstalling an older APK is a downgrade that Android usually
refuses for production apps, and the only generic workaround (uninstall) erases app data, including
Kodi's `Android/data` folder. A human-reviewed procedure is safer than an automated one. With the
person's authorization and the TV free:

1. `shield_apk_status(backup_id, verify_checksums=true)`: confirm the bundle belongs to this Shield,
   every saved file is present with a matching checksum, and which version is installed now.
2. Stop the app (for Kodi, `kodi_lifecycle stop`) and keep a separate copy of the current data before
   changing anything; for Kodi, `kodi_backup_file` covers single files only, so copy the whole
   `.kodi` folder from the mounted share or with `adb pull`.
3. If the failed install left the **original** version installed (`installed_matches: original`),
   only data may need restoring. If the candidate is installed and works, no recovery is needed.
4. To reinstall the original APKs: `adb install -r <bundle>/0.apk` (or `adb install-multiple -r`
   with every `N.apk` for split apps). If Android reports `INSTALL_FAILED_VERSION_DOWNGRADE`, stop:
   do not uninstall without explicit, informed consent that app data will be lost.
5. To restore Kodi data from `kodi-data.tar`, keep Kodi stopped, list the archive first
   (`tar -tf kodi-data.tar`; only `addons/` and `userdata/` members are expected), then extract it
   into the Kodi root (the mounted share, or push it and run `tar -xf` in
   `/sdcard/Android/data/org.xbmc.kodi/files/.kodi`). Regenerable caches (`userdata/Thumbnails`,
   `addons/packages`, `addons/temp`) were not archived and are rebuilt by Kodi.
6. Start Kodi, run `kodi_status`, and check both profiles and playback before calling it recovered.

## Inspiration

Design review of [Shield Manager](https://github.com/GitJaxder/shield-manager) informed the APK/split,
compatibility and installed-version checks. [Home Control](https://github.com/Yukuhu/home-control)
informed independent connection states; [Shield Control Suite](https://github.com/Smeagol69/shield-control-suite)
informed thermal diagnostics. Implementation here is original; no third-party source was copied.
