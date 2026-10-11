"""Independent transport readiness and bounded, optional Android health telemetry."""

import re
import shutil
from pathlib import Path

from .android_tools import signer_command
from .config import ShieldError

REMEDIES = {
    "authorization_required": "Select Allow on the Shield debugging prompt, then reconnect.",
    "authentication_denied": "Check this service's credentials; Kodi HTTP and Manager use separate credentials.",
    "offline": "Reconnect the configured Shield; do not restart anything while someone is viewing.",
    "unreachable": "Check the configured IP/port and that this service is enabled on the Shield.",
    "missing_dependency": "The agent should install/configure the required computer tool.",
    "timeout": "Service did not answer in time. Retry a read later; do not repeat writes automatically.",
    "write_disabled": "Kodi Manager Write Mode is off; the user can turn it on in its settings on the TV.",
    "unsupported": "The installed Kodi Manager is older than this tool needs; core tools still work.",
}


def readiness(ops):
    def probe(function):
        try:
            if function() is False:
                raise ShieldError("Service readiness could not be established", "invalid_response")
            return {"state": "ready"}
        except ShieldError as exc:
            return {
                "state": exc.kind,
                "message": str(exc),
                "next_step": REMEDIES.get(
                    exc.kind,
                    "Inspect the relevant service's bounded diagnostics before making changes.",
                ),
            }

    def kodi():
        response = ops.t.rpc("Application.GetProperties", {"properties": ["name", "version"]})
        return (
            isinstance(response, dict)
            and response.get("name") == "Kodi"
            and isinstance(response.get("version"), dict)
        )

    result = {
        "adb": probe(lambda: ops.t.adb("get-state").decode().strip() == "device"),
        "kodi_http": probe(kodi),
        "manager": probe(lambda: isinstance(ops.t.manager("/api/health"), dict))
        if ops.c.manager_token
        else {
            "state": "not_configured",
            "next_step": "Optional; core ADB/Kodi tools work without Manager.",
        },
        "capabilities": {
            "writes_enabled": ops.c.allow_writes,
            "plugin_browse_enabled": ops.c.allow_plugin_browse,
        },
        "note": "Ready means this service answered now. It does not prove the TV is idle or an account is authenticated.",
    }

    def exists(command):
        return bool(shutil.which(command)) or Path(command).is_file()

    try:
        signer = signer_command(ops.c)
        sign = all(exists(command) for command in (signer[0], signer[-1]) if command != "-jar")
    except ShieldError:
        sign = False
    result["apk_tools"] = {
        "aapt2_available": exists(ops.c.aapt2_path),
        "apksigner_available": sign,
        "note": "Availability only; actual APK inspection verifies tool execution and signatures.",
    }
    return ops.safe(result)


def meminfo(text):
    """``/proc/meminfo`` totals in kB: MemTotal, MemAvailable, SwapTotal and SwapFree when present."""
    return {
        key: int(value)
        for key, value in re.findall(
            r"^(MemTotal|MemAvailable|SwapTotal|SwapFree):\s*(\d+)\s*kB", text, re.M
        )
    }


def app_memory(text):
    """``dumpsys meminfo <package>`` App Summary in kB (PSS, native heap, RSS), or None."""
    pss = re.search(r"^\s*TOTAL PSS:\s*(\d+)", text, re.M)
    if not pss:
        return None
    native = re.search(r"^\s*Native Heap:\s*(\d+)", text, re.M)
    rss = re.search(r"TOTAL RSS:\s*(\d+)", text)
    return {
        "pss_kb": int(pss[1]),
        "native_heap_kb": int(native[1]) if native else None,
        "rss_kb": int(rss[1]) if rss else None,
    }


# Android event-log records of a process ending: am_proc_died [user,pid,name,oom_adj,proc_state]
# and am_kill [user,pid,name,oom_adj,reason].
PROCESS_EVENT = re.compile(
    r"^(?P<time>\d\d-\d\d \d\d:\d\d:\d\d\.\d+)\s.*?\b(?P<event>am_proc_died|am_kill)\s*:\s*"
    r"\[\d+,(?P<pid>\d+),(?P<name>[^,\]]+),(?P<adj>-?\d+),(?P<detail>[^\]]*)\]",
    re.M,
)


def process_deaths(events, package):
    """``am_proc_died``/``am_kill`` records for ``package`` from ``logcat -b events``, oldest first."""
    found = []
    for m in PROCESS_EVENT.finditer(events):
        if m["name"] != package:
            continue
        row = {
            "time": m["time"],
            "event": m["event"],
            "pid": int(m["pid"]),
            "oom_adj": int(m["adj"]),
        }
        if m["event"] == "am_proc_died" and m["detail"].isdigit():
            row["proc_state"] = int(m["detail"])
        else:
            row["reason"] = m["detail"][:200]
        found.append(row)
    return found


def health(memory, storage, uptime, thermal):
    metrics = meminfo(memory)
    status = re.search(r"Thermal Status:\s*(\d+)", thermal, re.I)
    temperatures = []
    if "Current temperatures from HAL:" in thermal:
        thermal = thermal.split("Current temperatures from HAL:", 1)[1].split(
            "Current cooling devices from HAL:", 1
        )[0]
    for line in thermal.splitlines():
        match = re.search(
            r"Temperature\{mValue=([\d.]+),\s*mType=(\d+),\s*mName=([^,}]+),\s*mStatus=(\d+)", line
        )
        if match and int(match[2]) in (0, 1):
            temperatures.append(
                {
                    "type": "cpu" if match[2] == "0" else "gpu",
                    "celsius": float(match[1]),
                    "status": int(match[4]),
                }
            )
    try:
        seconds = float(uptime.split()[0])
    except (ValueError, IndexError):
        seconds = None
    free = []
    for line in storage.splitlines()[1:]:
        values = line.split()
        if len(values) >= 6 and values[1].isdigit() and values[3].isdigit():
            free.append(
                {"mount": values[-1], "total_kb": int(values[1]), "available_kb": int(values[3])}
            )
    return {
        "memory_kb": metrics or None,
        "storage": free or None,
        "uptime_seconds": seconds,
        "thermal_status": int(status[1]) if status else None,
        "temperatures": temperatures,
        "note": "Missing telemetry is unavailable, not healthy. Android thermal status 0 means none; 1–6 indicate increasing throttling.",
    }
