"""Configuration & constants (port of Swift Core/Config.swift).

Note on regex anchoring semantics:
  Swift regex literals are matched with explicit methods (.wholeMatch vs
  .prefixMatch). Patterns here are stored raw (compiled on demand) and the
  call sites must apply the correct anchoring — mirror the Swift source.
"""

from __future__ import annotations

import re

# Max single-column limit — Excel columns A..Z only (no AA+), matching Swift.
_MAX_EXCEL_COLUMNS = 26


class Limits:
    header_row = 1
    min_data_start_row = header_row + 1
    default_excel_start_row = min_data_start_row
    max_excel_columns = _MAX_EXCEL_COLUMNS
    max_excel_rows = 10000
    max_folders_to_create = 5000
    max_merge_cell_area = 10000
    max_path_component_length = 255
    year_min = 1900
    year_max = 2100
    large_file_warning_threshold_mb = 50

    @staticmethod
    def large_file_warning_threshold_bytes() -> int:
        return Limits.large_file_warning_threshold_mb * 1024 * 1024

    max_unique_path_attempts = 9999
    max_sort_attempts = 3


class Paths:
    max_length = 1024
    backup_prefix = "_backup_"
    undo_history_filename = ".rename_history.json"


class Display:
    panel_line_width = 50
    max_title_display_chars = 20


class Regex:
    # NOTE: these mirror Swift's regex literal content exactly. Anchoring is
    # applied at the call site to reproduce .wholeMatch / .prefixMatch behavior.
    invalid_chars = re.compile(r"""[<>:"/\\|?*]""")
    chinese_section = re.compile(r"^第[一二三四五六七八九十]+部分")
    chinese_number = re.compile(r"^[一二三四五六七八九十]+、")
    date_time_suffix = re.compile(r"\s+(\d{2}:\d{2}:\d{2}|\d{6})$")
    eight_digit = re.compile(r"^\d{8}$")
    single_letter = re.compile(r"^([a-zA-Z])$")
    row_col = re.compile(r"^(\d+)-([a-zA-Z])$")
    folder_name_pattern = re.compile(r"^(\d+)-(.+)$")
    letters_only = re.compile(r"^[a-zA-Z]+$")


class InputKeys:
    yes = "y"
    no = "n"
    quit = "q"
    undo = "u"


class Defaults:
    sheet_name = "Sheet1"
    default_column_prefix = "Column_"
    temp_restore_prefix = ".temp_restore_"


ds_store = ".DS_Store"
history_version = 1

reserved_windows_names: frozenset[str] = frozenset({
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
})
