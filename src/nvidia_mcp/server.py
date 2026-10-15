"""Stdio-only MCP entry point for one configured Android TV / Fire OS / Apple TV device.

No HTTP listener and no arbitrary shell or RPC tool: device access is a fixed set of
argument-quoted ADB commands and allowlisted Kodi JSON-RPC methods. Write and disruptive tools
are registered only when NVIDIA_MCP_ALLOW_WRITES=1.
"""

import argparse
import functools
import inspect
import json
import sys
import time
from importlib.resources import files
from typing import Annotated, Any, Literal

import anyio
from pydantic import BaseModel, ConfigDict, Field

try:  # mcp 1.x
    from mcp.server.fastmcp import Context, FastMCP, Image
except ImportError:  # mcp 2.x renamed FastMCP to MCPServer
    from mcp.server.mcpserver import Context, Image
    from mcp.server.mcpserver import MCPServer as FastMCP
from mcp.types import ToolAnnotations

from . import __version__, privacy
from .apple_tv import make_operations
from .catalog import TOOL_NAMES, advertised_names
from .config import Config, ShieldError
from .diagnostics import readiness, support_bundle
from .operation_records import CONTEXT, REFUSALS, correlation, next_step, record
from .operations import READ_METHODS
from .retention import prune_state

ReadMethod = Literal[tuple(sorted(READ_METHODS))]
Button = Literal[
    "up", "down", "left", "right", "select", "back", "home", "menu", "play_pause", "stop"
]
KodiPath = Annotated[
    str,
    Field(
        description="Path relative to .kodi, e.g. userdata/advancedsettings.xml; no absolute paths or traversal"
    ),
]
FileHash = Annotated[
    str, Field(description="Original SHA-256 from kodi_read_file; must still match the file")
]
AddonId = Annotated[
    str,
    Field(description="Installed Kodi add-on ID from kodi_list_addons, e.g. plugin.video.example"),
]
SearchQuery = Annotated[
    str,
    Field(
        description="Case-insensitive setting ID/label search, max 200 characters; empty lists all"
    ),
]
PageStart = Annotated[
    int,
    Field(
        description="Zero-based result offset, 0–10000; use the returned next offset to continue"
    ),
]
SettingsLimit = Annotated[int, Field(description="Maximum settings per page, 1–50")]
SettingValue = Annotated[
    bool | int | float | str,
    Field(description="New value with the setting's reported JSON type; never supply credentials"),
]


class CatalogServer(FastMCP):
    """Advertise canonical names; route existing clients' names to the same guarded tools."""

    async def list_tools(self):
        tools = await super().list_tools()
        return [tool for tool in tools if tool.name in self.advertised_tools]

    async def call_tool(self, name, arguments, *args, **kwargs):
        # MCP 2.x supplies a request Context; 1.x resolves it in the base method.
        return await super().call_tool(TOOL_NAMES.get(name, name), arguments, *args, **kwargs)


class PatchEdit(BaseModel):
    """One exact replacement. ``before`` must occur exactly once in the file."""

    before: str = Field(min_length=1, max_length=100_000, description="Exact existing text")
    after: str = Field(max_length=100_000, description="Replacement text")


PatchEdits = Annotated[
    list[PatchEdit],
    Field(
        description="Ordered exact replacements; each before string must occur once; reuse the previewed edits when applying"
    ),
]


class LayoutRow(BaseModel):
    """A row as returned by kodi_inspect_manager(area='layout'), optionally edited."""

    model_config = ConfigDict(extra="allow")
    id: str | None = Field(
        None, description="Existing row id from the layout; omit to add a new row"
    )
    label: str | None = Field(None, max_length=100, description="Plain-text row label")
    path: str | None = Field(
        None,
        max_length=4096,
        description="plugin://plugin.video.* directory chosen with kodi_browse_directory",
    )
    action: str | None = Field(None, description="Existing action; cannot be changed")


class LayoutPlan(BaseModel):
    """Desired rows for one existing Manager hub section."""

    model_config = ConfigDict(extra="allow")
    section_id: str = Field(min_length=1, description="Section id, e.g. 'hub:moviehub'")
    expected_revision: str = Field(min_length=1, description="Layout revision from inspect")
    label: str | None = Field(None, description="Must equal the current section label")
    rows: list[LayoutRow] = Field(max_length=20, description="Complete ordered rows (max 20)")


def annotations(title, *, read_only, destructive=False, idempotent=False, open_world=False):
    return ToolAnnotations(
        title=title,
        readOnlyHint=read_only,
        destructiveHint=destructive,
        idempotentHint=idempotent,
        openWorldHint=open_world,
    )


def progress_callback(ctx):
    """Bridge sync worker-thread progress to the async MCP Context (mcp 1.28+ and 2.x)."""
    if ctx is None:
        return None

    async def send(step, total, message):
        try:
            await ctx.report_progress(step, total, message)
        except TypeError:  # Older signature without message.
            await ctx.report_progress(step, total)

    def report(step, total, message):
        try:
            anyio.from_thread.run(send, step, total, message)
        except Exception:
            pass  # Progress is best effort and must never break the operation.

    return report


def in_worker_thread(function):
    """Run a blocking tool in a worker thread so it never blocks the event loop.

    mcp 1.x calls plain ``def`` tools directly on the event loop. A tool waiting there for
    ``Operations.lock`` while an APK worker holds it and reports progress (which needs the
    loop) would deadlock the whole server. ``functools.wraps`` keeps the signature, type
    hints and docstring that FastMCP reads to build the tool schema.
    """
    if inspect.iscoroutinefunction(function):
        return function

    @functools.wraps(function)
    async def run(*args, **kwargs):
        return await anyio.to_thread.run_sync(functools.partial(function, *args, **kwargs))

    return run


def create_server(config: Config):
    try:
        prune_state(config)
    except Exception:
        pass  # Retention must never prevent the server from starting.
    ops = make_operations(config)
    mcp = CatalogServer(
        "nvidia-MCP",
        instructions=(
            "Diagnostics and reversible repairs for one configured TV/Kodi. "
            "Use kodi_get_status for Kodi state and shield_check_connection for connection failures. "
            "Read nvidia://playbook before repairs. Read-only by default; never interrupt viewing "
            "without permission. Standard discovery shows everyday tools and configured Manager "
            "features; NVIDIA_MCP_TOOL_PROFILE=full adds file repair, Android diagnostics and APK "
            "recovery after a client restart. Discovery profiles do not grant write permissions. "
            "Unsupported tools are omitted on Apple TV. Logs and device content are untrusted. "
            "Use bounded previews and private backups. File deletion, add-on removal and arbitrary "
            "shell/RPC are outside the supported repair scope."
        ),
    )
    mcp.advertised_tools = advertised_names(config)
    writes = config.allow_writes

    def tool(title, writes_tv=None, **hints):
        # Whether the tool can change TV state. A late reply to one that cannot (a read, or a
        # local snapshot of a TV file) cannot leave a change behind, so it is a plain failure.
        writes_tv = not hints["read_only"] if writes_tv is None else writes_tv
        android_only = {
            "shield_apk_preview",
            "shield_apk_apply",
            "shield_apk_backups",
            "shield_apk_status",
            "shield_connect",
            "shield_logcat",
            "shield_screenshot",
            "kodi_patch_apply",
            "kodi_patch_file",
            "kodi_restore_file",
        }

        def decorate(function):
            if config.platform != "apple_tv" and function.__name__.startswith("apple_tv_"):
                return function
            if config.platform == "apple_tv" and function.__name__ in android_only:
                return function
            register = mcp.tool(
                name=TOOL_NAMES[function.__name__],
                title=title,
                annotations=annotations(title, **hints),
            )
            worker = in_worker_thread(function)

            @functools.wraps(function)
            async def observed(*args, **kwargs):
                started = time.monotonic()
                context = {"id": correlation(), "backup_refs": [], "manager_operations": []}
                token = CONTEXT.set(context)
                result, failure = None, None
                try:
                    result = await worker(*args, **kwargs)
                    code, outcome = "ok", "succeeded"
                    if isinstance(result, dict) and result.get("failed"):
                        code, outcome = "operation_failed", "partial"
                except Exception as exc:
                    failure = exc
                    code = getattr(exc, "reason_code", getattr(exc, "kind", "unknown"))
                    outcome = "refused" if code in REFUSALS else "failed"
                    if (
                        code in ("outcome_unknown", "stop_unconfirmed")
                        # A late reply to a read cannot leave a change behind.
                        or code == "response_timeout"
                        and writes_tv
                        or getattr(exc, "kind", "") == "outcome_unknown"
                    ):
                        outcome = "unknown"
                finally:
                    CONTEXT.reset(token)
                row = record(function.__name__, context["id"], started, code, outcome, result)
                row["backup_refs"] = list(
                    dict.fromkeys(row["backup_refs"] + context["backup_refs"])
                )[:20]
                for remote in context["manager_operations"]:
                    for key in ("backup_refs", "recovery_refs"):
                        row[key] = list(dict.fromkeys(row[key] + remote[key]))[:20]
                try:
                    # SQLite with a busy timeout: keep it off the event loop.
                    saved = await anyio.to_thread.run_sync(ops.history.append, row)
                except Exception:
                    saved = False
                if not saved:
                    ops.history.available = False
                if failure is not None:
                    # FastMCP 1.x and 2.x preserve ToolError text; use only value-free metadata.
                    manager = context["manager_operations"]
                    remote = manager[-1] if manager else None
                    ref = remote["operation_id"] if remote else row["operation_id"]
                    message = (
                        # .message, not str(): the reason tag is appended once, below.
                        privacy.text(failure.message[:1000].rstrip(".") + ".", ops.known_secrets)
                        if isinstance(failure, ShieldError)
                        else "Operation failed; inspect current state before retrying."
                    )
                    raise ShieldError(
                        f"{message} Operation reference: {ref}; correlation: {row['correlation_id']}. "
                        + next_step(
                            "outcome_unknown" if outcome == "unknown" else row["reason_code"]
                        ),
                        row["reason_code"],
                    ) from None
                if isinstance(result, dict):
                    result = dict(result, operation=row, history_recorded=bool(saved))
                    if context["manager_operations"]:
                        result["manager_operations"] = context["manager_operations"]
                    if not saved:
                        result["diagnostic_warning"] = "history_unavailable"
                return result

            return register(observed)

        return decorate

    def write_tool(title, destructive=True, **hints):
        """Register only when writes are enabled; otherwise the tool does not exist."""
        if writes:
            return tool(title, read_only=False, destructive=destructive, **hints)
        return lambda function: function

    @tool("TV status", read_only=True, idempotent=True)
    def shield_status() -> dict[str, Any]:
        """Read device-level status: Android telemetry/foreground state, or paired Apple TV model/playback/power/capabilities. Use kodi_get_status for Kodi's profile, skin and players; shield_check_connection diagnoses access failures. No playback changes."""
        return ops.shield_status()

    @tool("TV connection check", read_only=True, idempotent=True)
    def shield_connection() -> dict[str, Any]:
        """Check connection readiness for platform controls, Kodi HTTP and optional Manager separately; returns per-service availability and actionable pairing/authorization failures. Use this for setup or unreachable tools, shield_get_status for device telemetry. Does not pair or connect a new device; Android authorization is handled by shield_connect_adb."""
        return readiness(ops)

    @tool("Private support bundle", read_only=True, idempotent=True)
    def shield_support_bundle() -> dict[str, Any]:
        """Collect a bounded diagnostic bundle for troubleshooting/support: readiness, versions, capabilities and value-free operation/recovery metadata. Use shield_check_connection for a quick access check. Excludes logs, arguments and viewing history; returns private data to the client and never uploads it."""
        return support_bundle(ops)

    @tool("Preview APK upgrade", read_only=False, destructive=False)
    async def shield_apk_preview(
        apk_paths: Annotated[
            list[str],
            Field(
                description="1–20 absolute paths to APK files on this computer; include all splits for one package"
            ),
        ],
        ctx: Context,
        trusted_signers: Annotated[
            list[str] | None,
            Field(
                description="Optional SHA-256 signer fingerprints to narrow the configured trust set; cannot add trust"
            ),
        ] = None,
    ) -> dict[str, Any]:
        """Stage 1–20 local APKs, verify hardware serial/SDK/ABI/signers and save the installed originals (pulls up to 1 GB from the TV over the network; refused while any media is playing or paused). A stable hardware serial is required. New apps need signers configured in NVIDIA_MCP_TRUSTED_SIGNERS; trusted_signers can only narrow that set. No TV changes."""
        progress = progress_callback(ctx)
        return await anyio.to_thread.run_sync(
            lambda: ops.apks.preview(apk_paths, trusted_signers, progress)
        )

    @write_tool("Install previewed APK")
    async def shield_apk_apply(
        preview_id: Annotated[
            str,
            Field(
                description="Unexpired preview_id returned by shield_preview_apk_upgrade; installs exactly those verified APKs"
            ),
        ],
        ctx: Context,
    ) -> dict[str, Any]:
        """Install an exact unexpired APK preview, replacing the installed app. Stopped target/idle TV, backup and readback required; reports progress. The install can take minutes after the last TV check, and an app opened meanwhile is closed by Android. Never uninstalls/downgrades/retries."""
        progress = progress_callback(ctx)
        return await anyio.to_thread.run_sync(lambda: ops.apks.apply(preview_id, progress))

    @tool("APK recovery bundles", read_only=True, idempotent=True)
    def shield_apk_backups() -> dict[str, Any]:
        """List private APK recovery bundles for this TV, with phases and Kodi data snapshot checksums."""
        return ops.apks.backups()

    @tool("APK recovery bundle status", read_only=True, idempotent=True)
    def shield_apk_status(
        backup_id: Annotated[
            str,
            Field(
                description="APK recovery bundle ID from shield_list_apk_backups; not a Kodi file-backup ID"
            ),
        ],
        verify_checksums: Annotated[
            bool,
            Field(
                description="Hash saved local APK/data files too; false checks metadata and file presence only"
            ),
        ] = False,
    ) -> dict[str, Any]:
        """Inspect one APK recovery bundle's phase, saved files and installed TV version. Use shield_list_apk_backups to discover IDs; verify_checksums also reads local backup bytes. Does not install or restore anything."""
        return ops.apks.status(backup_id, verify_checksums)

    @tool("Connect ADB", read_only=False, destructive=False, idempotent=True, open_world=True)
    def shield_connect() -> dict[str, Any]:
        """Connect ADB to the configured TV only. A new or revoked authorization shows Android's debugging prompt on the TV over whatever is playing; someone at the TV must accept it."""
        return ops.connect()

    @tool("Installed TV apps", read_only=True, idempotent=True)
    def shield_apps() -> dict[str, Any]:
        """List Android package names or paired Apple TV app names/bundle IDs; no account data."""
        if config.platform == "apple_tv":
            return ops.safe({"apps": ops.t.apple.apps()})
        return {"packages": ops.t.shell("pm", "list", "packages").splitlines()}

    @tool("Android log tail", read_only=True, idempotent=True)
    def shield_logcat(
        lines: Annotated[int, Field(description="Number of recent Android log lines, 1–500")] = 150,
    ) -> dict[str, Any]:
        """Read a bounded Android log tail for native crashes. Redaction is best effort."""
        if not 1 <= lines <= 500:
            raise ShieldError("Choose 1–500 Android log lines")
        return {
            "lines": privacy.text(
                ops.t.shell("logcat", "-d", "-t", str(lines), limit=600_000), ops.known_secrets
            )
        }

    @tool("TV screenshot", read_only=True)
    def shield_screenshot() -> Image:
        """Return a PNG image of the current Android TV screen (up to 6 MB), without navigation. Screens can contain private information. For text diagnostics use shield_get_status or kodi_read_logs."""
        data = ops.t.adb("exec-out", "screencap", "-p", limit=6_000_000)
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ShieldError("TV did not return a PNG screenshot")
        return Image(data=data, format="png")

    @write_tool("Remote button")
    def shield_remote(
        button: Annotated[
            Button,
            Field(
                description="One remote key; home leaves Kodi, play_pause/stop control only Kodi playback"
            ),
        ],
        allow_during_playback: Annotated[
            bool,
            Field(
                description="Explicit playback override for play_pause/stop; also requires NVIDIA_MCP_ALLOW_INTERRUPT=1 and viewer permission"
            ),
        ] = False,
    ) -> dict[str, Any]:
        """Send one remote button while idle; Apple TV requires active Kodi. play_pause/stop need allow_during_playback plus NVIDIA_MCP_ALLOW_INTERRUPT=1 and control only Kodi's player. Home switches to the TV home screen."""
        return ops.remote(button, allow_during_playback)

    @write_tool("Start/stop Kodi")
    def kodi_lifecycle(
        action: Annotated[
            Literal["start", "stop", "restart"],
            Field(
                description="Kodi process action; start/restart can bring Kodi onto the TV screen"
            ),
        ],
        allow_offline_recovery: Annotated[
            bool,
            Field(
                description="Android stop/restart with unreachable Kodi HTTP; also requires NVIDIA_MCP_ALLOW_OFFLINE_RECOVERY=1"
            ),
        ] = False,
        interrupt_other_app: Annotated[
            bool,
            Field(
                description="Permit interrupting another Android app only with NVIDIA_MCP_ALLOW_INTERRUPT=1 and viewer permission; never overrides Kodi playback"
            ),
        ] = False,
    ) -> dict[str, Any]:
        """Start/stop/restart Kodi while idle. Android: a hung quit can be force-stopped only with saved-settings evidence; offline recovery needs two opt-ins. Apple TV: paired launch and graceful quit only, no force-stop or offline recovery; another app's playback is never overridden. interrupt_other_app needs NVIDIA_MCP_ALLOW_INTERRUPT=1. Launch does not prove readiness."""
        return ops.lifecycle(action, allow_offline_recovery, interrupt_other_app)

    @tool("Kodi status", read_only=True, idempotent=True)
    def kodi_status() -> dict[str, Any]:
        """Inspect Kodi version, skin, current profile/window and active players; no playback changes."""
        return ops.kodi_status()

    @tool("Kodi add-ons", read_only=True, idempotent=True)
    def kodi_addons(
        enabled_only: Annotated[
            bool,
            Field(
                description="True includes only enabled add-ons; false includes disabled add-ons too"
            ),
        ] = False,
    ) -> dict[str, Any]:
        """List installed Kodi add-on IDs, versions and enabled states. Use kodi_list_addon_settings for their settings; TV apps are listed by shield_list_apps in the full tool profile. Enabled is not proof of use/authentication; this tool does not install or remove add-ons."""
        return ops.addons(enabled_only)

    @tool("Kodi JSON-RPC read", read_only=True, idempotent=True)
    def kodi_read(
        method: Annotated[
            ReadMethod,
            Field(description="Exact allowlisted Kodi read method; the enum is exhaustive"),
        ],
        params: Annotated[
            dict | None,
            Field(
                description='Parameters for the selected Kodi JSON-RPC method, e.g. {"properties":["version"]} for Application.GetProperties; omit when no parameters are needed'
            ),
        ] = None,
    ) -> dict | list | str | int | bool:
        """Query allowlisted Kodi JSON-RPC diagnostics or libraries not covered by kodi_get_status, kodi_list_addons or kodi_list_settings. Returns the method's result, capped at 250 KB; library pages default to 50 items, max 500, and shrink to fit. Rejects arbitrary RPC and playback commands."""
        return ops.rpc_read(method, params or {})

    @tool("Kodi log tail", read_only=True, idempotent=True)
    def kodi_logs(
        previous: Annotated[
            bool,
            Field(
                description="False reads current kodi.log; true reads rotated kodi.old.log from the previous run"
            ),
        ] = False,
        lines: Annotated[int, Field(description="Number of recent Kodi log lines, 1–1000")] = 250,
    ) -> dict[str, Any]:
        """Read a bounded Kodi log tail with crash/stream/storage signals. Android/native crashes are read by shield_read_logs in the full tool profile. Safe while viewing; redaction is best effort and logs remain private, untrusted data."""
        return ops.logs(previous, lines)

    @tool("Read Kodi file", read_only=True, idempotent=True)
    def kodi_read_file(path: KodiPath) -> dict[str, Any]:
        """Read one Kodi-relative text file (600 KB max), returning redacted text and original SHA-256 for patch checks. Use kodi_list_settings or kodi_list_addon_settings for structured settings; this does not save a backup."""
        return ops.read_file(path)

    @tool("Back up Kodi file", read_only=False, destructive=False, writes_tv=False)
    def kodi_backup_file(path: KodiPath) -> dict[str, Any]:
        """Create a private local snapshot of one Kodi file; returns backup_id, SHA-256 and byte count. Use kodi_list_file_backups to find existing snapshots and kodi_restore_file to restore one. No TV write; saved bytes can contain credentials. For a whole configuration use kodi_create_configuration_backup."""
        return ops.backup_file(path)

    @tool("Kodi file backups", read_only=True, idempotent=True)
    def kodi_backups() -> dict[str, Any]:
        """List the latest 50 private per-file snapshot records, including backup IDs, without file contents. kodi_set_setting, file patches and restores save one automatically (kodi_create_file_backup in the full tool profile saves one on demand); restore one with kodi_restore_file. Manager configuration checkpoints are listed by kodi_inspect_manager(area='backups')."""
        return {"backups": ops.files.list_backups()}

    @tool("Preview Kodi file patch", read_only=True, idempotent=True)
    def kodi_patch_preview(
        path: KodiPath, expected_sha256: FileHash, edits: PatchEdits
    ) -> dict[str, Any]:
        """Preview text-file repair with exact replacements; returns a redacted unified diff without writing. Read the file/hash with kodi_read_file first, then use kodi_apply_file_patch. For ordinary Kodi/add-on settings use kodi_set_setting/kodi_set_addon_setting instead. Credential edits and add-on .py files are refused."""
        return ops.patch_preview(path, expected_sha256, edits)

    @write_tool("Apply Kodi file patch")
    def kodi_patch_apply(
        path: KodiPath, expected_sha256: FileHash, edits: PatchEdits
    ) -> dict[str, Any]:
        """Apply exactly the text edits reviewed with kodi_preview_file_patch; returns backup/verification details. Requires Kodi stopped and a matching SHA, and creates an undo backup. For ordinary settings use kodi_set_setting/kodi_set_addon_setting; credential edits and add-on .py files are refused."""
        return ops.patch_apply(path, expected_sha256, edits)

    @write_tool("Patch Kodi file (deprecated)")
    def kodi_patch_file(
        path: str, expected_sha256: str, edits: list[PatchEdit], dry_run: bool = True
    ) -> dict[str, Any]:
        """Deprecated: use kodi_preview_file_patch and kodi_apply_file_patch. dry_run=true previews, false applies."""
        return ops.patch_file(path, expected_sha256, edits, dry_run)

    @write_tool("Restore Kodi file")
    def kodi_restore_file(
        backup_id: Annotated[
            str,
            Field(
                description="Per-file snapshot ID from kodi_list_file_backups; not a Manager checkpoint or APK bundle"
            ),
        ],
        expected_current_sha256: Annotated[
            str,
            Field(
                description="SHA-256 of the current target from kodi_read_file; prevents overwriting changes made since inspection"
            ),
        ],
    ) -> dict[str, Any]:
        """Restore one local per-file snapshot while Kodi is stopped; returns verification and undo-backup details. Rejects stale checksums and creates an undo snapshot. Use kodi_restore_configuration for Manager configuration checkpoints."""
        return ops.restore_file(backup_id, expected_current_sha256)

    @tool("Add-on settings", read_only=True, idempotent=True)
    def kodi_addon_settings(
        addon_id: AddonId, query: SearchQuery = "", start: PageStart = 0, limit: SettingsLimit = 25
    ) -> dict[str, Any]:
        """List/search one installed add-on's settings in the active profile, returning a redacted page and pagination metadata. Manager includes schema/defaults; fallback reads saved XML only. Use kodi_list_settings for Kodi core settings, kodi_set_addon_setting to change one; this does not preview file patches or home-screen layouts."""
        return ops.addon_settings(addon_id, query, start, limit)

    @tool("Kodi settings", read_only=True, idempotent=True)
    def kodi_settings(
        query: SearchQuery = "", start: PageStart = 0, limit: SettingsLimit = 25
    ) -> dict[str, Any]:
        """List/search Kodi core settings at expert level, returning a bounded page of IDs, types, current/default values and pagination metadata. Use kodi_list_addon_settings for an add-on's settings and kodi_set_setting to change a core value. Does not read arbitrary files."""
        return ops.core_settings(query, start, limit)

    @write_tool("Change add-on setting", idempotent=True)
    def kodi_set_addon_setting(
        addon_id: AddonId,
        expected_version: Annotated[
            str,
            Field(
                description="Exact installed add-on version from kodi_list_addons; stale versions are refused"
            ),
        ],
        setting: Annotated[
            str, Field(description="Non-credential add-on setting ID from kodi_list_addon_settings")
        ],
        value: SettingValue,
    ) -> dict[str, Any]:
        """Change one add-on setting found with kodi_list_addon_settings; returns backup and verification details. Checks installed version, refuses credentials and backs up first. Manager requires idle Kodi; without Manager, stop Kodi first. Use kodi_set_setting for core settings; text-file repair (kodi_apply_file_patch) is in the full tool profile."""
        return ops.set_addon_setting(addon_id, expected_version, setting, value)

    @write_tool("Change Kodi setting", idempotent=True)
    def kodi_set_setting(
        setting: Annotated[
            str,
            Field(
                description="Kodi core setting ID from kodi_list_settings, e.g. subtitles.align; not an add-on setting ID"
            ),
        ],
        value: SettingValue,
    ) -> dict[str, Any]:
        """Change one ordinary Kodi core setting through its runtime API; returns readback and a guisettings.xml undo snapshot (on Android, restore it with kodi_restore_file). Takes effect on the TV immediately; requires idle Kodi/launcher. Refuses credentials and protected security/service, display, audio-device, refresh-rate and language settings. Use kodi_set_addon_setting for add-ons; text-file repair (kodi_apply_file_patch) is in the full tool profile."""
        return ops.set_core_setting(setting, value)

    @tool("Browse Kodi folder", read_only=False, destructive=False, open_world=True)
    def kodi_browse(
        path: Annotated[
            str,
            Field(
                description="Exact provider/library directory URI, e.g. plugin://plugin.video.example/; never a playback, login or maintenance route"
            ),
        ],
        start: PageStart = 0,
        limit: Annotated[
            int, Field(description="Maximum directory items to return on this page, 1–48")
        ] = 24,
    ) -> dict[str, Any]:
        """Preview one page of actual provider/library folders; opt-in, idle-only. Runs the add-on's own code, which contacts its provider and can show notifications or dialogs on the TV. Routes with play/auth/settings/maintenance verbs are refused; for add-ons Kodi Manager knows (POV, Fen, TMDb Helper, BBC iPlayer) only their listing routes are allowed."""
        return ops.directory(path, start, limit)

    @tool("Kodi Manager inspect", read_only=True, idempotent=True)
    def kodi_manager_inspect(
        area: Annotated[
            Literal["layout", "sources", "health", "pipeline", "fixes", "backups"],
            Field(
                description="Manager report: layout=hubs/rows/revision, sources=providers, health=checks, pipeline=processing, fixes=suggestions, backups=configuration checkpoints"
            ),
        ],
        addon_id: Annotated[
            str | None,
            Field(
                description="Only with area=backups: installed add-on ID for its checkpoints; omit for whole-configuration checkpoints"
            ),
        ] = None,
    ) -> dict[str, Any]:
        """Read one Kodi Manager report for layout planning, diagnostics or checkpoint discovery; requires a configured Manager token. Returns the selected report without changes. Use kodi_get_widget_cache for cache rows, kodi_list_file_backups (listed with writes or the full tool profile) for local file snapshots, kodi_list_addon_settings for individual setting values."""
        return ops.manager_read(area, addon_id)

    @tool("Kodi Manager widget cache", read_only=True, idempotent=True)
    def kodi_manager_widget_cache() -> dict[str, Any]:
        """Read Kodi Manager 0.6+ widget-cache status and cached rows. This inspects stored cache data; kodi_inspect_manager(area='layout') reads configured home-screen rows. Use kodi_refresh_widget_cache to rebuild cache contents; this does not execute provider rows."""
        return ops.widget_cache()

    @write_tool("Refresh widget cache", destructive=False)
    def kodi_manager_widget_cache_refresh() -> dict[str, Any]:
        """Optional Kodi Manager 0.6+: queue a refresh of every cached widget row while Kodi is idle and no other app is in front. Runs each row's add-on in the background on the TV (CPU and network load for a while)."""
        return ops.widget_cache_refresh()

    @tool("Preview hub layout", read_only=False, destructive=False)
    def kodi_layout_preview(
        plan: Annotated[
            LayoutPlan,
            Field(
                description="Complete desired row order for one existing section; copy section_id and expected_revision from kodi_inspect_manager(area=layout)"
            ),
        ],
    ) -> dict[str, Any]:
        """Stage a Kodi Manager home-screen layout plan, returning preview_id and a diff without changing the layout. First inspect area='layout' with kodi_inspect_manager; use kodi_apply_layout after review. Changes row order/content, not individual settings or file text. Requires Manager; stores private preview state."""
        return ops.layout_preview(plan.model_dump(exclude_none=True))

    @write_tool("Apply hub layout")
    def kodi_layout_apply(
        preview_id: Annotated[
            str,
            Field(
                description="preview_id from kodi_preview_layout, valid for 10 minutes; applies that exact staged plan"
            ),
        ],
    ) -> dict[str, Any]:
        """Optional Manager: apply the exact staged plan within 10 minutes, changing the household's home-screen rows; Manager backs up and rejects stale revisions."""
        return ops.layout_apply(preview_id)

    @write_tool("Rebuild skin menus")
    def kodi_layout_rebuild() -> dict[str, Any]:
        """Optional Manager: request one skin-menu rebuild while Kodi is idle and in front. The skin reloads visibly on the TV a few seconds later (after the only check). Inspect TV after it finishes."""
        return ops.rebuild_layout()

    @write_tool("Back up Kodi configuration", destructive=False)
    def kodi_configuration_backup(
        addon_id: Annotated[
            str | None,
            Field(
                description="Installed Kodi add-on ID to checkpoint just its configuration; omit for detected skin/helpers/players"
            ),
        ] = None,
    ) -> dict[str, Any]:
        """Create a Kodi Manager configuration checkpoint for detected skin/helpers/players, or one add-on; returns Manager backup metadata. Idle TV required; private backups may contain credentials. List checkpoints with kodi_inspect_manager(area='backups'), restore with kodi_restore_configuration. For one local file snapshot use kodi_create_file_backup (full tool profile)."""
        return ops.configuration_backup(addon_id)

    @write_tool("Restore Kodi configuration")
    def kodi_configuration_restore(
        backup_id: Annotated[
            str,
            Field(
                description="Manager checkpoint ID from kodi_inspect_manager(area=backups); not a local file or APK backup ID"
            ),
        ],
        addon_id: Annotated[
            str | None,
            Field(
                description="Same add-on ID used when listing its backup; omit for a whole-configuration checkpoint"
            ),
        ] = None,
    ) -> dict[str, Any]:
        """Restore a Kodi Manager configuration checkpoint while idle, returning restore/undo metadata. Match the scope used with kodi_inspect_manager(area='backups'); retains undo backups. Local per-file snapshots are restored by kodi_restore_file on Android. No forced restore, APK downgrade or system recovery."""
        return ops.configuration_restore(backup_id, addon_id)

    @write_tool("Apple TV power")
    def apple_tv_power(
        action: Annotated[
            Literal["on", "off"],
            Field(
                description="on wakes the paired Apple TV; off sleeps it only with verified idle, active Kodi"
            ),
        ],
    ) -> dict[str, Any]:
        """Apple TV only: wake the paired TV, or sleep it after verified idle playback and active Kodi. No automatic app launch."""
        ops.writes()
        with ops.lock:
            if action == "off":
                ops.guard_tv("power")
            ops.t.apple.power(action == "on")
            return {"power_requested": action}

    @mcp.resource("nvidia://playbook")
    def repair_playbook() -> str:
        """Practical lessons from Shield/Kodi repairs, accounts, source selection and Bingie configuration."""
        return files("nvidia_mcp").joinpath("playbook.md").read_text()

    @mcp.resource("nvidia://configuration")
    def configuration() -> str:
        """Configured capabilities without passwords, tokens or local paths."""
        return json.dumps(
            {
                "version": __version__,
                "tool_profile": config.tool_profile,
                "writes": config.allow_writes,
                "interrupt_override": config.allow_interrupt,
                "offline_recovery": config.allow_offline_recovery,
                "plugin_browse": config.allow_plugin_browse,
                "manager": bool(config.manager_token),
                "trusted_signers_configured": len(config.trusted_signers),
                "transport": "stdio",
                "http_route": config.http_route,
                "single_device": True,
            }
        )

    @mcp.prompt()
    def audit_kodi(issue: str = "Improve reliability and usability") -> str:
        """Run a focused, non-disruptive Android TV / Fire OS / Apple TV / Kodi audit."""
        return f"Read nvidia://playbook. Task: {issue}. Inspect kodi_get_status, shield_get_status, kodi_list_addons and at most 250 current/old log lines. Explain evidence, uncertainties and one focused next change. Do not stop playback, change accounts or apply settings without task authorization. Preview exact patches, preserve backups, verify runtime results, and stop testing once appropriate checks pass."

    return mcp, ops


def main():
    parser = argparse.ArgumentParser(
        description="Local Android TV / Fire OS / Apple TV / Kodi MCP server"
    )
    parser.add_argument("--version", action="version", version=__version__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument(
        "--doctor",
        action="store_true",
        help="Probe device controls, Kodi HTTP and optional Manager separately and exit",
    )
    actions.add_argument(
        "--export-manager",
        metavar="DIRECTORY",
        help="Export the bundled optional Kodi Manager ZIP without connecting to the TV",
    )
    actions.add_argument(
        "--pair-adb",
        metavar="PAIRING_PORT",
        type=int,
        help="Pair the configured Android TV host; read the six-digit code privately from stdin",
    )
    actions.add_argument(
        "--pair-apple-tv",
        choices=("Companion", "AirPlay"),
        help="Pair only APPLE_TV_HOST; read the four-digit PIN privately",
    )
    args = parser.parse_args()
    ops = None
    try:
        if args.export_manager:
            from .companion import export_manager

            print(json.dumps(export_manager(args.export_manager), indent=2))
            return 0
        config = Config.from_env()
        if args.pair_apple_tv:
            if config.platform != "apple_tv":
                raise ShieldError("Select NVIDIA_MCP_PLATFORM=apple_tv before pairing")
            from getpass import getpass

            from .apple_bridge import AppleBridge

            bridge = AppleBridge(config)
            try:

                def read_pin():
                    return (
                        getpass("Apple TV PIN: ")
                        if sys.stdin.isatty()
                        else sys.stdin.readline(32).strip()
                    )

                print(json.dumps(bridge.pair(args.pair_apple_tv, read_pin)))
            finally:
                bridge.close()
            return 0
        if args.pair_adb is not None:
            if config.platform != "android":
                raise ShieldError("ADB pairing is unavailable on Apple TV")
            from getpass import getpass

            from .transport import Transport

            try:
                code = (
                    getpass("TV pairing code: ")
                    if sys.stdin.isatty()
                    else sys.stdin.readline(32).strip()
                )
            except (EOFError, KeyboardInterrupt):
                raise ShieldError("ADB pairing cancelled", "pairing_cancelled") from None
            transport = Transport(config)
            try:
                print(json.dumps(transport.pair(args.pair_adb, code)))
            finally:
                transport.close()
            return 0
        mcp, ops = create_server(config)
        if args.doctor:
            result = readiness(ops)
            print(json.dumps(result, indent=2))
            return (
                0
                if result["apple_tv" if config.platform == "apple_tv" else "adb"]["state"]
                == result["kodi_http"]["state"]
                == "ready"
                and result["manager"]["state"] in ("ready", "not_configured")
                else 1
            )
        mcp.run(transport="stdio")
        return 0
    except ShieldError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        if ops is not None:
            ops.t.close()


if __name__ == "__main__":
    sys.exit(main())
