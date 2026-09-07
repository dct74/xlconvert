"""Chinese-ordinal parsing and directory sequence-prefix helpers.

This is a deliberate Python-only enhancement (NOT in the Swift source): to let
folders whose names start with a Chinese ordinal (第X部分 / 第X章 / 一、 …)
sort numerically, we prefix each such directory with an Arabic sequence number
padded with leading zeros, e.g.:

    "第一章 发行人本次发行上市的批准"  ->  "01 第一章 发行人本次发行上市的批准"
    "第二部分 尽职调查工作记录"        ->  "02 第二部分 尽职调查工作记录"

Padding width rule (user-confirmed "C"): at least 2 digits; widen only when the
largest ordinal at that level needs more. Width is therefore computed per
parent directory (all ordinal-named children under one parent = one level).

Supported Chinese numerals: 一..九, 十, 十一..十九, 二十..九十九, 一百.
"""

from __future__ import annotations

import os
import re
from collections import defaultdict

# Chinese digit char -> value (ones). Zero ("零") accepted but not emitted by us.
_DIGITS = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9,
}
_NUMBER_CHARS = "一二三四五六七八九十百零"
_UNIT_CHARS = "部分章节编篇款项"  # trailing unit after 第X (word-forming), plus 、


def chinese_number_to_int(text: str) -> int | None:
    """Parse a leading Chinese numeral (一..一百) into an int.

    Returns the value if `text` starts with a supported numeral, else None.
    """
    if not text:
        return None
    # Consume the leading run of numeral chars.
    n = 0
    while n < len(text) and text[n] in _NUMBER_CHARS:
        n += 1
    if n == 0:
        return None
    token = text[:n]
    # "零" only makes sense inside e.g. 一百零五; not required -> reject alone.
    val = _parse_ordinal_token(token)
    return val


def _parse_ordinal_token(token: str) -> int | None:
    """Parse a pure Chinese numeral token like 一 / 十 / 二十三 / 一百."""
    if not token or token == "零":
        return None
    # 100
    if token == "一百":
        return 100
    if token.startswith("百"):
        return None  # only 一百 supported
    # tens-and-ones forms up to 九十九.
    # Cases: "十" | "X十" | "X十Y" | "一".."九"
    if token == "十":
        return 10
    if "十" in token:
        parts = token.split("十")
        tens_str, ones_str = parts[0], parts[1] if len(parts) > 1 else ""
        tens = 1 if tens_str == "" else _DIGITS.get(tens_str)
        if tens is None:
            return None
        ones = _DIGITS.get(ones_str) if ones_str else 0
        if ones is None:
            return None
        return tens * 10 + ones
    # plain single digit 一..九
    return _DIGITS.get(token)


def _strip_ordinal_prefix(name: str) -> tuple[str, int] | None:
    """Return (seqtype, number) if `name` starts with a supported ordinal.

    seqtype distinguishes naming families so siblings of different families
    under one parent never share a width or a number: it carries the trailing
    unit word for `第X<unit>` (so 第X章 and 第X部分 are distinct) and a marker
    for the `X、` item family.
    """
    # Family 1: 第X部分/章/节 ... (unit is the leading word chars, no 、)
    if name.startswith("第"):
        rest = name[1:]
        m = re.match(rf"([{_NUMBER_CHARS}]+)([{_UNIT_CHARS}]+)", rest)
        if m:
            num = chinese_number_to_int(m.group(1))
            if num is not None:
                unit = m.group(2)
                return (f"ord_第{unit}", num)
    # Family 2: X、条目
    m = re.match(rf"([{_NUMBER_CHARS}]+)、", name)
    if m:
        num = chinese_number_to_int(m.group(1))
        if num is not None:
            return ("ord_、", num)
    return None


def add_sequence_prefix(root_dir: str) -> int:
    """Prefix ordinal-named directories under `root_dir` with Arabic numbers.

    Walks deepest-first so renaming a child never invalidates a parent path.
    Width is chosen per (parent, seqtype) group as max(2, digits of max ordinal),
    then every member is renamed to "NN <original>".

    Returns the number of directories renamed.
    """
    # Collect all directories with their depth.
    nodes: list[tuple[int, str]] = []
    for base, dirs, _files in os.walk(root_dir):
        # depth = number of path components under root
        depth = 0 if os.path.abspath(base) == os.path.abspath(root_dir) else (
            len(os.path.relpath(base, root_dir).split(os.sep))
        )
        for d in dirs:
            nodes.append((depth, os.path.join(base, d)))
    nodes.sort(reverse=True)  # deepest first

    # Group children by parent to size widths. We re-derive parent from path.
    by_parent: dict[str, list[tuple[str, str, int]]] = defaultdict(list)
    for _depth, path in nodes:
        parent = os.path.dirname(path)
        base = os.path.basename(path)
        parsed = _strip_ordinal_prefix(base)
        if parsed is not None:
            stype, num = parsed
            by_parent[parent].append((base, stype, num))

    # Compute width per (parent, stype).
    width: dict[tuple[str, str], int] = {}
    for parent, items in by_parent.items():
        by_type: dict[str, list[int]] = defaultdict(list)
        for _base, stype, num in items:
            by_type[stype].append(num)
        for stype, nums in by_type.items():
            w = len(str(max(nums)))
            width[(parent, stype)] = max(2, w)

    renamed = 0
    # Process deepest-first; renaming only changes leaf names, safe.
    for _depth, path in nodes:
        parent = os.path.dirname(path)
        base = os.path.basename(path)
        parsed = _strip_ordinal_prefix(base)
        if parsed is None:
            continue
        stype, num = parsed
        w = width.get((parent, stype))
        if w is None:
            continue
        new_name = f"{num:0{w}d} {base}"
        if new_name == base:
            continue
        os.rename(path, os.path.join(parent, new_name))
        renamed += 1
    return renamed
