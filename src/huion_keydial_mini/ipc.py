"""IPC v2 helpers: runtime paths + framing constants.

Wire format: one JSON object per newline-terminated line, both directions.
A connection may carry many requests. Responses always include {"v": 2}.
"""
import os
from pathlib import Path

PROTOCOL_VERSION = 2
MAX_LINE = 65536


def runtime_dir() -> Path:
    base = os.environ.get("XDG_RUNTIME_DIR")
    if base:
        d = Path(base) / "huion-keydial-mini"
    else:
        d = Path.home() / ".local" / "share" / "huion-keydial-mini"
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(str(d), 0o700)
    return d


def socket_path() -> str:
    return str(runtime_dir() / "control.sock")
