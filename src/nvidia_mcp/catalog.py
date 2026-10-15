"""Canonical tool names and discovery profiles; permissions stay in the operation guards."""

TOOL_NAMES = {
    "shield_status": "shield_get_status",
    "shield_connection": "shield_check_connection",
    "shield_support_bundle": "shield_get_support_bundle",
    "shield_apk_preview": "shield_preview_apk_upgrade",
    "shield_apk_apply": "shield_apply_apk_upgrade",
    "shield_apk_backups": "shield_list_apk_backups",
    "shield_apk_status": "shield_get_apk_backup",
    "shield_connect": "shield_connect_adb",
    "shield_apps": "shield_list_apps",
    "shield_logcat": "shield_read_logs",
    "shield_screenshot": "shield_capture_screenshot",
    "shield_remote": "shield_send_button",
    "kodi_lifecycle": "kodi_control_lifecycle",
    "kodi_status": "kodi_get_status",
    "kodi_addons": "kodi_list_addons",
    "kodi_read": "kodi_query_rpc",
    "kodi_logs": "kodi_read_logs",
    "kodi_read_file": "kodi_read_file",
    "kodi_backup_file": "kodi_create_file_backup",
    "kodi_backups": "kodi_list_file_backups",
    "kodi_patch_preview": "kodi_preview_file_patch",
    "kodi_patch_apply": "kodi_apply_file_patch",
    "kodi_patch_file": "kodi_patch_file",  # Legacy preview/apply facade; never advertised.
    "kodi_restore_file": "kodi_restore_file",
    "kodi_addon_settings": "kodi_list_addon_settings",
    "kodi_settings": "kodi_list_settings",
    "kodi_set_addon_setting": "kodi_set_addon_setting",
    "kodi_set_setting": "kodi_set_setting",
    "kodi_browse": "kodi_browse_directory",
    "kodi_manager_inspect": "kodi_inspect_manager",
    "kodi_manager_widget_cache": "kodi_get_widget_cache",
    "kodi_manager_widget_cache_refresh": "kodi_refresh_widget_cache",
    "kodi_layout_preview": "kodi_preview_layout",
    "kodi_layout_apply": "kodi_apply_layout",
    "kodi_layout_rebuild": "kodi_rebuild_layout",
    "kodi_configuration_backup": "kodi_create_configuration_backup",
    "kodi_configuration_restore": "kodi_restore_configuration",
    "apple_tv_power": "apple_tv_set_power",
}

CORE_TOOLS = {
    "shield_status",
    "shield_connection",
    "shield_support_bundle",
    "shield_connect",
    "kodi_status",
    "kodi_addons",
    "kodi_read",
    "kodi_logs",
    "kodi_addon_settings",
    "kodi_settings",
    "shield_remote",
    "kodi_lifecycle",
    "kodi_set_addon_setting",
    "kodi_set_setting",
    "apple_tv_power",
}
UNDO_TOOLS = {"kodi_backups", "kodi_read_file", "kodi_restore_file"}
MANAGER_TOOLS = {
    "kodi_manager_inspect",
    "kodi_manager_widget_cache",
    "kodi_manager_widget_cache_refresh",
    "kodi_layout_preview",
    "kodi_layout_apply",
    "kodi_layout_rebuild",
    "kodi_configuration_backup",
    "kodi_configuration_restore",
}


def advertised_names(config):
    """Offer everyday tools first, with configured Manager/provider features when available.

    Full discovery adds file repair, Android diagnostics and APK recovery. Existing names and
    unadvertised tools remain callable for compatibility, subject to all existing permissions.
    This is a context/selection preference, never an access-control boundary.
    """
    if config.tool_profile == "full":
        selected = set(TOOL_NAMES)
    else:
        selected = set(CORE_TOOLS)
        if config.manager_token:
            selected |= MANAGER_TOOLS
        if config.allow_writes and config.platform != "apple_tv":
            # The undo path for the everyday setting writes: find the per-file snapshot, read
            # the current hash, restore it. kodi_restore_file is Android-only.
            selected |= UNDO_TOOLS
    if config.allow_plugin_browse:
        selected.add("kodi_browse")
    else:
        selected.discard("kodi_browse")
    selected.discard("kodi_patch_file")
    return {TOOL_NAMES[name] for name in selected}
