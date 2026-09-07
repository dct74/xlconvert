"""Pytest fixtures for shared-string xlsx files.

Real Excel/WPS xlsx files store strings in a shared-strings table. openpyxl
writes ``inlineStr`` instead, which CoreXLSX (the Swift reference) cannot read.
Tests that claim to mirror Swift must therefore use shared-string fixtures, so
these helpers are the single way to build xlsx in tests.
"""

import os
import sys
from pathlib import Path

import pytest

# Ensure xlsx_util is importable (it lives beside this file).
sys.path.insert(0, os.path.dirname(__file__))
from xlsx_util import write_shared_string_xlsx  # noqa: E402


@pytest.fixture()
def shared_xlsx_writer():
    """Callable returning the path of a shared-string xlsx in tmp_path."""
    def _write(name, sheets, tmp_dir=None, **kw):
        target = Path(tmp_dir) / name if tmp_dir else name
        if tmp_dir is None:
            target.parent.mkdir(parents=True, exist_ok=True)
        write_shared_string_xlsx(target, sheets, **kw)
        return str(target)

    return _write
