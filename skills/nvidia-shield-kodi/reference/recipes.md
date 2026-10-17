# Recipes

Each recipe assumes you already ran the triage in SKILL.md §2. Stay read-only unless the person asked
for a change and write mode is on. "Full profile" means `NVIDIA_MCP_TOOL_PROFILE=full` is set in the
server's private environment; it adds tools but no permissions.

## Buffering, stutter, or a stream that won't start

1. Get the time it happened and what was playing. Read `kodi_read_logs` around that time.
2. Look for transport errors (timeouts, HTTP 4xx/5xx, `CCurlFile`), decoder errors (`MediaCodec`,
   `InstanceGuard locked`, "open failed") and cache/storage warnings.
3. Check `shield_get_status` for low free memory or storage, and other apps in the foreground.
4. Interpret:
   - Transport errors → the source or provider, not Kodi's buffer. Suggest another source or a retry
     with a fresh link. Do not apply generic "advancedsettings buffer" tweaks without evidence.
   - Decoder errors → codec/hardware path (HEVC, Dolby Vision, 4K on older devices). Check
     `kodi_list_settings(query="videoplayer")` before suggesting changes.
   - Audio playing but no picture after a source switch counts as a failed video start, not success.
5. Which source a provider picks, autoplay and debrid priority are the **provider add-on's**
   settings (`kodi_list_addon_settings`), not the skin's.

## No sound, wrong audio track, soundbar/AVR passthrough

1. Ask what the audio path is: TV speakers, a soundbar over HDMI ARC/eARC, or an AV receiver. Don't
   guess.
2. Read audio settings: `kodi_list_settings(query="audiooutput")`.
3. TV speakers usually need decoded PCM (passthrough off). A receiver can take passthrough for the
   formats it supports. Change only what matches the hardware the person described.
4. Audio-device and refresh-rate settings are protected and `kodi_set_setting` refuses them. Explain
   the TV menu path for the person to change it themselves.
5. A preferred-language setting cannot guarantee a file has that track.

## Add-on errors, "check the log" pop-ups, crashes to home

1. `kodi_read_logs` (`lines` up to 1000, `previous=true` for the run before a crash): find the first `ERROR` or Python traceback and the add-on ID in it.
2. `kodi_list_addons`: note that add-on's version and its dependencies' versions.
3. A native crash (Kodi vanishes with no Python traceback): in the full profile, read a short
   `shield_read_logs` tail for `FATAL`, `SIGSEGV` or a tombstone.
4. Usual fixes, in order: update the add-on through Kodi, reconfigure it, report it upstream.
   Do not patch add-on Python code: the server refuses it, and updates overwrite it.
5. Warnings are not crashes. Say which lines actually matter.

## Kodi won't open, or the tools can't reach it

1. `shield_check_connection` separates ADB, Kodi HTTP and Kodi Manager. Fix only the part that fails.
2. ADB unauthorised → the person accepts the prompt on the TV (`shield_connect_adb` can trigger it).
   Warn them first: it appears over whatever is on screen.
3. Kodi HTTP down but ADB fine → Kodi is closed, or its web-server setting or password changed. With
   write mode and the person's OK, `kodi_control_lifecycle` can start Kodi.
4. Don't force-stop or do "offline recovery" unless the person explicitly asks. Both are refused
   while anything is playing.

## Change a Kodi or add-on setting

1. Find it: `kodi_list_settings` (core) or `kodi_list_addon_settings` (one add-on), using `query`
   rather than paging through everything.
2. Change it: `kodi_set_setting` / `kodi_set_addon_setting`. Credentials and protected settings are
   refused.
3. Verify the read-back value. Core settings reach guisettings.xml only on a clean Kodi exit, so tell
   the person a crash before then loses the change.
4. Undo: set the previous value again. On Android, the guisettings.xml snapshot from step 2 can be
   restored with `kodi_restore_file` while Kodi is stopped.

## Repair a text/XML file (full profile, write mode)

1. Read `addons/<id>/addon.xml` to confirm the version; fixes are version-specific.
2. `kodi_read_file` the target and keep its SHA-256.
3. `kodi_preview_file_patch` with exact before/after text. Show the person the diff.
4. With permission and nobody watching, stop Kodi with `kodi_control_lifecycle`. If it reports a hung
   exit, stop: Kodi is still running.
5. `kodi_apply_file_patch` with the same edits. Keep the `backup_id`.
6. Start Kodi, check `kodi_get_status`, and test the behaviour that was broken.
7. Roll back: stop Kodi, then `kodi_restore_file(backup_id, expected_current_sha256)` (the hash from `kodi_read_file`).

## Home-screen rows in Bingie (optional Kodi Manager)

These tools need the Kodi Manager companion and its token. The standard profile lists them only when a token is configured; the full profile always lists them, so a listed tool is not proof that Kodi Manager is set up.

1. `kodi_inspect_manager(area="layout")`: read section IDs, rows and the revision.
2. `kodi_preview_layout` with the **complete** row list for that section. Missing rows are removed,
   so keep all existing row properties.
3. Show the preview, get approval, `kodi_apply_layout(preview_id)`, then `kodi_rebuild_layout` once.
   The skin visibly reloads on the TV.
4. To find real folder paths for rows, `kodi_browse_directory` needs its own opt-in
   (`NVIDIA_MCP_ALLOW_PLUGIN_BROWSE=1`). It runs the add-on's code. Never invent plugin routes.
5. Unknown skin or Manager versions are view-only. Don't try to bypass that.

## Upgrade Kodi or another APK (full profile, write mode)

1. Do this only when the person asks and has the APK file on the computer. Follow the repository's
   `docs/apk-upgrades.md` exactly. It needs Android SDK build tools.
2. `shield_preview_apk_upgrade` verifies signer, version and ABI and saves the installed originals.
   Review the result with the person.
3. Make sure nobody will use the TV for a few minutes. Stop Kodi with `kodi_control_lifecycle`.
4. `shield_apply_apk_upgrade(preview_id)`. Never retry automatically. On a timeout, check
   `shield_get_apk_backup` first, because the install may have finished.
5. Never uninstall or downgrade Kodi to fix a configuration problem.
