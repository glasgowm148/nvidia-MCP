"""Android TV / Fire OS Kodi MCP server and library (legacy Shield API retained)."""

__version__ = "0.4.10"

from .config import Config, ShieldError  # noqa: E402
from .device import Shield  # noqa: E402

AndroidTV = Shield

__all__ = ["AndroidTV", "Config", "Shield", "ShieldError", "__version__"]
