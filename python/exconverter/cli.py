"""CLI entry point (port of Swift main.swift).

Menu flow:
  IPO filename -> auto-process and exit.
  Otherwise loop: WPSheet (exits after), ControlSheet / Rename / Undo (return to
  menu), Exit (optionally delete the backup dir).
"""

from __future__ import annotations

import os
import shutil
import sys
from collections.abc import Callable

from . import config, console
from .console_io import get_excel_file, is_ipo_template, safe_read_line
from .processors.control_sheet import ControlSheetProcessor
from .processors.ipo import IPOTemplateProcessor
from .processors.rename import FileRenameProcessor
from .processors.wp_sheet import WPSheetProcessor
from .state import RenameStateManager

_MENU = """[1] WPSheet to folders
[2] ControlSheet to folders
[3] Rename files using Excel
[4] Undo rename
[Q] Exit"""

_VALID = {"1", "2", "3", "4", "q"}


def show_menu(input_fn: Callable[[], str]) -> str:
    print()
    console.panel("Excel to Folders", _MENU)
    while True:
        print("Select option: ", end="", flush=True)
        line = safe_read_line(input_fn)
        if line is None:
            # Swift readLine() == nil -> exit menu gracefully.
            console.info("EOF detected, exiting.")
            return "q"
        raw = line.strip().lower()
        if raw not in _VALID:
            console.error("Invalid option. Please try again.")
            continue
        return raw


def _backup_dir_for(excel_file: str) -> str:
    from . import string_transform

    stem = os.path.splitext(os.path.basename(excel_file))[0]
    sanitized = string_transform.sanitize(stem)
    return os.path.join(
        os.path.dirname(excel_file), f"{sanitized}{config.Paths.backup_prefix}"
    )


def _maybe_delete_backup(excel_file: str, input_fn: Callable[[], str]) -> None:
    backup_dir = _backup_dir_for(excel_file)
    if not os.path.isdir(backup_dir):
        return
    print("Delete backup directory? (y/n, default: n): ", end="", flush=True)
    line = safe_read_line(input_fn)
    if line is None:
        console.info(
            f"Backup directory preserved: {os.path.basename(backup_dir)}"
        )
        return
    answer = line.strip().lower()
    if answer == config.InputKeys.yes:
        shutil.rmtree(backup_dir, ignore_errors=True)
        console.info("Backup directory deleted.")
    else:
        console.info(
            f"Backup directory preserved: {os.path.basename(backup_dir)}"
        )


def main(argv=None) -> None:
    if argv is None:
        argv = sys.argv[1:]
    input_fn: Callable[[], str] = input

    excel_file = get_excel_file(input_fn)
    if excel_file is None:
        # Swift: no file chosen (incl. EOF) -> nothing runs, program ends exit 0.
        return

    try:
        # IPO auto-detection.
        if is_ipo_template(excel_file):
            console.info(
                f"\nIPO template file detected: {os.path.basename(excel_file)}"
            )
            console.rule()
            console.info(
                f"\nProcessing IPO template: {os.path.basename(excel_file)}"
            )
            IPOTemplateProcessor(excel_file, input_fn=input_fn).process()
            sys.exit(0)

        coordinator = RenameStateManager(excel_file)

        while True:
            choice = show_menu(input_fn)
            if choice == "1":  # WPSheet
                WPSheetProcessor(excel_file, input_fn=input_fn).process()
                console.success("WPSheet processing completed successfully.")
                console.info("\nExiting program...")
                break
            elif choice == "2":  # ControlSheet
                ControlSheetProcessor(excel_file, input_fn=input_fn).process()
            elif choice == "3":  # Rename
                FileRenameProcessor(
                    excel_file, coordinator=coordinator, input_fn=input_fn
                ).process()
            elif choice == "4":  # Undo
                FileRenameProcessor(
                    excel_file, coordinator=coordinator, input_fn=input_fn
                ).undo_last_batch()
            elif choice == "q":  # Exit
                _maybe_delete_backup(excel_file, input_fn)
                break
    except Exception as exc:
        console.error(f"Error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
