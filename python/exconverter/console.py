"""Console formatting utilities (port of Utils/Console.swift).

Swift's width calculation gives CJK-range characters a display width of 2.
`isEmojiPresentation` has no direct Python equivalent; we approximate it with
the common Emoji_Presentation blocks that affect layout.
"""

from __future__ import annotations

from . import config

_RESET = "\u001B[0m"


def _is_wide_cjk(cp: int) -> bool:
    return (
        0x1100 <= cp <= 0x115F
        or 0x2E80 <= cp <= 0x303F
        or 0x3040 <= cp <= 0x33BF
        or 0x3400 <= cp <= 0x4DBF
        or 0x4E00 <= cp <= 0x9FFF
        or 0xA960 <= cp <= 0xA97F
        or 0xAC00 <= cp <= 0xD7AF
        or 0xF900 <= cp <= 0xFAFF
        or 0xFE10 <= cp <= 0xFE6F
        or 0xFF01 <= cp <= 0xFF60
        or 0xFFE0 <= cp <= 0xFFE6
    )


# Approximate Emoji_Presentation ranges (affects layout width = 2).
_EMOJI_BLOCKS = (
    (0x1F000, 0x1FAFF),
    (0x2600, 0x27BF),
    (0x2B00, 0x2BFF),
    (0x2190, 0x21FF),
    (0x2300, 0x23FF),
    (0x2700, 0x27BF),
    (0x2B05, 0x2B07),
    (0xFE0F, 0xFE0F),
)


def _is_emoji_presentation(cp: int) -> bool:
    return any(lo <= cp <= hi for lo, hi in _EMOJI_BLOCKS)


def display_width(of: str) -> int:
    width = 0
    for ch in of:
        cp = ord(ch)
        if _is_emoji_presentation(cp) or _is_wide_cjk(cp):
            width += 2
        else:
            width += 1
    return width


def _pad_right(to_width: int, string: str) -> str:
    current = display_width(of=string)
    if current >= to_width:
        return string
    return string + " " * (to_width - current)


def success(msg: str) -> None:
    print(f"\u001B[32m\u2714 {msg}{_RESET}")


def warning(msg: str) -> None:
    print(f"\u001B[33m\u26A0\uFE0F {msg}{_RESET}")


def error(msg: str) -> None:
    print(f"\u001B[31m\u2717 {msg}{_RESET}")


def info(msg: str) -> None:
    print(msg)


def debug(msg: str) -> None:
    print(f"\u001B[90m \u21B3 {msg}{_RESET}")


def rule(title: str = "", dash_count: int = config.Display.panel_line_width) -> None:
    line = "\u2500" * dash_count
    print(line if not title else f"{line} {title} {line}")


def panel(title: str, content: str) -> None:
    lines = content.split("\n")
    max_content_width = max((display_width(of=ln) for ln in lines), default=0)
    display_title = title
    if len(display_title) > config.Display.max_title_display_chars:
        display_title = (
            display_title[: config.Display.max_title_display_chars - 3] + "..."
        )
    title_used_width = 3 + display_width(of=display_title)
    inner_width = max(max_content_width + 2, title_used_width + 2)
    title_line_padding = max(0, inner_width - title_used_width)
    print(
        "\u250C\u2500 "
        + display_title
        + " "
        + "\u2500" * title_line_padding
        + "\u2510"
    )
    for line in lines:
        padded = _pad_right(to_width=max_content_width, string=line)
        print("\u2502 " + padded + " \u2502")
    print("\u2514" + "\u2500" * inner_width + "\u2518")
