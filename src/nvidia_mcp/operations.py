"""Device operations. UI disruption and offline file changes have distinct guards."""

import ast
import difflib
import json
import re
import shlex
import threading
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import PurePosixPath
from urllib.parse import parse_qs, unquote, urlsplit

from defusedxml.ElementTree import fromstring

from . import privacy
from .apks import ApkOperations
from .config import ShieldError
from .files import MAX_FILE, Files, digest, relative

READ_METHODS = {
    "JSONRPC.Version",
    "Application.GetProperties",
    "GUI.GetProperties",
    "Addons.GetAddonDetails",
    "Profiles.GetProfiles",
    "Profiles.GetCurrentProfile",
    "Player.GetActivePlayers",
    "Player.GetProperties",
    "Player.GetItem",
    "Settings.GetSettingValue",
    "Settings.GetSettings",
    "Settings.GetCategories",
    "Settings.GetSections",
    "XBMC.GetInfoLabels",
    "XBMC.GetInfoBooleans",
    "VideoLibrary.GetMovies",
    "VideoLibrary.GetTVShows",
    "VideoLibrary.GetSeasons",
    "VideoLibrary.GetEpisodes",
    "VideoLibrary.GetRecentlyAddedMovies",
    "VideoLibrary.GetRecentlyAddedEpisodes",
}
LIBRARY_DEFAULT = 50
LIBRARY_MAX = 500
BUTTONS = {
    "up": "19",
    "down": "20",
    "left": "21",
    "right": "22",
    "select": "23",
    "back": "4",
    "home": "3",
    "menu": "82",
    "play_pause": "85",
    "stop": "86",
}
KODI = "org.xbmc.kodi"
# The single set of home-screen packages treated as "nothing else is being watched".
# Extend with NVIDIA_MCP_EXTRA_LAUNCHERS (comma-separated package names).
LAUNCHERS = frozenset(
    {
        "com.google.android.tvlauncher",
        "com.google.android.apps.tv.launcherx",
        "com.android.tv.launcher",
        "com.spocky.projengmenu",
    }
)
# Kodi core settings that weaken security or expose services. kodi_set_setting refuses them.
PROTECTED_PREFIXES = (
    "services.",  # web server, auth, ports, event server, zeroconf, UPnP, AirPlay, SMB...
    "masterlock.",
    "system.",
    "debug.",
    "pvrparental.",
    "network.httpproxy",
    "network.usehttpproxy",
)
PROTECTED_SETTINGS = frozenset(
    {"addons.unknownsources", "addons.updatemode", "general.addonupdates", "lookandfeel.skin"}
)
# Harmless exceptions inside protected prefixes.
UNPROTECTED_SETTINGS = frozenset({"debug.showloginfo"})


def protected_setting(setting, allowed=()):
    """True when a core setting is on the security/service denylist and not explicitly allowed."""
    name = setting.lower()
    if name in UNPROTECTED_SETTINGS or name in {a.lower() for a in allowed}:
        return False
    return name in PROTECTED_SETTINGS or name.startswith(PROTECTED_PREFIXES)


# kodi_browse refuses plugin routes whose path segments, query keys or values contain an
# action verb. Matching is per word (camelCase/snake_case/dotted split), by prefix.
UNSAFE_STEMS = (
    "play",
    "resolve",
    "toggle",
    "refresh",
    "clear",
    "clean",
    "delete",
    "remove",
    "install",
    "uninstall",
    "setting",
    "auth",
    "login",
    "logout",
    "maintenance",
    "manager",
    "rescan",
    "reset",
    "update",
    "input",
    "keyboard",
    "dialog",
    "context",
    "execute",
    "runscript",
    "download",
    "sync",
    "mark",
    "unmark",
    "rate",
    "subscribe",
    "unsubscribe",
    "favourite",
    "favorite",
)
UNSAFE_WORDS = frozenset({"sign", "signin", "signout", "signup", "run", "add", "rename", "edit"})
SAFE_WORDS = frozenset(
    {"playlist", "playlists", "author", "authors", "updated", "inputstream", "rated", "rating"}
)
# Display text, not routing; only their names are checked.
FREE_TEXT_KEYS = frozenset({"name", "title", "label", "plot", "tagline", "originaltitle"})


def unsafe_words(value):
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", unquote(value))
    return [
        word
        for word in re.split(r"[^a-z0-9]+", value.lower())
        if word
        and word not in SAFE_WORDS
        and (word in UNSAFE_WORDS or word.startswith(UNSAFE_STEMS))
    ]


def unsafe_plugin_route(url):
    """Words in a plugin:// path or query that suggest playback, auth or a mutating utility."""
    p = urlsplit(url)
    found = unsafe_words(p.path)
    for key, values in parse_qs(p.query, keep_blank_values=True).items():
        found += unsafe_words(key)
        if key.lower() not in FREE_TEXT_KEYS:
            for value in values:
                found += unsafe_words(value)
    return found


def field(result, key, method):
    """Read a JSON-RPC result field, turning a missing key into an actionable error."""
    if not isinstance(result, dict) or key not in result:
        raise ShieldError(
            f"Kodi {method} returned no '{key}'; check the setting/add-on id and Kodi version",
            "invalid_response",
        )
    return result[key]


def text(data):
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise ShieldError("File is not UTF-8 text; it cannot be shown or patched") from None


def foreground(transport):
    """Return the one resumed foreground package, or refuse when it is ambiguous/unknown."""
    text = transport.shell("dumpsys", "activity", "activities", limit=2_000_000)
    lines = [
        line
        for line in text.splitlines()
        if "mResumedActivity" in line or "topResumedActivity" in line
    ]
    packages = {
        match[1]
        for line in lines
        if (match := re.search(r"\b([A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+)/", line))
    }
    if len(packages) != 1:
        raise ShieldError(
            "Foreground TV app is unknown; no disruptive action performed", "foreground_unknown"
        )
    return packages.pop()


class Operations:
    def __init__(self, transport):
        self.t = transport
        self.c = transport.c
        self.files = Files(transport)
        self.lock = threading.RLock()
        self.plans = {}
        self.known_secrets = (self.c.password, self.c.manager_token)
        self.apks = ApkOperations(self)

    def safe(self, result):
        return privacy.scrub(result, self.known_secrets)

    def writes(self):
        if not self.c.allow_writes:
            raise ShieldError(
                "Write tools are disabled. Set NVIDIA_MCP_ALLOW_WRITES=1 in your MCP client and restart the server"
            )

    def idle(self, allow_offline=False):
        try:
            players = self.t.rpc("Player.GetActivePlayers")
        except ShieldError:
            if allow_offline:
                return "Kodi HTTP unavailable; explicitly permitted offline recovery"
            raise ShieldError("Playback state is unknown; no disruptive action performed") from None
        if not isinstance(players, list):
            raise ShieldError("Playback state is unknown; no disruptive action performed")
        if players:
            raise ShieldError("Kodi is playing. Wait until viewing has finished")
        return "idle"

    def running(self, package=KODI):
        """The one process probe; ``|| true`` keeps a stopped app from being an ADB error."""
        return bool(self.t.shell("sh", "-c", "pidof " + shlex.quote(package) + " || true"))

    def kodi_running(self):
        return self.running(KODI)

    def launchers(self):
        return LAUNCHERS | set(getattr(self.c, "extra_launchers", ()) or ())

    def require_interrupt_opt_in(self, flag):
        if not getattr(self.c, "allow_interrupt", False):
            raise ShieldError(
                f"{flag}=true was refused: interrupting viewing also needs the user to set "
                "NVIDIA_MCP_ALLOW_INTERRUPT=1 in the MCP client and restart the server. "
                "No action performed",
                "interrupt_not_permitted",
            )

    def guard_tv(
        self,
        kind,
        allow_override=False,
        *,
        allow_offline=False,
        assume_running=False,
        package=None,
        override_flag="allow_during_playback",
    ):
        """One guard for every UI-disruptive action.

        Combines Kodi playback state, the Android foreground app (checked against one shared
        launcher set) and whether Kodi / a target package is running. ``allow_override`` is
        model-controlled, so it is honoured only with NVIDIA_MCP_ALLOW_INTERRUPT=1.
        ``kind`` is one of remote, lifecycle, layout, browse, apk.
        """
        if allow_override:
            self.require_interrupt_opt_in(override_flag)
        state = {"kind": kind, "override": bool(allow_override)}
        if assume_running:
            # Skip the ADB probe: the playback query establishes the state on its own.
            running = True
        else:
            running = self.kodi_running()
        if kind in ("layout", "browse") and not running:
            raise ShieldError("Kodi is not running; start it first", "kodi_stopped")
        if running and not allow_override:
            state["playback"] = self.idle(allow_offline)
        app = foreground(self.t)
        state["foreground"] = app
        if app not in self.launchers() | {KODI} and not allow_override:
            raise ShieldError(
                f"Another TV app ({app}) is in the foreground. Get the viewer's permission "
                f"before setting {override_flag}=true; no disruptive action performed",
                "other_app_foreground",
            )
        if package and (running if package == KODI else self.running(package)):
            raise ShieldError("Stop the target app before installing its APK", "app_running")
        state["kodi_running"] = running
        return state

    def stopped(self):
        if self.kodi_running():
            raise ShieldError(
                "Stop Kodi before editing files; Kodi can overwrite changes while running"
            )

    def audit(self, operation, target, backup_id=None):
        self.c.state.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.c.state.chmod(0o700)
        p = self.c.state / "audit.jsonl"
        with p.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "time": time.time(),
                        "operation": operation,
                        "target": target,
                        "backup_id": backup_id,
                    }
                )
                + "\n"
            )
        p.chmod(0o600)

    def shield_status(self):
        from .diagnostics import health

        props = {}
        for key in (
            "ro.product.model",
            "ro.build.version.release",
            "ro.build.version.sdk",
            "ro.product.cpu.abi",
        ):
            props[key] = self.t.shell("getprop", key)
        memory = self.t.shell("cat", "/proc/meminfo", limit=64000)
        storage = self.t.shell("df", "-k", "/data", "/sdcard", limit=16000)
        telemetry = {}
        for name, args in {
            "uptime": ("cat", "/proc/uptime"),
            "thermal": ("dumpsys", "thermalservice"),
        }.items():
            try:
                telemetry[name] = self.t.shell(*args, limit=64000)
            except ShieldError:
                telemetry[name] = ""
        return {
            "properties": props,
            "storage": storage,
            "memory": memory.splitlines()[:6],
            "kodi_running": self.kodi_running(),
            "health": health(memory, storage, telemetry["uptime"], telemetry["thermal"]),
        }

    def kodi_status(self):
        result = {}
        connection_error = None
        queries = {
            "application": ("Application.GetProperties", {"properties": ["version", "name"]}),
            "screen": (
                "GUI.GetProperties",
                {"properties": ["currentwindow", "currentcontrol", "skin"]},
            ),
            "profile": ("Profiles.GetCurrentProfile", {}),
            "players": ("Player.GetActivePlayers", {}),
        }
        for name, (method, params) in queries.items():
            if connection_error:
                result[name] = {"unavailable": connection_error}
                continue
            try:
                result[name] = self.t.rpc(method, params)
            except ShieldError as exc:
                result[name] = {"unavailable": str(exc)}
                if str(exc).startswith(("Cannot reach", "Authentication denied")):
                    connection_error = str(exc)
        result["capabilities"] = {
            "writes_enabled": self.c.allow_writes,
            "plugin_browse_enabled": self.c.allow_plugin_browse,
            "manager_configured": bool(self.c.manager_token),
            "file_access": "mounted share" if self.c.mount else "ADB",
        }
        return self.safe(result)

    def rpc_read(self, method, params):
        if method not in READ_METHODS:
            raise ShieldError("Method is outside the read-only allowlist; use a dedicated tool")
        if method == "Settings.GetSettingValue" and privacy.SECRET.search(
            str(params.get("setting", ""))
        ):
            raise ShieldError(
                "Credential values are not exposed; inspect redacted settings instead"
            )
        if len(json.dumps(params)) > 12_000:
            raise ShieldError("Parameters exceed size limit")
        if method.startswith("VideoLibrary."):
            params = dict(params)
            limits = params.get("limits") or {}
            start = limits.get("start", 0) if isinstance(limits, dict) else 0
            end = limits.get("end") if isinstance(limits, dict) else None
            if not isinstance(start, int) or start < 0:
                start = 0
            if not isinstance(end, int) or end <= start or end - start > LIBRARY_MAX:
                end = start + (LIBRARY_DEFAULT if end is None else LIBRARY_MAX)
            params["limits"] = {"start": start, "end": end}
        return self.safe(self.t.rpc(method, params))

    def addons(self, enabled_only=False):
        params = {
            "properties": ["name", "version", "enabled", "type"],
            "limits": {"start": 0, "end": 500},
        }
        if enabled_only:
            params["enabled"] = True
        return self.safe(self.t.rpc("Addons.GetAddons", params))

    def read_file(self, path):
        data = self.files.read(path)
        return {
            "path": relative(path),
            "sha256": digest(data),
            "bytes": len(data),
            "content": privacy.file_text(text(data), self.known_secrets),
            "note": "Content is redacted; checksum describes the original file. Use exact non-secret anchors for patches.",
        }

    def logs(self, previous=False, lines=250):
        if not 1 <= lines <= 1000:
            raise ShieldError("Choose 1–1000 log lines")
        content = privacy.text(
            self.files.tail("temp/kodi.old.log" if previous else "temp/kodi.log", lines),
            self.known_secrets,
        )
        patterns = {
            "crash": r"fatal|segmentation|crash|signal 11|SIGSEGV",
            "python": r"PythonToCppException|Traceback|Error Type:",
            "stream": r"curl.*(?:error|timeout)|read.*error|EOF|buffering|CVideoPlayer.*error",
            "shutdown": r"service.*stop.*timeout|script.*stopp|thread.*join",
            "storage": r"write error|no space|permission denied|read.only file",
        }
        return {
            "lines": content,
            "signals": {k: len(re.findall(v, content, re.I)) for k, v in patterns.items()},
            "note": "Signals are clues, not a root-cause verdict. This is a bounded tail, not the whole log.",
        }

    def lifecycle(self, action, allow_offline=False, interrupt_other_app=False):
        self.writes()
        with self.lock:
            # A stopped Kodi cannot be playing, and its HTTP API is down, so the
            # playback check would always report "unknown". Skip it only then.
            self.guard_tv(
                "lifecycle",
                interrupt_other_app,
                allow_offline=allow_offline,
                assume_running=action != "start",
                override_flag="interrupt_other_app",
            )
            if action in ("stop", "restart"):
                self.t.shell("am", "force-stop", "org.xbmc.kodi")
                self.stopped()
            if action in ("start", "restart"):
                self.t.shell("am", "start", "-n", "org.xbmc.kodi/.Splash")
            self.audit("kodi_" + action, "org.xbmc.kodi")
            return {
                "requested": action,
                "note": "Run kodi_status to verify startup; launching an activity does not confirm Kodi is ready.",
            }

    def remote(self, button, allow_during_playback=False):
        self.writes()
        if button not in BUTTONS:
            raise ShieldError("Unknown remote button")
        with self.lock:
            self.guard_tv("remote", allow_during_playback)
            self.t.shell("input", "keyevent", BUTTONS[button])
            self.audit("remote", button)
        return {"sent": button}

    def connect(self):
        self.t.adb("connect", self.c.serial, device=False)
        return {"state": self.t.adb("get-state").decode().strip()}

    def rebuild_layout(self):
        self.writes()
        with self.lock:
            self.guard_tv("layout")
            result = self.t.manager("/api/widgets/layout/rebuild", "POST", {})
            self.audit("rebuild_layout", "active profile")
            return self.safe(result)

    PATCH_SUFFIXES = (".py", ".xml", ".json", ".properties", ".txt")

    def _patch_plan(self, path, expected_sha256, edits):
        """Validate and compute a patch without writing. Returns (before, after) bytes."""
        relative(path)
        suffix = PurePosixPath(path).suffix
        if suffix not in self.PATCH_SUFFIXES:
            raise ShieldError("Only Kodi text configuration/source files can be patched")
        if path.startswith("addons/") and suffix in (".py", ".pyo"):
            raise ShieldError(
                "Add-on Python code cannot be patched by an agent; update the add-on instead",
                "addon_code",
            )
        edits = [e.model_dump() if hasattr(e, "model_dump") else e for e in edits or []]
        if not re.fullmatch(r"[a-f0-9]{64}", expected_sha256) or not 1 <= len(edits) <= 20:
            raise ShieldError("Provide a SHA-256 and 1–20 exact edits")
        before = self.files.read(path)
        if digest(before) != expected_sha256:
            raise ShieldError("File changed since inspection; patch cancelled")
        content = original = text(before)
        for edit in edits:
            old, new = (edit.get("before"), edit.get("after")) if isinstance(edit, dict) else (0, 0)
            if (
                not isinstance(old, str)
                or not old
                or not isinstance(new, str)
                or content.count(old) != 1
            ):
                raise ShieldError(
                    "Each before anchor must occur exactly once; no fuzzy replacements"
                )
            if privacy.contains_secret(old) or privacy.contains_secret(new):
                raise ShieldError(
                    "Edits that touch credentials or secret settings are refused", "secret_edit"
                )
            content = content.replace(old, new, 1)
        data = content.encode("utf-8")
        if len(data) > MAX_FILE:
            raise ShieldError("Patched file exceeds the size limit")
        try:
            if suffix == ".py":
                ast.parse(content)
            elif suffix == ".xml":
                fromstring(content)
            elif suffix == ".json":
                json.loads(content)
        except Exception:
            raise ShieldError("Patched file failed syntax validation; no write performed") from None
        changed_lines = [
            line[1:]
            for line in difflib.unified_diff(
                original.splitlines(), content.splitlines(), lineterm="", n=0
            )
            if line[:1] in "+-" and not line.startswith(("+++", "---"))
        ]
        try:
            touched = privacy.secret_fields(original, suffix) != privacy.secret_fields(
                content, suffix
            )
        except Exception:
            touched = True  # The original is unparseable; be conservative.
        if touched or any(privacy.contains_secret(line) for line in changed_lines):
            raise ShieldError(
                "Edits that touch credentials or secret settings are refused", "secret_edit"
            )
        return before, data, len(edits)

    def patch_preview(self, path, expected_sha256, edits):
        with self.lock:
            before, data, count = self._patch_plan(path, expected_sha256, edits)
        old = privacy.text(text(before), self.known_secrets).splitlines()
        new = privacy.text(text(data), self.known_secrets).splitlines()
        diff = list(difflib.unified_diff(old, new, "a/" + path, "b/" + path, lineterm="", n=2))
        return {
            "dry_run": True,
            "path": path,
            "before_sha256": digest(before),
            "after_sha256": digest(data),
            "edits": count,
            "changed": before != data,
            "diff": "\n".join(diff[:400]) + ("\n... (diff truncated)" if len(diff) > 400 else ""),
            "note": "Diff is redacted. Apply with kodi_patch_apply using the same arguments.",
        }

    def patch_apply(self, path, expected_sha256, edits):
        self.writes()
        with self.lock:
            before, data, _ = self._patch_plan(path, expected_sha256, edits)
            self.stopped()
            backup = self.files.snapshot(path, before)
            try:
                self.files.write(path, data, expected_sha256)
            except Exception:
                raise ShieldError(
                    "Patch failed; original backup is "
                    + backup
                    + ". Inspect current file before restoring"
                ) from None
            self.audit("patch_file", path, backup)
            return {
                "path": path,
                "sha256": digest(data),
                "backup_id": backup,
                "restart_required": True,
            }

    def patch_file(self, path, expected_sha256, edits, dry_run=True):
        """Deprecated combined entry point kept for existing agents."""
        if dry_run:
            return self.patch_preview(path, expected_sha256, edits)
        return self.patch_apply(path, expected_sha256, edits)

    def restore_file(self, backup_id, expected_current_sha256):
        self.writes()
        with self.lock:
            self.stopped()
            path, data = self.files.restore_data(backup_id)
            current = self.files.read(path)
            if digest(current) != expected_current_sha256:
                raise ShieldError("Current checksum differs; restore cancelled")
            safety = self.files.snapshot(path, current)
            self.files.write(path, data, expected_current_sha256)
            self.audit("restore_file", path, safety)
            return {"path": path, "sha256": digest(data), "undo_backup_id": safety}

    def directory(self, path, start=0, limit=24):
        if not self.c.allow_plugin_browse:
            raise ShieldError(
                "Directory execution is opt-in: set NVIDIA_MCP_ALLOW_PLUGIN_BROWSE=1. Installed add-ons may fetch remote metadata"
            )
        if not 0 <= start <= 10_000 or not 1 <= limit <= 48 or len(path) > 12_000:
            raise ShieldError("Directory preview bounds exceeded")
        p = urlsplit(path)
        if p.username or p.password or p.fragment or any(ord(c) < 32 for c in path):
            raise ShieldError("Invalid directory path")
        if p.scheme == "plugin":
            if not p.netloc.startswith("plugin.video."):
                raise ShieldError("Only video add-on directories can be previewed")
            words = unsafe_plugin_route(path)
            if words:
                raise ShieldError(
                    "Interactive/playback/utility action cannot be previewed (route contains: "
                    + ", ".join(sorted(set(words))[:5])
                    + ")",
                    "unsafe_route",
                )
            self.guard_tv("browse")
            addon = field(
                self.t.rpc(
                    "Addons.GetAddonDetails", {"addonid": p.netloc, "properties": ["enabled"]}
                ),
                "addon",
                "Addons.GetAddonDetails",
            )
            if not addon.get("enabled"):
                raise ShieldError("Video add-on is not enabled")
        elif not (
            p.scheme in ("videodb", "library")
            or path.startswith("special://profile/playlists/video/")
        ):
            raise ShieldError(
                "Choose an installed video plugin, video library or profile video playlist"
            )
        else:
            self.guard_tv("browse")
        result = self.t.rpc(
            "Files.GetDirectory",
            {
                "directory": path,
                "media": "video",
                "properties": [
                    "title",
                    "art",
                    "plot",
                    "year",
                    "season",
                    "episode",
                    "playcount",
                    "resume",
                ],
                "limits": {"start": start, "end": start + limit},
            },
        )
        return self.safe(result)

    def set_core_setting(self, setting, value):
        self.writes()
        if privacy.SECRET.search(setting) or not re.fullmatch(r"[a-zA-Z0-9_.-]+", setting):
            raise ShieldError("Credential settings cannot be changed through this tool")
        if protected_setting(setting, getattr(self.c, "allow_settings", ())):
            raise ShieldError(
                f"{setting} is a protected security/service setting (web server, add-on sources "
                "and updates, master lock, system, debug, proxy or skin) and cannot be changed "
                "by an agent. Change it on the TV, or the user can list this exact id in "
                "NVIDIA_MCP_ALLOW_SETTINGS",
                "protected_setting",
            )
        if type(value) not in (bool, int, float, str) or len(str(value)) > 500:
            raise ShieldError("Use a short primitive setting value")
        with self.lock:
            self.idle()
            old = field(
                self.t.rpc("Settings.GetSettingValue", {"setting": setting}),
                "value",
                "Settings.GetSettingValue",
            )
            path = self.profile_userdata() + "/guisettings.xml"
            backup = self.files.snapshot(path, self.files.read(path))
            accepted = self.t.rpc("Settings.SetSettingValue", {"setting": setting, "value": value})
            new = field(
                self.t.rpc("Settings.GetSettingValue", {"setting": setting}),
                "value",
                "Settings.GetSettingValue",
            )
            if accepted is not True or new != value:
                raise ShieldError("Kodi did not confirm the new setting; backup is " + backup)
            self.audit("set_core_setting", setting, backup)
            return self.safe(
                {"setting": setting, "previous": old, "current": new, "backup_id": backup}
            )

    def manager_read(self, area):
        endpoints = {
            "layout": "/api/widgets/layout",
            "sources": "/api/widgets/sources",
            "health": "/api/health",
            "pipeline": "/api/pipeline",
            "fixes": "/api/fixes",
        }
        return self.safe(self.t.manager(endpoints[area]))

    def widget_cache(self):
        """Kodi Manager 0.6+ widget cache: status plus cached row definitions (read-only)."""
        try:
            status = self.t.manager("/api/widget-cache")
            rows = self.t.manager("/api/widget-cache/rows")
        except ShieldError as exc:
            if exc.kind == "service_error":
                raise ShieldError(
                    "Kodi Manager did not offer the widget-cache API; it needs Kodi Manager 0.6+",
                    "unsupported",
                ) from None
            raise
        return self.safe({"status": status, "rows": rows})

    def widget_cache_refresh(self):
        self.writes()
        with self.lock:
            self.idle()
            result = self.t.manager("/api/widget-cache/refresh", "POST", {})
            self.audit("widget_cache_refresh", "active profile")
            return self.safe(result)

    def backup_file(self, path):
        data = self.files.read(path)
        return {
            "backup_id": self.files.snapshot(path, data),
            "sha256": digest(data),
            "bytes": len(data),
        }

    def settings_page(self, tree, query, start, limit):
        if not 0 <= start <= 10_000 or not 1 <= limit <= 50 or len(query) > 200:
            raise ShieldError("Choose 1–50 settings per page and a short search query")
        rows = []

        def visit(node):
            if isinstance(node, dict):
                if "id" in node and "value" in node:
                    if (
                        query.lower()
                        in (str(node["id"]) + " " + str(node.get("label", ""))).lower()
                    ):
                        rows.append(
                            {
                                k: v
                                for k, v in node.items()
                                if k
                                in (
                                    "id",
                                    "label",
                                    "type",
                                    "value",
                                    "default",
                                    "options",
                                    "editable",
                                    "secret",
                                    "value_source",
                                )
                            }
                        )
                else:
                    for value in node.values():
                        visit(value)
            elif isinstance(node, list):
                for value in node:
                    visit(value)

        visit(tree)
        return self.safe(
            {
                "settings": rows[start : start + limit],
                "total": len(rows),
                "start": start,
                "next_start": start + limit if start + limit < len(rows) else None,
            }
        )

    def core_settings(self, query="", start=0, limit=25):
        return self.settings_page(
            self.t.rpc("Settings.GetSettings", {"level": "expert"}), query, start, limit
        )

    def addon_settings(self, addon_id, query="", start=0, limit=25):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", addon_id):
            raise ShieldError("Invalid add-on ID")
        if self.c.manager_token:
            return self.settings_page(
                self.t.manager(f"/api/addons/{addon_id}/settings"), query, start, limit
            )
        root = fromstring(
            self.files.read(f"{self.profile_userdata()}/addon_data/{addon_id}/settings.xml")
        )
        rows = [
            {
                "id": n.get("id"),
                "value": n.get("value", n.text or ""),
                "value_source": "saved XML; defaults/schema not included",
            }
            for n in root.iter("setting")
            if n.get("id")
        ]
        return self.settings_page(rows, query, start, limit)

    def profile_userdata(self):
        """Resolve the actual profile instead of silently editing the master profile."""
        root = fromstring(self.files.read("userdata/profiles.xml"))
        profiles = root.findall("profile")
        try:
            label = field(
                self.t.rpc("Profiles.GetCurrentProfile"), "label", "Profiles.GetCurrentProfile"
            )
        except ShieldError:
            if self.kodi_running():
                raise ShieldError(
                    "Kodi is running but its active profile cannot be queried; no profile assumed"
                ) from None
            last = root.findtext("lastloaded", "0")
            matches = [p for p in profiles if p.get("id") == last]
        else:
            matches = [p for p in profiles if p.findtext("name") == label]
        if len(matches) != 1:
            raise ShieldError(
                "Cannot uniquely resolve the active Kodi profile; inspect profiles.xml"
            )
        path = matches[0].findtext("directory", "").rstrip("/")
        if path in ("special://masterprofile", "") and matches[0].get("id") == "0":
            return "userdata"
        if path.startswith("profiles/") and ".." not in PurePosixPath(path).parts:
            return relative("userdata/" + path)
        raise ShieldError("Unsupported profile directory; use explicit Kodi-relative file tools")

    def set_addon_setting(self, addon_id, expected_version, setting, value):
        self.writes()
        if (
            not re.fullmatch(r"[A-Za-z0-9_.-]+", addon_id)
            or not re.fullmatch(r"[A-Za-z0-9_.-]+", setting)
            or privacy.SECRET.search(setting)
        ):
            raise ShieldError("Invalid or credential-related add-on setting")
        if type(value) not in (bool, int, float, str) or len(str(value)) > 500:
            raise ShieldError("Use a short primitive setting value")
        with self.lock:
            metadata = fromstring(self.files.read(f"addons/{addon_id}/addon.xml"))
            if metadata.get("id") != addon_id or metadata.get("version") != expected_version:
                raise ShieldError("Installed add-on version differs from the inspected version")
            if self.c.manager_token:
                self.idle()
                result = self.t.manager(
                    f"/api/addons/{addon_id}/settings",
                    "PATCH",
                    {"changes": [{"id": setting, "value": value}]},
                )
                self.audit("set_addon_setting", addon_id + ":" + setting, result.get("backup_id"))
                return self.safe(result)
            self.stopped()
            path = f"{self.profile_userdata()}/addon_data/{addon_id}/settings.xml"
            before = self.files.read(path)
            root = fromstring(before)
            nodes = [n for n in root.iter("setting") if n.get("id") == setting]
            if len(nodes) != 1:
                raise ShieldError(
                    "Only existing, unambiguous saved settings can be edited without Manager"
                )
            node = nodes[0]
            new = str(value).lower() if isinstance(value, bool) else str(value)
            if "value" in node.attrib:
                node.set("value", new)
            else:
                node.text = new
            node.attrib.pop("default", None)
            data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            backup = self.files.snapshot(path, before)
            self.files.write(path, data, digest(before))
            self.audit("set_addon_setting", addon_id + ":" + setting, backup)
            return {"changed_count": 1, "backup_id": backup, "restart_required": True}

    def layout_preview(self, plan):
        if (
            not isinstance(plan, dict)
            or not plan.get("section_id")
            or not plan.get("expected_revision")
            or not isinstance(plan.get("rows"), list)
            or len(plan["rows"]) > 20
            or len(json.dumps(plan)) > 100_000
        ):
            raise ShieldError(
                "Provide a section_id, expected_revision and up to 20 complete rows from manager layout"
            )
        self.idle()
        with self.lock:
            result = self.t.manager("/api/widgets/layout/preview", "POST", plan)
            preview_id = uuid.uuid4().hex
            profile = self.t.rpc("Profiles.GetCurrentProfile").get("label")
            if not profile:
                raise ShieldError("Cannot bind preview to the active profile")
            self.plans[preview_id] = (time.monotonic(), json.loads(json.dumps(plan)), profile)
            self.plans = {k: v for k, v in self.plans.items() if time.monotonic() - v[0] < 600}
            return self.safe({"preview_id": preview_id, "expires_seconds": 600, "preview": result})

    def layout_apply(self, preview_id):
        self.writes()
        with self.lock:
            self.idle()
            saved = self.plans.get(preview_id)
            if not saved or time.monotonic() - saved[0] > 600:
                raise ShieldError(
                    "Preview expired or belongs to another MCP session; preview again"
                )
            if self.t.rpc("Profiles.GetCurrentProfile").get("label") != saved[2]:
                raise ShieldError(
                    "Kodi profile changed after preview; preview the intended profile again"
                )
            result = self.t.manager("/api/widgets/layout/apply", "POST", saved[1])
            del self.plans[preview_id]
            self.audit("apply_layout", saved[1]["section_id"], result.get("backup_id"))
            return self.safe(result)
