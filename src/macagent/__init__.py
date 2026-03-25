"""macagent package."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("macagent")
except PackageNotFoundError:  # pragma: no cover - local editable/src path before install
    __version__ = "0.0.0"

__all__ = ["__version__"]
