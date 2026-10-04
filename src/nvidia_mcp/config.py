"""Explicit, single-device configuration. No network scanning or saved credentials."""

import ipaddress
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


class ShieldError(RuntimeError):
    """An actionable error safe to return to an MCP client."""

    def __init__(self, message, kind="unknown"):
        super().__init__(message)
        self.kind = kind


def private_host(host: str) -> str:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        raise ShieldError("SHIELD_HOST must be a private LAN IP address, not a URL or hostname")
    if (
        not (address.is_private or address.is_loopback)
        or address.is_unspecified
        or address.is_multicast
    ):
        raise ShieldError("Use a private LAN IP address; public endpoints are not supported")
    return host


def port(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise ShieldError("Ports must be integers")
    if not 1 <= number <= 65535:
        raise ShieldError("Port must be between 1 and 65535")
    return number


def state_path() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "nvidia-mcp"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "nvidia-mcp"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "nvidia-mcp"


@dataclass(frozen=True)
class Config:
    host: str
    adb_port: int = 5555
    adb_path: str = "adb"
    kodi_port: int = 8080
    username: str = field(default="", repr=False)
    password: str = field(default="", repr=False)
    manager_port: int = 8765
    manager_token: str = field(default="", repr=False)
    mount: Path | None = None
    state: Path = field(default_factory=state_path)
    allow_writes: bool = False
    allow_plugin_browse: bool = False
    remote_root: str = "/sdcard/Android/data/org.xbmc.kodi/files/.kodi"
    aapt2_path: str = "aapt2"
    apksigner_path: str = "apksigner"
    java_path: str = "java"

    @classmethod
    def from_env(cls):
        host = private_host(os.environ.get("SHIELD_HOST", ""))
        root = os.environ.get("KODI_REMOTE_ROOT", cls.remote_root)
        if not re.fullmatch(
            r"/(?:sdcard|storage/emulated/0)/[A-Za-z0-9_./-]+", root
        ) or ".." in root.split("/"):
            raise ShieldError(
                "KODI_REMOTE_ROOT must be an absolute path inside Shield shared storage"
            )
        mount = os.environ.get("KODI_MOUNT")
        return cls(
            host=host,
            adb_port=port(os.environ.get("SHIELD_ADB_PORT", "5555")),
            adb_path=os.environ.get("ADB_PATH", "adb"),
            kodi_port=port(os.environ.get("KODI_PORT", "8080")),
            username=os.environ.get("KODI_USERNAME", ""),
            password=os.environ.get("KODI_PASSWORD", ""),
            manager_port=port(os.environ.get("KODI_MANAGER_PORT", "8765")),
            manager_token=os.environ.get("KODI_MANAGER_TOKEN", ""),
            mount=Path(mount).expanduser().resolve() if mount else None,
            state=Path(os.environ.get("NVIDIA_MCP_STATE_DIR", state_path())).expanduser().resolve(),
            allow_writes=os.environ.get("NVIDIA_MCP_ALLOW_WRITES", "0") == "1",
            allow_plugin_browse=os.environ.get("NVIDIA_MCP_ALLOW_PLUGIN_BROWSE", "0") == "1",
            remote_root=root.rstrip("/"),
            aapt2_path=os.environ.get("AAPT2_PATH", "aapt2"),
            apksigner_path=os.environ.get("APKSIGNER_PATH", "apksigner"),
            java_path=os.environ.get("JAVA_PATH", "java"),
        )

    @property
    def serial(self):
        host = f"[{self.host}]" if ":" in self.host else self.host
        return f"{host}:{self.adb_port}"

    def url(self, manager=False):
        host = f"[{self.host}]" if ":" in self.host else self.host
        return f"http://{host}:{self.manager_port if manager else self.kodi_port}"
