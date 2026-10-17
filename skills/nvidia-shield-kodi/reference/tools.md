# nvidia-MCP tools at a glance

Checked against nvidia-MCP 0.5.12. The server's `tools/list` is the source of truth. If a tool named
here is missing, the server is older, the profile or opt-in below is off, or the device is an Apple TV
(no ADB tools).

## Visibility and permissions

| Setting (server env, set privately by the person) | Effect |
| --- | --- |
| *(default)* standard profile | Everyday read-only tools for status, add-ons, settings and logs |
| `NVIDIA_MCP_ALLOW_WRITES=1` | Registers the write tools. Without it they do not exist |
| `NVIDIA_MCP_TOOL_PROFILE=full` | Adds file, screenshot, Android-log, app and APK tools. Writes still need the opt-in above |
| `KODI_MANAGER_TOKEN` | Lets the Kodi Manager tools work (layout, configuration checkpoints, widget cache). The standard profile lists them only when a token is set; the full profile always lists them, and they fail without the token |
| `NVIDIA_MCP_ALLOW_PLUGIN_BROWSE=1` | Adds `kodi_browse_directory`, which runs add-on code |
| `NVIDIA_MCP_ALLOW_INTERRUPT=1` | Lets play/pause/stop and app interruption through. Ask before suggesting it |

Changing any of these means editing the MCP client's server config and reloading the server. Set
writes and browsing back to `0` when the job is done.

## Which tool for which job

| Job | Read-only | Change (write mode) |
| --- | --- | --- |
| Reachability | `shield_check_connection`, `shield_connect_adb` (no write mode needed; shows the TV prompt) | — |
| TV state | `shield_get_status`, `shield_list_apps`*, `shield_capture_screenshot`* | `shield_send_button` |
| Kodi state | `kodi_get_status`, `kodi_query_rpc` (allowlisted reads) | `kodi_control_lifecycle` |
| Add-ons | `kodi_list_addons`, `kodi_list_addon_settings` | `kodi_set_addon_setting` |
| Core settings | `kodi_list_settings` | `kodi_set_setting` |
| Logs | `kodi_read_logs`, `shield_read_logs`* | — |
| Files | `kodi_read_file`*, `kodi_list_file_backups`*, `kodi_preview_file_patch`*, `kodi_create_file_backup`* (private staging) | `kodi_apply_file_patch`*, `kodi_restore_file`* |
| Kodi Manager | `kodi_inspect_manager`, `kodi_get_widget_cache`, `kodi_preview_layout` | `kodi_apply_layout`, `kodi_rebuild_layout`, `kodi_refresh_widget_cache`, `kodi_create_configuration_backup`, `kodi_restore_configuration` |
| Provider folders | `kodi_browse_directory` (own opt-in) | — |
| APKs* | `shield_list_apk_backups`, `shield_get_apk_backup`, `shield_preview_apk_upgrade` | `shield_apply_apk_upgrade` |
| Support | `shield_get_support_bundle` (private, never upload) | — |

\* full profile. With writes on, the standard profile also lists `kodi_read_file`, `kodi_list_file_backups` and `kodi_restore_file` (the undo path).

Resources and prompts: `nvidia://playbook` (read it first), `nvidia://configuration`, and the
`audit_kodi` prompt for a focused audit that doesn't disturb viewing.

## Guards you will see (don't work around them)

- **Viewing guard:** writes, lifecycle, buttons and browsing are refused while Kodi or another app is
  playing or paused, or while the viewing state is unknown.
- **Checksum guard:** file patches and restores need the current SHA-256. Re-read and re-preview
  instead of forcing.
- **Credential guard:** passwords, tokens and add-on Python code cannot be changed through these
  tools.
- **Version guard:** Bingie layout writes need reviewed skin and Manager versions. Others are
  view-only.
- **Timed-out writes:** check the current state before retrying, because it may have completed.
