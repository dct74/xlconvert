"""WPSheet -> hierarchical folders processor
(port of Swift Processors/WPSheetProcessor.swift).

Fixed A..E columns. Recognizes "第X部分" section headers and "X、" numbered
items, then builds up to a 6-level tree:
    file/ sheet/ 第一部分/ 一、.../ A值(4) / B值 C值(5) / D值 E值(6)
"""

from __future__ import annotations

import os
from collections.abc import Callable

from .. import config, console, excel_parser, file_system, sequence_prefix, string_transform
from ..excel_parser import open_workbook


def _chinese_section(cell: str) -> bool:
    return config.Regex.chinese_section.match(cell) is not None


def _chinese_number(cell: str) -> bool:
    return config.Regex.chinese_number.match(cell) is not None


def _trim_empty(s: str) -> bool:
    return not s.strip()


class WPSheetProcessor:
    """Create a folder tree from every worksheet of an Excel file."""

    def __init__(
        self,
        excel_file: str,
        input_fn: Callable[[], str] = input,
    ) -> None:
        self.excel_file = excel_file
        self.input_fn = input_fn

    def process(self) -> None:
        wb = open_workbook(self.excel_file)
        try:
            sheet_names = excel_parser.sheet_names(wb)
            if not sheet_names:
                console.error("No worksheets found in Excel file.")
                return

            excel_filename = string_transform.sanitize(
                os.path.splitext(os.path.basename(self.excel_file))[0]
            )
            base_dir = os.path.dirname(os.path.abspath(self.excel_file))
            top_folder = os.path.join(base_dir, excel_filename)
            total: list[int] = [0]

            if not file_system.create_folder_safely(at=top_folder, count=total):
                raise ValueError("Failed to create top folder.")

            for sheet_name in sheet_names:
                try:
                    ctx = excel_parser.read_excel_to_grid(
                        path=self.excel_file,
                        sheet_name=sheet_name,
                        start_row=config.Limits.default_excel_start_row,
                        workbook=wb,
                    )
                    grid = ctx.grid
                    if len(grid) <= 1:
                        console.warning(
                            f"Worksheet '{sheet_name}' is empty, skipping"
                        )
                        continue

                    clean = string_transform.sanitize(sheet_name)
                    sheet_folder = os.path.join(top_folder, clean)
                    if not file_system.create_folder_safely(
                        at=sheet_folder, count=total
                    ):
                        continue

                    total[0] += self._process_sheet_hierarchy(sheet_folder, grid)
                except Exception as exc:
                    console.warning(
                        f"Error processing sheet '{sheet_name}': {exc}"
                    )
                    continue
        finally:
            wb.close()

        print()
        console.success(f"Folder creation completed: {total[0]} folders created")
        seq = sequence_prefix.add_sequence_prefix(top_folder)
        if seq:
            console.info(f"Added numeric prefixes to {seq} ordinal directories.")

    def _process_sheet_hierarchy(
        self, sheet_folder: str, grid: list[list[str]]
    ) -> int:
        """Build the per-sheet tree; returns number of folders created."""
        count: list[int] = [0]
        current_section: str | None = None
        current_number: str | None = None
        current_a_value: str | None = None
        last_created_a_value: str | None = None
        current_b_value: str | None = None
        processing_number = False

        for r in range(1, len(grid)):
            row = grid[r]
            excel_row_num = r + 1

            row_has_section = False
            row_has_number = False
            section_value = ""
            number_value = ""

            for cell in row:
                c = cell.strip()
                if not c:
                    continue
                if not row_has_section and _chinese_section(c):
                    row_has_section = True
                    section_value = c
                    break
                if not row_has_number and _chinese_number(c):
                    row_has_number = True
                    number_value = c
                    break

            # Section row.
            if row_has_section:
                sec_name = string_transform.sanitize(section_value)
                if not sec_name:
                    continue
                current_section = sec_name
                current_number = None
                current_a_value = None
                last_created_a_value = None
                current_b_value = None
                processing_number = False

                section_folder = os.path.join(sheet_folder, sec_name)
                file_system.create_folder_safely(at=section_folder, count=count)
                continue

            # Numbered item row.
            if row_has_number:
                if current_section is None:
                    console.warning(
                        f"Number '{number_value}' found without preceding "
                        f"section at row {excel_row_num}, skipping"
                    )
                    continue
                num_name = string_transform.sanitize(number_value)
                if not num_name:
                    continue
                current_number = num_name
                current_a_value = None
                last_created_a_value = None
                current_b_value = None
                processing_number = True

                number_folder = os.path.join(
                    sheet_folder, current_section, num_name
                )
                file_system.create_folder_safely(at=number_folder, count=count)
                continue

            # Data row.
            if not processing_number:
                continue
            if current_section is None or current_number is None:
                continue
            if len(row) < 3:
                continue
            if all(_trim_empty(row[i]) for i in range(min(5, len(row)))):
                continue

            a_val = row[0] if len(row) > 0 else ""
            b_val = row[1] if len(row) > 1 else ""
            c_val = row[2] if len(row) > 2 else ""
            d_val = row[3] if len(row) > 3 else ""
            e_val = row[4] if len(row) > 4 else ""

            a_has_content = bool(a_val.strip())
            b_has_content = bool(b_val.strip())

            if a_has_content:
                current_a_value = a_val.strip()
            if b_has_content:
                current_b_value = b_val.strip()

            # Determine A logic.
            use_a_logic: bool
            effective_a_val: str | None
            if current_a_value is not None and current_a_value:
                use_a_logic = True
                effective_a_val = current_a_value
            elif a_has_content:
                use_a_logic = True
                effective_a_val = a_val.strip()
            else:
                use_a_logic = False
                effective_a_val = None

            level4_name = ""
            level5_name = ""
            level6_name = ""

            if use_a_logic and effective_a_val is not None:
                a_str = string_transform.sanitize(effective_a_val)
                if not a_str:
                    continue
                level4_name = a_str

                effective_b: str | None
                if b_has_content:
                    effective_b = b_val.strip()
                elif current_b_value is not None and current_b_value:
                    effective_b = current_b_value
                else:
                    effective_b = None

                b_str = (
                    string_transform.sanitize(effective_b)
                    if effective_b is not None
                    else ""
                )
                c_trim = c_val.strip()
                c_str = (
                    string_transform.sanitize(c_trim) if c_trim else ""
                )
                level5_name = f"{b_str} {c_str}".strip()

                d_trim = d_val.strip()
                e_trim = e_val.strip()
                d_str = string_transform.sanitize(d_trim) if d_trim else ""
                e_str = string_transform.sanitize(e_trim) if e_trim else ""
                level6_name = f"{d_str} {e_str}".strip()
            else:
                # No-A logic.
                effective_b: str | None
                if b_has_content:
                    effective_b = b_val.strip()
                elif current_b_value is not None and current_b_value:
                    effective_b = current_b_value
                else:
                    effective_b = None
                if effective_b is None:
                    console.warning(
                        f"Row {excel_row_num} has empty B column and no previous "
                        "B value, skipping"
                    )
                    continue

                b_str = string_transform.sanitize(effective_b)
                c_trim = c_val.strip()
                c_str = string_transform.sanitize(c_trim) if c_trim else ""
                level4_name = b_str if not c_str else f"{b_str} {c_str}".strip()

                d_trim = d_val.strip()
                e_trim = e_val.strip()
                d_str = string_transform.sanitize(d_trim) if d_trim else ""
                e_str = string_transform.sanitize(e_trim) if e_trim else ""
                level5_name = f"{d_str} {e_str}".strip()
                level6_name = ""

            # Dedup level-4 folder.
            if use_a_logic and effective_a_val is not None:
                skip_level4 = effective_a_val == last_created_a_value
            else:
                skip_level4 = False

            if not level4_name:
                console.warning(
                    f"Row {excel_row_num} has empty level-4 name, skipping"
                )
                continue

            number_folder = os.path.join(
                sheet_folder, current_section, current_number
            )
            level4_folder = os.path.join(number_folder, level4_name)

            if not skip_level4:
                file_system.create_folder_safely(at=level4_folder, count=count)
                if use_a_logic and effective_a_val is not None:
                    last_created_a_value = effective_a_val

            if level5_name:
                level5_folder = os.path.join(level4_folder, level5_name)
                file_system.create_folder_safely(at=level5_folder, count=count)
                if use_a_logic and level6_name:
                    level6_folder = os.path.join(level5_folder, level6_name)
                    file_system.create_folder_safely(at=level6_folder, count=count)
            elif use_a_logic and level6_name:
                console.warning(
                    f"Row {excel_row_num} has level-6 name but no level-5 name, "
                    "skipping level-6"
                )

        return count[0]
