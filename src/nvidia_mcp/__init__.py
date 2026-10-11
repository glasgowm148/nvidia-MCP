"""NVIDIA Shield TV MCP server, and a small library API for the same device code."""

__version__ = "0.4.7"

from .config import Config, ShieldError  # noqa: E402
from .device import Shield  # noqa: E402

__all__ = ["Config", "Shield", "ShieldError", "__version__"]
