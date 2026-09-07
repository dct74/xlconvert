"""File rename + undo processor (port of Processors/FileRenameProcessor.swift).

Batch-renames files according to cell values in the Excel workbook, backing up
the original folder structure with hard links, and records operations so they
can be undone. Files live in the Excel sibling folder (or under the
Excel-stem-named folder); their filenames encode the target row & columns.
"""

from __future__ import annotations

import os
import shutil
import uuid
from collections.abc import Callable

from .. import config, console, excel_parser, file_system, string_transform
from ..console_io import safe_read_line
from ..excel_columns import index as col_index
from ..excel_columns import letter as col_letter
from ..excel_parser import open_workbook, read_excel_to_grid
from ..models import (
    ExcelContext,
    FileNamePartType,
    OperationStatus,
    ParseResult,
    RenameBatch,
    RenameOperation,
    classify_filename,
)
from ..state import RenameStateManager


class _RenameResult:
    __slots__ = ("kind", "op", "message")

    def __init__(self, kind: str, op=None, message: str = ""):
        self.kind = kind  # "success" | "skipped" | "failure"
        self.op = op
        self.message = message


class FileRenameProcessor:
    def __init__(
        self,
        excel_file: str,
        coordinator: RenameStateManager | None = None,
        input_fn: Callable[[], str] = input,
    ) -> None:
        self.excel_file = excel_file
        self.coordinator = coordinator or RenameStateManager(excel_file)
        self.input_fn = input_fn

    # ------------------------------------------------------------------ #
    # Public
    # ------------------------------------------------------------------ #
    def process(self) -> None:
        self.coordinator.clear_warned_ambiguous_headers()
        files = self._collect_files()
        if not files:
            console.warning("No files found to rename.")
            console.info(
                "Files should be located in or under: "
                f"{os.path.dirname(self.excel_file)}"
            )
            return

        files_by_folder: dict[str, list[str]] = {}
        for f in files:
            files_by_folder.setdefault(os.path.dirname(f), []).append(f)

        self._prepare_backup(files_by_folder)

        all_ops: list[RenameOperation] = []
        renamed_count = 0
        empty_files: list[str] = []
        base_dir = os.path.dirname(os.path.abspath(self.excel_file))

        # Resolve Excel context (sheet) per source folder.
        folder_contexts: dict[str, tuple[ExcelContext, str]] = {}
        for folder in files_by_folder:
            ctx = self._resolve_context(folder)
            if ctx is not None:
                folder_contexts[folder] = ctx

        folder_keys = list(files_by_folder.keys())
        for folder in folder_keys:
            folder_files = files_by_folder[folder]
            print()
            console.rule(f"Folder: {os.path.basename(folder.rstrip(os.sep))}", dash_count=10)
            section_num = folder_keys.index(folder) + 1
            console.info(
                f"Folder {section_num}/{len(folder_keys)}: "
                f"{os.path.basename(folder.rstrip(os.sep))}"
            )

            resolved = folder_contexts.get(folder)
            if resolved is None:
                console.warning(
                    f"Skipping folder {os.path.basename(folder.rstrip(os.sep))}, "
                    "no matching Excel data found."
                )
                continue
            ctx, sheet_name = resolved
            console.info(f"Using worksheet: {sheet_name}")

            parse_result = ParseResult.from_folder_path(folder)

            print(f"\nSort files for worksheet '{sheet_name}'? (y/n): ", end="")
            line = safe_read_line(self.input_fn)
            sort_choice = line.strip().lower() if line is not None else ""

            sheet_row_mapping: dict[int, int] | None = None
            use_custom_sort = False

            if sort_choice == "y":
                sort_col = self._ask_sort_column(ctx, sheet_name)
                col_idx = col_index(sort_col) if sort_col else None
                if sort_col and col_idx is not None:
                    console.success(f"Sort by column: {sort_col}")
                    sheet_row_mapping = self._build_row_mapping(ctx, col_idx)
                    use_custom_sort = True
                else:
                    console.info("Using built-in row numbers as sequence numbers")
            else:
                console.info("No sorting, keep original filenames")

            padding_width = len(str(len(ctx.grid)))

            for file in folder_files:
                if os.path.basename(file) == config.ds_store:
                    continue
                result = self._rename_single_file(
                    file,
                    ctx,
                    padding_width,
                    sheet_row_mapping,
                    use_custom_sort,
                    sort_choice,
                    parse_result,
                    base_dir,
                )
                if result.kind == "success" and result.op:
                    all_ops.append(result.op)
                    renamed_count += 1
                elif result.kind == "failure":
                    if result.op:
                        all_ops.append(result.op)
                    filename = os.path.basename(file)
                    msg = result.message
                    if "All columns empty" in msg or "all columns empty" in msg:
                        empty_files.append(filename)
                    elif "No row number found" in msg or "Invalid column letters" in msg:
                        console.warning(f"WARNING: {msg}")
                    elif "Filename unchanged" in msg:
                        pass
                    else:
                        console.warning(f"Error processing {filename}: {msg}")

        # Finalize batch.
        if all_ops and self.coordinator.backup_directory:
            batch = RenameBatch.new(
                all_ops,
                os.path.basename(self.coordinator.backup_directory),
            )
            self.coordinator.append_batch(batch)

        print()
        console.success(f"Renamed: {renamed_count} files")
        if empty_files:
            console.warning(
                f"{len(empty_files)} files had all empty columns and were not renamed"
            )

    # ------------------------------------------------------------------ #
    # File collection & context
    # ------------------------------------------------------------------ #
    def _collect_files(self) -> list[str]:
        excel_dir = os.path.dirname(os.path.abspath(self.excel_file))
        stem = os.path.splitext(os.path.basename(self.excel_file))[0]
        excel_filename = string_transform.sanitize(stem)
        excel_folder = os.path.join(excel_dir, excel_filename)
        start_dir = excel_folder if os.path.isdir(excel_folder) else excel_dir

        if not os.path.isdir(start_dir):
            console.error("ERROR: start_dir does not exist!")
            return []

        files: list[str] = []
        for root, dirs, names in os.walk(start_dir):
            # Do not descend into backup dirs.
            dirs[:] = [d for d in dirs if not d.startswith(config.Paths.backup_prefix)]
            for name in names:
                parent = os.path.basename(root)
                if parent.startswith(config.Paths.backup_prefix):
                    continue
                if name == config.ds_store or name == os.path.basename(self.excel_file):
                    continue
                path = os.path.join(root, name)
                if os.path.isfile(path):
                    files.append(path)
        return files

    def _resolve_context(self, folder: str) -> tuple[ExcelContext, str] | None:
        excel_dir = os.path.dirname(os.path.abspath(self.excel_file))
        stem = os.path.splitext(os.path.basename(self.excel_file))[0]
        excel_name = string_transform.sanitize(stem)

        rel = folder.replace(excel_dir + os.sep, "")
        parts = [p for p in rel.split(os.sep) if p]

        target_sheet: str | None = None
        if len(parts) >= 2 and parts[0] == excel_name:
            target_sheet = parts[1]
        elif len(parts) >= 1:
            target_sheet = parts[0]
        if target_sheet is None:
            return None

        try:
            wb = open_workbook(self.excel_file)
            try:
                available = excel_parser.sheet_names(wb)
                matched = next(
                    (n for n in available if n.casefold() == target_sheet.casefold()),
                    None,
                )
                if matched is None:
                    if available:
                        first = available[0]
                        console.warning(
                            f"Sheet '{target_sheet}' not found, using first sheet '{first}'"
                        )
                        ctx = read_excel_to_grid(
                            self.excel_file, first,
                            config.Limits.default_excel_start_row, workbook=wb,
                        )
                        return (ctx, first)
                    return None
                ctx = read_excel_to_grid(
                    self.excel_file, matched,
                    config.Limits.default_excel_start_row, workbook=wb,
                )
                return (ctx, matched)
            finally:
                wb.close()
        except Exception:
            return None

    # ------------------------------------------------------------------ #
    # Backup
    # ------------------------------------------------------------------ #
    def _prepare_backup(self, files_by_folder: dict[str, list[str]]) -> None:
        file_system.init_backup_directory(self.excel_file, self.coordinator)
        backup_dir = self.coordinator.backup_directory
        if backup_dir is None:
            from ..errors import BackupError

            raise BackupError("Failed to initialize backup directory.")
        source_dir = os.path.dirname(os.path.abspath(self.excel_file))
        file_system.ensure_same_volume(source_dir, backup_dir)
        if not file_system.backup_folder_structure(
            list(files_by_folder.keys()), to=backup_dir, base_dir=source_dir
        ):
            self._cleanup_failed_backup(backup_dir)
            from ..errors import BackupError

            raise BackupError(
                "CRITICAL: Aborting rename process because folder structure backup failed."
            )
        console.success("Backup completed.")

    def _cleanup_failed_backup(self, backup_dir: str) -> None:
        shutil.rmtree(backup_dir, ignore_errors=True)
        self.coordinator.backup_directory = None

    # ------------------------------------------------------------------ #
    # Sorting
    # ------------------------------------------------------------------ #
    def _ask_sort_column(self, ctx: ExcelContext, sheet_name: str) -> str | None:
        for _ in range(config.Limits.max_sort_attempts):
            print(
                f"Specify sort column for Sheet '{sheet_name}' (A-Z) or press "
                "Enter to sort by row number: ",
                end="",
            )
            line = safe_read_line(self.input_fn)
            if line is None:
                return None  # EOF
            raw = line.strip().upper()
            if not raw:
                return None
            if (
                len(raw) == 1
                and raw[0].isalpha()
                and (idx := col_index(raw)) is not None
                and (not ctx.grid or idx < len(ctx.grid[0]))
            ):
                return raw
            console.error("Invalid input, please enter a single letter")
        console.warning("Multiple invalid attempts, skipping sorting")
        return None

    def _build_row_mapping(self, ctx: ExcelContext, col_idx: int) -> dict[int, int]:
        indices = list(range(1, len(ctx.grid)))
        indices.sort(key=lambda a: (ctx.grid[a][col_idx] if col_idx < len(ctx.grid[a]) else "").lower())
        mapping: dict[int, int] = {}
        # grid index r -> Excel row number r+1 (grid[0] is header row 1).
        for order, r in enumerate(indices, start=1):
            mapping[r + 1] = order
        return mapping

    # ------------------------------------------------------------------ #
    # Core rename logic
    # ------------------------------------------------------------------ #
    def _rename_single_file(
        self,
        file: str,
        ctx: ExcelContext,
        padding_width: int,
        sheet_row_mapping: dict[int, int] | None,
        use_custom_sort: bool,
        sort_choice: str,
        parse_result: ParseResult,
        base_dir: str,
    ) -> _RenameResult:
        filename = os.path.basename(file)
        if filename == config.ds_store:
            return _RenameResult("skipped", message="ds_store")

        stem, ext = os.path.splitext(filename)
        ext_with_dot = ext
        parts = stem.split("-")

        row_num: int | None = None
        start_idx = 0
        part_type = classify_filename(filename)

        def _int(s: str) -> int | None:
            try:
                return int(s)
            except ValueError:
                return None

        if part_type == FileNamePartType.digits_only:
            row_num = _int(stem)
            start_idx = 1
        elif parts and _int(parts[0]) is not None:
            row_num = _int(parts[0])
            start_idx = 1
        elif part_type == FileNamePartType.letters_only and parse_result.is_valid or parse_result.is_valid:
            row_num = parse_result.row_number
            start_idx = 0

        if row_num is None:
            return _RenameResult("failure", message=f"No row number found: {filename}")

        data_row_index = row_num - ctx.start_row + 1
        if not (1 <= data_row_index < len(ctx.grid)):
            return _RenameResult(
                "failure", message=f"Row number {row_num} out of range: {filename}"
            )

        # Column parts.
        if start_idx == 0:
            column_parts = parts
        elif start_idx < len(parts):
            column_parts = parts[start_idx:]
        else:
            column_parts = []

        # Validate letters-only column parts.
        if column_parts and not all(
            config.Regex.letters_only.fullmatch(p) for p in column_parts
        ):
            return _RenameResult(
                "failure", message=f"Invalid column letters in filename: {filename}"
            )

        # Order prefix.
        if use_custom_sort and sheet_row_mapping and row_num in sheet_row_mapping:
            order_str = f"{sheet_row_mapping[row_num]:0{padding_width}d}-"
        elif sort_choice == "y":
            order_str = f"{row_num:0{padding_width}d}-"
        else:
            order_str = ""

        # Auto-detect the data-table header row by scanning column A for the
        # serial header ("序号"/"注册号").
        header_row_index = 0
        for i, row in enumerate(ctx.grid):
            col_a = row[0] if row else ""
            if col_a == "序号" or col_a == "注册号":
                header_row_index = i
                break

        # Build column letter -> header map.
        letter_to_header: dict[str, str] = {}
        for i, header in enumerate(ctx.grid[header_row_index]):
            letter_ = col_letter(i)
            if letter_ is not None:
                letter_to_header[letter_.lower()] = header
                letter_to_header[letter_.upper()] = header

        data_row = ctx.grid[data_row_index]

        if not column_parts:
            # No column letters -> scan all non-empty cells.
            collected = self._collect_cell_values(data_row)
            if collected is None:
                return _RenameResult(
                    "failure", message=f"All columns empty: {filename}"
                )
            new_parts = collected
        elif len(column_parts) == 1:
            # Single letters group -> use header names.
            collected = []
            for ch in column_parts[0].upper():
                header = letter_to_header.get(ch)
                if header is not None:
                    clean_header = string_transform.sanitize(header)
                    collected.append(clean_header if clean_header else ch)
                else:
                    collected.append(ch)
            new_parts = collected
        else:
            # Multiple parts -> flatten letters, read cell values.
            all_letters: list[str] = []
            for part in column_parts:
                all_letters.extend(ch for ch in part.upper())
            collected = []
            for ch in all_letters:
                idx = col_index(ch)
                if idx is None:
                    continue
                val = data_row[idx] if idx < len(data_row) else ""
                val = val.strip()
                if not val:
                    continue
                formatted = string_transform.format_date_string(val)
                clean = string_transform.sanitize(formatted)
                if clean:
                    collected.append(clean)
            if not collected:
                return _RenameResult(
                    "failure", message=f"All columns empty: {filename}"
                )
            new_parts = collected

        if not new_parts:
            return _RenameResult("failure", message=f"No valid columns: {filename}")

        new_name = "-".join(new_parts)
        new_filename = f"{order_str}{new_name}{ext_with_dot}"

        if new_filename == filename:
            return _RenameResult("skipped", message=f"Filename unchanged: {filename}")

        old_rel = file_system.get_relative_path(base_dir, file)
        safe_name, _ = string_transform.truncate_path_component(new_filename)
        final_url = file_system.get_unique_file_path(
            os.path.join(os.path.dirname(file), safe_name)
        )
        new_rel = file_system.get_relative_path(base_dir, final_url)

        try:
            os.replace(file, final_url)
        except OSError as exc:
            op = RenameOperation(
                old_relative_path=old_rel,
                new_relative_path=new_rel,
                relative_backup_path=old_rel,
                status=OperationStatus.failed,
                error_message=str(exc),
            )
            console.error(f"Failed to rename {filename}: {exc}")
            return _RenameResult("failure", op=op, message=str(exc))

        op = RenameOperation(
            old_relative_path=old_rel,
            new_relative_path=new_rel,
            relative_backup_path=old_rel,
            status=OperationStatus.success,
            error_message=None,
        )
        return _RenameResult("success", op=op)

    @staticmethod
    def _collect_cell_values(data_row: list[str]) -> list[str] | None:
        collected: list[str] = []
        for val in data_row:
            val = val.strip()
            if not val:
                continue
            formatted = string_transform.format_date_string(val)
            clean = string_transform.sanitize(formatted)
            if clean:
                collected.append(clean)
        return collected if collected else None

    # ------------------------------------------------------------------ #
    # Undo
    # ------------------------------------------------------------------ #
    def undo_last_batch(self) -> None:
        if self.coordinator.is_history_empty:
            console.warning("Nothing to undo.")
            return
        base_dir = os.path.dirname(os.path.abspath(self.excel_file))
        batch = self.coordinator.last_batch
        if batch is None:
            return
        backup_dir = os.path.join(base_dir, batch.backup_dir_name)

        success = originally_failed = already_restored = failed = 0
        has_new_progress = False

        for i in reversed(range(len(batch.operations))):
            op = batch.operations[i]
            if op.is_restored:
                already_restored += 1
                continue
            if op.status != OperationStatus.success:
                originally_failed += 1
                continue
            backup_file = os.path.join(backup_dir, op.relative_backup_path)
            original_file = os.path.join(base_dir, op.old_relative_path)
            if not os.path.isfile(backup_file):
                console.warning(
                    f"Backup missing for {os.path.basename(original_file)}, skipping restore."
                )
                failed += 1
                continue

            temp_restore = os.path.join(
                os.path.dirname(original_file),
                f"{config.Defaults.temp_restore_prefix}{uuid.uuid4()}",
            )
            if os.path.exists(original_file):
                try:
                    os.replace(original_file, temp_restore)
                except OSError as exc:
                    console.warning(
                        f"Failed to move current file to temp state: {exc}"
                    )
                    failed += 1
                    continue

            try:
                os.replace(backup_file, original_file)
                if os.path.exists(temp_restore):
                    os.remove(temp_restore)
                # Remove the renamed file now that the original is restored.
                renamed_file = os.path.join(base_dir, op.new_relative_path)
                if renamed_file != original_file and os.path.exists(renamed_file):
                    os.remove(renamed_file)
                op.is_restored = True
                self.coordinator.update_last_batch(
                    lambda b: self._set_op(b, i, op)
                )
                has_new_progress = True
                success += 1
            except OSError as exc:
                console.error(
                    f"Failed to restore {os.path.basename(original_file)}: {exc}"
                )
                console.error(
                    f"Original file is safely preserved at: {temp_restore}"
                )
                failed += 1

        total_ops = len(batch.operations)
        if failed == 0 and success + originally_failed + already_restored == total_ops:
            self.coordinator.remove_last_batch()
            if os.path.isdir(backup_dir) and not os.listdir(backup_dir):
                shutil.rmtree(backup_dir, ignore_errors=True)
            console.success(
                f"Undo completed: {success} restored, {originally_failed} "
                f"originally failed, {already_restored} already restored."
            )
        elif failed == 0:
            if has_new_progress:
                self.coordinator._save_history()
            console.success(
                f"Undo progress: {success} restored, {originally_failed} "
                f"originally failed, {already_restored} already restored."
            )
        else:
            if has_new_progress:
                self.coordinator._save_history()
            console.error(
                f"Undo halted with {failed} errors! Progress is saved. "
                "You can retry 'Undo' to continue."
            )

    @staticmethod
    def _set_op(batch: RenameBatch, index: int, op: RenameOperation) -> None:
        batch.operations[index] = op
