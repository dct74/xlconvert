"""Data models (port of Swift Models/Types.swift)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum

from . import config


@dataclass
class ExcelContext:
    """The resolved grid for one worksheet.

    Mirrors Swift ExcelContext:
      - grid[0] is the header row (Excel row `startRow - 1`)
      - grid[1...] holds data rows beginning at Excel row `startRow`
      - every row is padded to `maxCol` cells (cap 26 columns A..Z)
    """

    file_path: str
    sheet_name: str
    start_row: int
    headers: dict[str, list[int]]
    grid: list[list[str]] = field(default_factory=list)


# --------------------------------------------------------------------------
# Rename operations / history
# --------------------------------------------------------------------------
class OperationStatus(Enum):
    success = "success"
    failed = "failed"
    skipped = "skipped"
    pending = "pending"


@dataclass
class RenameOperation:
    old_relative_path: str
    new_relative_path: str
    relative_backup_path: str
    status: OperationStatus
    error_message: str | None = None
    is_restored: bool = False

    def to_dict(self) -> dict:
        return {
            "oldRelativePath": self.old_relative_path,
            "newRelativePath": self.new_relative_path,
            "relativeBackupPath": self.relative_backup_path,
            "status": self.status.value,
            "errorMessage": self.error_message,
            "isRestored": self.is_restored,
        }

    @classmethod
    def from_dict(cls, d: dict) -> RenameOperation:
        return cls(
            old_relative_path=d.get("oldRelativePath", ""),
            new_relative_path=d.get("newRelativePath", ""),
            relative_backup_path=d.get("relativeBackupPath", ""),
            status=OperationStatus(d.get("status", "pending")),
            error_message=d.get("errorMessage"),
            is_restored=bool(d.get("isRestored", False)),
        )


@dataclass
class RenameBatch:
    """A group of rename operations sharing one backup directory."""

    version: int
    operations: list[RenameOperation]
    backup_dir_name: str

    @staticmethod
    def new(operations: list[RenameOperation], backup_dir_name: str) -> RenameBatch:
        return RenameBatch(
            version=config.history_version,
            operations=operations,
            backup_dir_name=backup_dir_name,
        )

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "operations": [op.to_dict() for op in self.operations],
            "backupDirName": self.backup_dir_name,
        }

    @classmethod
    def from_dict(cls, d: dict) -> RenameBatch:
        return cls(
            version=d.get("version", config.history_version),
            operations=[RenameOperation.from_dict(o) for o in d.get("operations", [])],
            backup_dir_name=d.get("backupDirName", ""),
        )


# --------------------------------------------------------------------------
# File-name parsing
# --------------------------------------------------------------------------
class FileNamePartType(Enum):
    digits_only = "digits_only"
    letters_only = "letters_only"
    mixed = "mixed"
    empty = "empty"


def classify_filename(filename: str) -> FileNamePartType:
    """Classify a filename by its stem (port of Swift getFileNamePartType)."""
    stem = os.path.splitext(filename)[0]
    if not stem:
        return FileNamePartType.empty
    is_digits = all(c.isascii() and c.isdigit() for c in stem)
    if is_digits:
        return FileNamePartType.digits_only
    is_letters = all(c.isascii() and c.isalpha() for c in stem)
    if is_letters:
        return FileNamePartType.letters_only
    return FileNamePartType.mixed


@dataclass
class ParseResult:
    """Parsed folder name of form "<row>-<basename>" (port of ParseResult)."""

    sheet_name: str | None
    row_number: int | None
    base_folder_name: str | None
    is_valid: bool

    @staticmethod
    def from_folder_path(folder_path: str) -> ParseResult:
        folder_name = os.path.basename(folder_path.rstrip(os.sep))
        m = config.Regex.folder_name_pattern.fullmatch(folder_name)
        if m:
            row = int(m.group(1))
            return ParseResult(
                sheet_name=os.path.basename(os.path.dirname(folder_path.rstrip(os.sep))),
                row_number=row,
                base_folder_name=m.group(2),
                is_valid=True,
            )
        return ParseResult(sheet_name=None, row_number=None, base_folder_name=None, is_valid=False)
