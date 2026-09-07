"""Tests for sequence_prefix (Chinese-ordinal -> numeric prefix enhancement)."""

import os

from exconverter.sequence_prefix import (
    _strip_ordinal_prefix,
    add_sequence_prefix,
    chinese_number_to_int,
)


def test_chinese_number_to_int():
    cases = {
        "一": 1, "三": 3, "九": 9, "十": 10, "十一": 11, "十九": 19,
        "二十": 20, "二十三": 23, "九十九": 99, "一百": 100,
    }
    for cn, val in cases.items():
        assert chinese_number_to_int(cn) == val
    # unsupported
    assert chinese_number_to_int("一百零五") is None
    assert chinese_number_to_int("") is None
    assert chinese_number_to_int("零") is None
    assert chinese_number_to_int("abc") is None


def test_strip_ordinal_prefix():
    assert _strip_ordinal_prefix("第一章 发行人") == ("ord_第章", 1)
    assert _strip_ordinal_prefix("第二部分 记录") == ("ord_第部分", 2)
    assert _strip_ordinal_prefix("一、本次发行") == ("ord_、", 1)
    assert _strip_ordinal_prefix("十一、项K") == ("ord_、", 11)
    # not ordinals
    assert _strip_ordinal_prefix("第X部分") is None
    assert _strip_ordinal_prefix("普通名") is None
    assert _strip_ordinal_prefix("资产A") is None


def _make_tree(root, paths):
    for p in paths:
        os.makedirs(os.path.join(root, p), exist_ok=True)


def test_add_sequence_prefix_basic(tmp_path):
    _make_tree(
        str(tmp_path),
        ["第一章 甲", "第二章 乙", "第十一章 戊", "普通目录"],
    )
    n = add_sequence_prefix(str(tmp_path))
    assert n == 3
    names = sorted(os.listdir(tmp_path))
    assert names == ["01 第一章 甲", "02 第二章 乙", "11 第十一章 戊", "普通目录"]


def test_add_sequence_prefix_nested_per_parent(tmp_path):
    _make_tree(
        str(tmp_path),
        [
            "第一部分 A",
            "第二部分 B",
            "第一部分 A/一、x",
            "第一部分 A/二、y",
            "第一部分 A/十一、z",
        ],
    )
    n = add_sequence_prefix(str(tmp_path))
    assert n == 5
    # part and item families sized independently
    parts = sorted(
        os.listdir(tmp_path)
    )
    assert parts == ["01 第一部分 A", "02 第二部分 B"]
    items = sorted(os.listdir(tmp_path / "01 第一部分 A"))
    assert items == ["01 一、x", "02 二、y", "11 十一、z"]


def test_chapter_and_part_distinct_sequences(tmp_path):
    # 第X章 vs 第X部分 in same dir must NOT share numbers
    _make_tree(
        str(tmp_path),
        ["第一章 A", "第二章 B", "第一部分 X", "第二部分 Y"],
    )
    add_sequence_prefix(str(tmp_path))
    names = sorted(os.listdir(tmp_path))
    # chapters: 01,02 ; parts: 01,02 (separate families, same prefix ok)
    assert names == ["01 第一章 A", "01 第一部分 X", "02 第二章 B", "02 第二部分 Y"]


def test_add_sequence_prefix_wider_than_two(tmp_path):
    _make_tree(str(tmp_path), ["第一部分 A", "第二十三部分 Z"])
    add_sequence_prefix(str(tmp_path))
    names = sorted(os.listdir(tmp_path))
    # max ordinal 23 -> width 2 -> 01, 23
    assert names == ["01 第一部分 A", "23 第二十三部分 Z"]
