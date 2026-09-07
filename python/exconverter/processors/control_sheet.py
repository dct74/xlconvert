"""ControlSheet -> folders processor
(port of Swift Processors/ControlSheetProcessor.swift).

Creates a folder per sheet name, plus optional subfolders from user-specified
column rules. Column letter `B` = one folder per non-empty cell in that column
(`行号-值`); row-col `3-B` = one folder from that single cell value.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass

from .. import config, console, excel_parser, file_system, sequence_prefix, string_transform
from ..console_io import safe_read_line
from ..excel_columns import index as col_index
from ..excel_parser import open_workbook, read_excel_to_grid
from ..folder_processor import create_base_folder
from ..models import ExcelContext


@dataclass
class FolderRule:
    kind: str  # "column_all" | "single_cell"
    col_letter: str
    column: str
    display: str
    row: int | None = None


@dataclass
class SheetControlConfig:
    rules: list[FolderRule]
    start_row: int


class ControlSheetProcessor:
    def __init__(
        self,
        excel_file: str,
        input_fn: Callable[[], str] = input,
    ) -> None:
        self.excel_file = excel_file
        self.input_fn = input_fn

    # --- Rule parsing -----------------------------------------------------
    def _parse_control_rule_input(
        self, raw: str, ctx: ExcelContext
    ) -> list[FolderRule]:
        rules: list[FolderRule] = []
        grid_cols = len(ctx.grid[0]) if ctx.grid else 0
        for part in raw.split(","):
            p = part.strip()
            m_single = config.Regex.single_letter.fullmatch(p)
            if m_single:
                letter_ = m_single.group(1)
                col_idx = col_index(letter_)
                if col_idx is None:
                    continue
                if col_idx >= grid_cols:
                    console.warning(
                        f"Column {letter_} exceeds actual sheet width "
                        f"({grid_cols} columns)."
                    )
                    continue
                rules.append(
                    FolderRule(
                        kind="column_all",
                        col_letter=letter_.upper(),
                        column=ctx.grid[0][col_idx],
                        display=(
                            f"Column {letter_.upper()} (all non-empty)"
                        ),
                        row=None,
                    )
                )
                continue
            m_rc = config.Regex.row_col.fullmatch(p)
            if m_rc:
                row = int(m_rc.group(1))
                letter_ = m_rc.group(2)
                col_idx = col_index(letter_)
                if col_idx is None:
                    continue
                if col_idx >= grid_cols:
                    console.warning(
                        f"Column {letter_} exceeds actual sheet width "
                        f"({grid_cols} columns)."
                    )
                    continue
                lo = config.Limits.default_excel_start_row
                hi = len(ctx.grid) + config.Limits.default_excel_start_row - 2
                if not (lo <= row <= hi):
                    console.warning(
                        f"{p} (Row number out of range, valid: {lo}-{hi})"
                    )
                    continue
                rules.append(
                    FolderRule(
                        kind="single_cell",
                        col_letter=letter_.upper(),
                        column=ctx.grid[0][col_idx],
                        display=(
                            f"Row {row}, Column {letter_.upper()}"
                        ),
                        row=row,
                    )
                )
                continue
            if p:
                console.warning(
                    f"{p} (Format error, should be: column letter or row-col, "
                    "e.g.: b or 3-b)"
                )
        return rules

    # --- Collect sheet info & rules --------------------------------------
    def _collect_control_rules(self) -> list[tuple] | None:
        wb = open_workbook(self.excel_file)
        try:
            sheet_names = excel_parser.sheet_names(wb)
            all_sheets: list[tuple] = []

            console.info(
                "\nThe script will create hierarchical folders with structure: "
                "filename>Sheet name"
            )
            console.info(
                "\nWhether to create subfolders under Sheet folder and rules:"
            )
            console.info(
                "\n- Column letter: Create folders using all non-empty cells in "
                "this column of the Sheet, e.g. b"
            )
            console.info(
                "- Row number-Column letter: Create folders using specified "
                "row-column cell in the Sheet, e.g. 3-b"
            )
            console.info(
                "- Press Enter directly at rule prompt: No subfolders under "
                "Sheet folder"
            )
            console.info("")
            console.warning("Note:")
            console.info("\n- Headers must be at the top of the table")
            console.info("- Line breaks in cells must be natural line breaks")
            console.info(
                "- Merged cells in the table need to be replaced with cross-row "
                "center alignment"
            )
            console.info("- No extra spaces or invisible characters in cells")
            console.info(
                "- No special characters not supported by file/folder naming "
                "in cells"
            )

            start_row = config.Limits.default_excel_start_row

            for sheet_name in sheet_names:
                ctx: ExcelContext | None = None
                try:
                    ctx = read_excel_to_grid(
                        path=self.excel_file,
                        sheet_name=sheet_name,
                        start_row=start_row,
                        workbook=wb,
                    )
                except Exception as exc:
                    print()
                    console.warning(
                        f"Sheet '{sheet_name}': {exc} Folder will be created "
                        "without subfolders."
                    )
                    all_sheets.append((sheet_name, None, None))
                    continue

                if ctx is None or len(ctx.grid) <= 1:
                    all_sheets.append((sheet_name, None, ctx))
                    print()
                    console.info(
                        f"Sheet '{sheet_name}' has no data rows. Folder will be "
                        "created without subfolders."
                    )
                    continue

                has_added_rules = False
                while not has_added_rules:
                    print(
                        f"\nSelect rule for Sheet '{sheet_name}' (press Enter to "
                        "skip subfolders): ",
                        end="",
                    )
                    line = safe_read_line(self.input_fn)
                    if line is None:
                        break
                    raw_in = line.strip()

                    if not raw_in:
                        break

                    rules = self._parse_control_rule_input(raw_in, ctx)
                    invalid = []
                    for part in raw_in.split(","):
                        p = part.strip()
                        if config.Regex.single_letter.fullmatch(p):
                            continue
                        if config.Regex.row_col.fullmatch(p):
                            continue
                        if p:
                            invalid.append(p)
                    if invalid:
                        console.warning("Invalid rules:")
                        for inv in invalid:
                            console.warning(f" - {inv} (Format error)")
                        continue

                    if rules:
                        all_sheets.append(
                            (
                                sheet_name,
                                SheetControlConfig(rules=rules, start_row=start_row),
                                ctx,
                            )
                        )
                        has_added_rules = True
                        summary = ", ".join(rule.display for rule in rules)
                        console.success(
                            f"Added rules for Sheet '{sheet_name}': {summary}"
                        )
                    else:
                        console.warning(
                            "No valid rules parsed. Please try again or press "
                            "Enter to skip."
                        )

                if not has_added_rules:
                    all_sheets.append((sheet_name, None, ctx))
                    console.info(
                        f"Sheet '{sheet_name}' will be created without subfolders."
                    )
            return all_sheets or None
        finally:
            wb.close()

    # --- Folder components ------------------------------------------------
    def _resolve_folder_components(
        self,
        data_index: int,  # grid index r (1-based data row)
        row: list[str],
        rules: list[FolderRule],
        padding_width: int,
    ) -> list[str] | None:
        components: list[str] = []
        excel_row_num = data_index + 1
        for rule in rules:
            col_idx = col_index(rule.col_letter)
            if col_idx is None or col_idx >= len(row):
                return None
            if rule.kind == "single_cell":
                if rule.row is not None and excel_row_num != rule.row:
                    return None
            cell_value = row[col_idx] if col_idx < len(row) else ""
            trimmed = cell_value.strip()
            if not trimmed:
                return None
            clean_value = string_transform.sanitize(trimmed)
            if not clean_value:
                return None
            if rule.kind == "column_all":
                folder_name = f"{excel_row_num:0{padding_width}d}-{clean_value}"
            else:
                folder_name = clean_value
            components.append(folder_name)
        return components or None

    # --- Process sheet ----------------------------------------------------
    def _process_sheet(
        self,
        name: str,
        config_: SheetControlConfig | None,
        ctx: ExcelContext | None,
        top_folder: str,
        total_count: list[int],
    ) -> None:
        sheet_folder = os.path.join(top_folder, string_transform.sanitize(name))
        if not file_system.create_folder_safely(at=sheet_folder, count=total_count):
            return
        if (
            config_ is None
            or not config_.rules
            or ctx is None
            or len(ctx.grid) <= 1
        ):
            return

        padding_width = len(str(len(ctx.grid)))
        for r in range(1, len(ctx.grid)):
            components = self._resolve_folder_components(
                data_index=r,
                row=ctx.grid[r],
                rules=config_.rules,
                padding_width=padding_width,
            )
            if not components:
                continue
            build_path = sheet_folder
            for comp in components:
                build_path = os.path.join(build_path, comp)
                file_system.safe_create_directory(at=build_path)
            total_count[0] += len(components)

    # --- Main flow --------------------------------------------------------
    def process(self) -> None:
        all_sheets = self._collect_control_rules()
        if not all_sheets:
            return
        total: list[int] = [0]
        top_folder = create_base_folder(self.excel_file, total)
        if top_folder is None:
            raise ValueError("Failed to create top-level folder.")
        for sheet_name, cfg, ctx in all_sheets:
            self._process_sheet(sheet_name, cfg, ctx, top_folder, total)
        print()
        console.success(f"Created {total[0]} folders.")
        seq = sequence_prefix.add_sequence_prefix(top_folder)
        if seq:
            console.info(f"Added numeric prefixes to {seq} ordinal directories.")
