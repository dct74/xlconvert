"""Rename state / history coordinator (port of State/RenameStateManager.swift).

Swift used an UnfairLock; Python's GIL makes explicit locking unnecessary for
this single-threaded CLI, so state is held on a plain object. The on-disk
history file (JSON in the temp dir, keyed by the Excel file name) is preserved
for cross-run undo support, matching Swift.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile

from . import config, console
from .models import RenameBatch


class RenameStateManager:
    def __init__(self, excel_file: str):
        basename = os.path.basename(excel_file)
        filename = f"ExcelConverter_{basename}_{config.Paths.undo_history_filename}"
        self.history_file_url = os.path.join(tempfile.gettempdir(), filename)
        self._backup_directory: str | None = None
        self._rename_history: list[RenameBatch] = []
        self._load_history()

    # --- backup dir -------------------------------------------------------
    @property
    def backup_directory(self) -> str | None:
        return self._backup_directory

    @backup_directory.setter
    def backup_directory(self, value: str | None) -> None:
        self._backup_directory = value

    # --- history ----------------------------------------------------------
    @property
    def is_history_empty(self) -> bool:
        return not self._rename_history

    @property
    def last_batch(self) -> RenameBatch | None:
        return self._rename_history[-1] if self._rename_history else None

    def append_batch(self, batch: RenameBatch) -> None:
        self._rename_history.append(batch)
        self._save_history()

    def remove_last_batch(self) -> None:
        if self._rename_history:
            self._rename_history.pop()
        self._save_history()

    def update_last_batch(self, update) -> None:
        """Apply `update(batch)` to the last batch in place."""
        if not self._rename_history:
            return
        update(self._rename_history[-1])

    def clear_warned_ambiguous_headers(self) -> None:
        # Retained for API parity with Swift; header-ambiguity tracking was
        # unused by the rename processor in the ported path.
        pass

    # --- persistence ------------------------------------------------------
    def _save_history(self) -> None:
        data = [b.to_dict() for b in self._rename_history]
        try:
            with open(self.history_file_url, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError as exc:
            console.warning(f"Failed to save rename history: {exc}")

    def _load_history(self) -> None:
        if not os.path.isfile(self.history_file_url):
            return
        try:
            with open(self.history_file_url, encoding="utf-8") as f:
                data = json.load(f)
            batches = [RenameBatch.from_dict(d) for d in data]
            if all(b.version == config.history_version for b in batches):
                self._rename_history = batches
            else:
                console.warning("Rename history version mismatch. History ignored.")
                self._remove_history_file()
        except (OSError, ValueError) as exc:
            console.warning(f"Failed to load rename history: {exc}")
            self._remove_history_file()

    def _remove_history_file(self) -> None:
        with contextlib.suppress(OSError):
            os.remove(self.history_file_url)