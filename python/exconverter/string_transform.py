"""String cleaning, UTF-8-safe truncation, and date formatting
(port of Utils/StringTransform.swift).
"""

from __future__ import annotations

import datetime
import re

from . import config, console

_CHINESE_DATE_PATTERN = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")


def sanitize(s: str | None) -> str:
    """Trim, drop illegal filename chars, and guard Windows reserved names.

    Mirrors Swift: trim whitespace; if empty return ""; if the component before
    the first "." uppercased is a Windows reserved name, wrap the *trimmed*
    original in underscores; otherwise strip illegal characters.
    """
    if s is None:
        return ""
    trimmed = s.strip()
    if not trimmed:
        return ""

    stem = next((part for part in trimmed.split(".") if part), "").upper()
    if stem in config.reserved_windows_names:
        return f"_{trimmed}_"

    return config.Regex.invalid_chars.sub("", trimmed)


def safe_utf8_truncate(string: str, max_byte_len: int) -> str:
    """Truncate to a UTF-8 byte budget without splitting a code point."""
    if len(string.encode("utf-8")) <= max_byte_len:
        return string
    result = ""
    current_bytes = 0
    for ch in string:
        ch_bytes = len(ch.encode("utf-8"))
        if current_bytes + ch_bytes > max_byte_len:
            break
        result += ch
        current_bytes += ch_bytes
    return result


def truncate_path_component(
    component: str, max_len: int = config.Limits.max_path_component_length
) -> tuple[str, bool]:
    """Truncate a path component to a byte budget, keeping its extension."""
    if len(component.encode("utf-8")) <= max_len:
        return component, False

    stem = component
    ext = ""
    # Swift uses lastIndex(of: ".") != startIndex
    dot_index = component.rfind(".")
    if dot_index > 0:
        stem = component[:dot_index]
        ext = component[dot_index:]

    ext_len = len(ext.encode("utf-8"))
    suffix = "..."
    suffix_len = len(suffix.encode("utf-8"))
    max_stem_len = max_len - ext_len - suffix_len

    if max_stem_len <= 0:
        safe = safe_utf8_truncate(component, max_byte_len=max_len)
        console.warning(f"Path truncated (ext too long): {component} -> {safe}")
        return safe, True

    safe_stem = safe_utf8_truncate(stem, max_byte_len=max_stem_len)
    final = safe_stem + suffix + ext
    console.warning(f"Path truncated: {component} -> {final}")
    return final, True


def _is_valid_date(year: int, month: int, day: int) -> bool:
    try:
        datetime.date(year, month, day)
        return True
    except ValueError:
        return False


def _validate_and_format_date(year: int, month: int, day: int) -> str | None:
    if not (config.Limits.year_min <= year <= config.Limits.year_max):
        return None
    if not (1 <= month <= 12):
        return None
    if not (1 <= day <= 31):
        return None
    if not _is_valid_date(year, month, day):
        return None
    return f"{year:04d}{month:02d}{day:02d}"


def format_date_string(value: str) -> str:
    """Normalize many date shapes to YYYYMMDD (port of formatDateString)."""
    str_value = value.strip()
    if not str_value:
        return ""

    # Remove a trailing date-time suffix, e.g. " 12:30:45" or " 123456".
    str_value = config.Regex.date_time_suffix.sub("", str_value)

    # All digits but not 8 -> not a date; sanitize and return early.
    is_all_digits = str_value.isdecimal()
    if is_all_digits and len(str_value) != 8:
        return sanitize(str_value)

    # Try splitting on date separators - / .
    parts = [p for p in re.split(r"[-/.]", str_value) if p]
    if len(parts) == 3:
        # YYYY-MM-DD
        if len(parts[0]) == 4:
            try:
                y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
            except ValueError:
                y = m = d = None
            if y is not None:
                formatted = _validate_and_format_date(y, m, d)
                if formatted is not None:
                    return formatted
        # MM-DD-YYYY or DD-MM-YYYY
        if len(parts[2]) == 4:
            try:
                y = int(parts[2])
                m, d = int(parts[0]), int(parts[1])
            except ValueError:
                y = None
                m = d = None
            if y is not None:
                formatted = _validate_and_format_date(y, m, d)
                if formatted is not None:
                    return formatted
                # Try DD-MM-YYYY
                formatted = _validate_and_format_date(y, d, m)
                if formatted is not None:
                    return formatted

    # Chinese date pattern — searches anywhere in the string (Swift uses
    # NSRegularExpression.firstMatch, not an anchored match).
    m = _CHINESE_DATE_PATTERN.search(str_value)
    if m:
        try:
            y, mo, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        except ValueError:
            y = mo = day = None
        if y is not None:
            formatted = _validate_and_format_date(y, mo, day)
            if formatted is not None:
                return formatted

    # 8-digit date YYYYMMDD
    if config.Regex.eight_digit.fullmatch(str_value):
        try:
            y = int(str_value[:4])
            mo = int(str_value[4:6])
            day = int(str_value[6:8])
        except ValueError:
            y = mo = day = None
        if y is not None:
            formatted = _validate_and_format_date(y, mo, day)
            if formatted is not None:
                return formatted

    return sanitize(str_value)
