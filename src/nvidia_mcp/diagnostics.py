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


def health(memory, storage, uptime, thermal):
    metrics = {
        key: int(value)
        for key, value in re.findall(r"^(MemTotal|MemAvailable):\s*(\d+)\s*kB", memory, re.M)
    }
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
