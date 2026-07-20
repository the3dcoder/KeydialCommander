"""Huion Keydial Mini driver package."""
try:
    from importlib.metadata import version, PackageNotFoundError
except ImportError:  # Python < 3.8 fallback path
    from importlib_metadata import version, PackageNotFoundError  # type: ignore

try:
    __version__ = version("huion-keydial-mini-driver")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

__author__ = "Earl"
__email__ = "earl@bigbwain.com"
