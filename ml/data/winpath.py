"""Windows MAX_PATH (260) workaround for deep dataset trees.

PlantDoc ships auto-generated member names over 200 chars; from a nested base directory the
full target easily exceeds the Win32 260-char limit, and Python's io layer then fails with
FileNotFoundError at open-time (zipfile is not MAX_PATH-aware). The extended-length ``\\\\?\\``
prefix lifts the limit for local absolute paths. `windows_safe()` is a no-op everywhere else:
identity on POSIX, identity on Windows for paths within a safe margin.
"""

import os
from pathlib import Path

MAX_SAFE_LENGTH = 240  # deliberate headroom under the 260-char Win32 limit

_EXTENDED_PREFIX = "\\\\?\\"


def windows_safe(path: Path | str) -> str:
    """Extended-length path string for Windows when needed; plain str(path) otherwise.

    Callers pass ordinary paths only (never an already-prefixed one): the prefix is added here.
    """
    text = str(path)
    if os.name != "nt" or len(text) <= MAX_SAFE_LENGTH:
        return text
    absolute = str(Path(text).absolute()).replace("/", "\\").lstrip("\\")
    return _EXTENDED_PREFIX + absolute
