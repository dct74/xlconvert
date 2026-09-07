"""Excel column letter <-> index conversion (port of Utils/ExcelColumns.swift).

Only single columns A..Z (index 0..25) are produced; multi-letter input that
would exceed the 26-column cap is rejected (matches Swift).
"""

from __future__ import annotations

from . import config

_A = ord("A")


def letter(index: int) -> str | None:
    """Return the single column letter for a 0-based index, or None if invalid."""
    if 0 <= index < config.Limits.max_excel_columns:
        return chr(_A + index)
    return None


def index(letter_: str) -> int | None:
    """Return the 0-based index for a column letter (case-insensitive).

    Accepts only input that lands within the A..Z cap. Multi-letter input is
    decoded base-26 then range-checked, reproducing Swift's behavior of
    rejecting e.g. "AB" (would be 27 -> index 26 -> out of range).
    """
    upper = letter_.upper()
    result = 0
    for ch in upper:
        av = ord(ch)
        if not (_A <= av <= _A + 25):
            return None
        result = result * 26 + (av - _A + 1)
    zero_based = result - 1
    if not (0 <= zero_based < config.Limits.max_excel_columns):
        return None
    return zero_based
