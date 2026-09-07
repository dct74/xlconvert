"""URL/path helpers (port of Extensions/URL+Helpers.swift)."""

from __future__ import annotations

import os
from pathlib import Path

from . import string_transform


def relative_path(from_base: str | Path, to_file: str | Path) -> str:
    """Compute a relative path from base to dest using symlink-resolved
    absolute paths, mirroring Swift's URL.relativePath.
    """
    dest_abs = os.path.realpath(os.path.abspath(str(to_file)))
    base_abs = os.path.realpath(os.path.abspath(str(from_base)))

    dest_parts = dest_abs.split(os.sep)
    base_parts = base_abs.split(os.sep)

    i = 0
    while (
        i < len(dest_parts)
        and i < len(base_parts)
        and dest_parts[i] == base_parts[i]
    ):
        i += 1

    rel = [".."] * (len(base_parts) - i)
    rel.extend(dest_parts[i:])
    return "/".join(rel)


def assumed_base_folder(excel_path: str | Path) -> str:
    """Derive the sibling base-folder name from an Excel file's stem
    (sanitized), matching Swift's assumedBaseFolder.
    """
    p = Path(str(excel_path))
    stem = sanitized_stem(p)
    return os.path.join(os.path.dirname(str(p)), stem)


def sanitized_stem(p: Path) -> str:
    return string_transform.sanitize(p.stem)
