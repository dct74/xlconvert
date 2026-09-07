"""File-system operations (port of Swift Services/FileSystem.swift).

Phase 2 covers directory creation helpers. Rename/backup helpers
(collect_files, init_backup_directory, backup_folder_structure, unique paths)
arrive with the rename processor in Phase 3.
"""

from __future__ import annotations

import errno
import os
import uuid
from pathlib import Path

from . import config, console


def get_relative_path(from_base: str | Path, to_file: str | Path) -> str:
    from .path_utils import relative_path

    return relative_path(from_base, to_file)


def validate_path_length(url: str | Path) -> bool:
    """Return True if the path byte-length is within the safe limit."""
    p = os.fspath(url)
    path_length = len(p.encode("utf-8"))
    if path_length <= config.Paths.max_length:
        return True
    console.error(
        f"Path length ({path_length} bytes) exceeds safe limit "
        f"({config.Paths.max_length}): {p}"
    )
    return False


def _dir_exists(url: str) -> bool:
    return os.path.isdir(url)


def safe_create_directory(at: str | Path) -> bool:
    """Create a directory (with parents) if possible (port of safeCreateDirectory).

    Returns True when the directory exists after the call (newly created or
    pre-existing). Returns False when a file blocks the path or on error.
    """
    url = os.fspath(at)
    if not validate_path_length(url):
        return False
    try:
        os.makedirs(url, exist_ok=True)
        if _dir_exists(url):
            return True
        console.error(
            f"Failed to create directory {url}: A file already exists at this path."
        )
        return False
    except OSError as exc:
        if exc.errno == errno.EEXIST:
            console.error(
                f"Failed to create directory {url}: A file already exists at this path."
            )
        else:
            console.error(f"Failed to create directory {url}: {exc}")
        return False


def create_folder_safely(at: str | Path, count: list[int]) -> bool:
    """Create a folder honoring the global folder-count cap (port of Swift).

    `count` is a single-element list mutated in place (Python has no inout
    params); it holds the running number of folders created so far.
    """
    if count[0] >= config.Limits.max_folders_to_create:
        console.error(
            f"Reached safe limit of {config.Limits.max_folders_to_create} folders. "
            "Aborting creation."
        )
        return False
    url = os.fspath(at)
    if not validate_path_length(url):
        return False
    if safe_create_directory(url):
        count[0] += 1
        return True
    return False


def backup_dir_for(excel_file: str) -> str:
    """Derive the backup directory name (sanitized stem + _backup_)."""
    from . import string_transform

    stem = os.path.splitext(os.path.basename(excel_file))[0]
    sanitized = string_transform.sanitize(stem)
    return os.path.join(
        os.path.dirname(os.path.abspath(excel_file)),
        f"{sanitized}{config.Paths.backup_prefix}",
    )


def init_backup_directory(excel_file: str, state) -> str:
    """Create (or clean a residual empty) backup dir; set on state.
    (port of Swift FileSystem.initBackupDirectory). Returns the backup path.
    """
    backup_url = backup_dir_for(excel_file)
    dir_name = os.path.basename(backup_url)

    if os.path.isdir(backup_url):
        contents = os.listdir(backup_url)
        if not contents:
            os.rmdir(backup_url)
            console.info("Cleaned up empty residual backup directory.")
        else:
            from .errors import BackupError

            raise BackupError(
                "Backup directory already exists and is not empty: "
                f"{dir_name}. Please remove it manually."
            )

    try:
        os.makedirs(backup_url, exist_ok=True)
        state.backup_directory = backup_url
        console.success(f"Backup directory created: {dir_name}")
        return backup_url
    except OSError as exc:
        from .errors import BackupError

        raise BackupError(f"Cannot create backup directory: {exc}") from exc


def backup_folder_structure(
    source_folders: list[str], to: str, base_dir: str
) -> bool:
    """Hard-link each file under the source folders into the backup dir,
    mirroring their relative structure (port of Swift backupFolderStructure).
    Returns True on full success.
    """
    from . import console

    for folder in source_folders:
        rel_path = get_relative_path(base_dir, folder)
        dest_folder = os.path.join(to, rel_path)
        if not safe_create_directory(at=dest_folder):
            return False
        for root, dirs, files in os.walk(folder):
            for fn in files:
                if fn == config.ds_store:
                    continue
                src = os.path.join(root, fn)
                # mirror relative path from the source folder root
                inner_rel = get_relative_path(folder, src)
                dest_file = os.path.join(dest_folder, inner_rel)
                try:
                    os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                    os.link(src, dest_file)
                except OSError as exc:
                    console.error(
                        f"CRITICAL: Failed to hard-link backup {fn}: {exc}"
                    )
                    return False
    return True


def ensure_same_volume(source_dir: str, backup_dir: str) -> None:
    """Verify source and backup dirs are on the same device (port of Swift
    ensureSameVolume via lstat st_dev).
    """
    from .errors import AbortError, FileSystemError

    def _dev(path: str) -> int:
        try:
            return os.lstat(path).st_dev
        except OSError as exc:
            raise FileSystemError(exc) from exc

    src_dev = _dev(os.path.abspath(source_dir))
    bak_dev = _dev(os.path.abspath(backup_dir))
    if src_dev != bak_dev:
        raise AbortError(
            "CRITICAL: Source directory and backup directory are on different "
            "volumes.\nHard linking is not supported across volumes, and copying "
            "large files may fail or cause data loss.\nPlease ensure the Excel "
            "file and the target folders are on the same drive."
        )


def get_unique_file_path(original: str) -> str:
    """Return an unused path by appending _N (or a UUID) (port of Swift)."""
    base, ext = os.path.splitext(original)
    if not os.path.exists(original):
        return original
    for n in range(1, config.Limits.max_unique_path_attempts + 1):
        candidate = f"{base}_{n}{ext}" if ext else f"{base}_{n}"
        if not os.path.exists(candidate):
            return candidate
    candidate = f"{base}_{uuid.uuid4()}{ext}" if ext else f"{base}_{uuid.uuid4()}"
    return candidate
