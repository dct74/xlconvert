"""Shared helpers for folder-producing processors
(port of Swift Protocols/FolderProcessor.swift default methods).

Swift uses a protocol with default implementations; Python expresses the two
reusable pieces as plain functions taking the excel file path.
"""

from __future__ import annotations

from . import file_system
from .path_utils import assumed_base_folder


def create_base_folder(excel_file: str, created_count: list[int]) -> str | None:
    """Create the top-level (Excel-file-named) folder (port of createBaseFolder
    without a sheet subfolder). Returns its path, or None on failure.
    """
    top_folder = assumed_base_folder(excel_file)
    if not file_system.create_folder_safely(at=top_folder, count=created_count):
        return None
    return top_folder
