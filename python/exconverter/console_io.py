"""Interactive console I/O (port of Swift Utils/ConsoleIO.swift helpers used
by the CLI entry point).
"""

from __future__ import annotations

import os
from collections.abc import Callable


def safe_read_line(input_fn: Callable[[], str]) -> str | None:
    """Read a line like Swift's readLine(): None on EOF."""
    try:
        return input_fn()
    except EOFError:
        return None


def get_excel_file(
    input_fn: Callable[[], str] = input,
) -> str | None:
    """Prompt for a dragged/dropped Excel path or search the current dir."""
    print(
        "Drag and drop an Excel file here, or press Enter to search current "
        "directory:"
    )
    line = safe_read_line(input_fn)
    if line is None:
        return None  # Swift readLine() == nil -> no input, exit silently
    raw = line.strip()
    path_str = raw.replace("'", "").replace('"', "").replace("\\ ", " ")
    path_str = os.path.abspath(os.path.expanduser(path_str))

    if path_str.lower().endswith(".xlsx") and os.path.isfile(path_str):
        return path_str

    # Fall back to the first .xlsx in the current directory.
    try:
        for entry in sorted(os.listdir(os.getcwd())):
            if entry.lower().endswith(".xlsx") and os.path.isfile(entry):
                return os.path.abspath(entry)
    except OSError:
        pass

    from . import console

    console.error("No Excel file found.")
    return None


def is_ipo_template(excel_file: str) -> bool:
    """Auto-detect IPO templates by filename (port of main.swift)."""
    filename = os.path.basename(excel_file).lower()
    return "ipo项目模板" in filename
