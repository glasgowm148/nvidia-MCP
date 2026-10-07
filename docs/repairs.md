# Practical repair flows

## Diagnose without disturbing viewing

Ask the assistant to read `nvidia://playbook`, then use `kodi_status`, `shield_status`, `kodi_addons`,
and bounded current/previous `kodi_logs`. For native crashes add a short `shield_logcat` tail.
Keep the timestamp, Kodi/add-on versions, actual errors and what was playing. Do not stop playback
merely to collect a log. A redacted URL cannot prove which individual stream failed.

## Patch a skin or add-on configuration

Text files under `addons/` and `userdata/` (`.xml`, `.json`, `.properties`, `.txt`, and `.py` outside
`addons/`) can be patched. Add-on Python code under `addons/` and anything touching credentials or
secret settings is refused: update the add-on or change the account on the TV instead.

1. Read its `addons/<id>/addon.xml` to confirm the version.
2. Read the file and retain its SHA-256.
3. Call `kodi_patch_preview` with exact `before`/`after` anchors and review the redacted diff.
4. Review the proposed behaviour and get permission to interrupt if someone is viewing.
5. Enable write mode. Stop Kodi with `kodi_lifecycle`; it refuses active Kodi playback.
6. Apply the same edits with `kodi_patch_apply`. Retain its `backup_id` and new checksum.
   (`kodi_patch_file` with `dry_run=true/false` still works but is deprecated.)
7. Start Kodi, verify `kodi_status` and test the specific behaviour.
8. To roll back: stop Kodi, read the current checksum, call `kodi_restore_file`, then start and verify.

Patches are exact, version-specific repairs, not automatic downloads or blanket replacements.
If an add-on update replaces your patch, inspect the new source/version before reapplying it.
Do not splice redacted credential XML back into the real file.

## Change a setting

Core Kodi settings: read `Settings.GetSettingValue` with `kodi_read`, then use `kodi_set_setting`.
It takes a backup and verifies the runtime value. Revert one setting by setting its previous value;
restoring all of guisettings.xml can also revert unrelated settings.

Add-ons: inspect `kodi_addon_settings` and the add-on version. `kodi_set_addon_setting` uses a Manager
runtime write if configured. Otherwise stop Kodi and edit an existing saved primitive setting in the
resolved last-loaded profile. New settings/defaults, provider-specific databases and credential changes
need a dedicated integration/native setup. Main and Kids profiles must not be silently mixed up.

## Discover useful widget folders

Enable plugin browsing, wait for Kodi to be idle and start at an actual installed video add-on root,
for example `plugin://plugin.video.pov/` if that add-on is installed. Preview at most 24 items per page.
Follow returned folder paths, keep labels and populated item counts, and avoid interactive utilities.
Do not guess provider route parameters or recursively expand every season/episode/pagination folder.

## Live Bingie edits with an existing Manager

Use `kodi_manager_inspect(area="layout")`. Read the saved section IDs, current rows and revision.
To reorder/change rows, submit the full desired row list to `kodi_layout_preview`:

```json
{
  "section_id": "THE_RETURNED_SECTION_ID",
  "expected_revision": "THE_RETURNED_REVISION",
  "rows": [
    {"id": "EXISTING_ROW_ID", "label": "Continue Watching", "path": "OBSERVED_PROVIDER_FOLDER"}
  ]
}
```

That is a structural example, not real IDs/routes. Preserve complete unchanged row properties from
the returned layout. An apply **replaces that section's row list**; omitting existing rows removes them
from the layout. Inspect the preview, authorize the change, apply its preview ID and rebuild once.
Inspect the TV after rebuild. Unsupported versions remain read-only; do not bypass source checks.
