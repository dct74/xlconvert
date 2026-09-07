"""Smoke tests for phase-0 pure modules."""

from exconverter import config, excel_columns, string_transform


def test_excel_columns_letter():
    assert excel_columns.letter(0) == "A"
    assert excel_columns.letter(25) == "Z"
    assert excel_columns.letter(26) is None
    assert excel_columns.letter(-1) is None


def test_excel_columns_index():
    assert excel_columns.index("A") == 0
    assert excel_columns.index("z") == 25
    assert excel_columns.index("a") == 0
    assert excel_columns.index("AA") is None  # out of 26-col cap
    assert excel_columns.index("0") is None
    assert excel_columns.index("") is None


def test_sanitize_basic():
    assert string_transform.sanitize("  abc  ") == "abc"
    assert string_transform.sanitize(None) == ""
    assert string_transform.sanitize("   ") == ""
    assert string_transform.sanitize("a<b>:c/\\|?*") == "abc"
    assert string_transform.sanitize("a b") == "a b"


def test_sanitize_reserved_windows_names():
    assert string_transform.sanitize("CON") == "_CON_"
    assert string_transform.sanitize("con.txt") == "_con.txt_"
    assert string_transform.sanitize("COM1") == "_COM1_"
    assert string_transform.sanitize("com10") == "com10"
    assert string_transform.sanitize("LPT9") == "_LPT9_"
    assert string_transform.sanitize("aux") == "_aux_"


def test_safe_utf8_truncate_byte_budget():
    # "中" is 3 UTF-8 bytes, so budget 4 fits both; budget 3 truncates to "中".
    assert string_transform.safe_utf8_truncate("中a", 4) == "中a"
    assert string_transform.safe_utf8_truncate("中a", 3) == "中"
    assert string_transform.safe_utf8_truncate("abc", 10) == "abc"
    assert string_transform.safe_utf8_truncate("abcde", 3) == "abc"


def test_truncate_path_component_keeps_ext():
    val, truncated = string_transform.truncate_path_component("a" * 200 + ".txt", 50)
    assert truncated is True
    assert val.endswith(".txt")
    assert len(val.encode("utf-8")) <= 50


def test_format_date_chinese():
    assert string_transform.format_date_string("2026年1月15日") == "20260115"
    assert string_transform.format_date_string("2026年01月5日") == "20260105"


def test_format_date_separator():
    assert string_transform.format_date_string("2026-1-15") == "20260115"
    assert string_transform.format_date_string("2026/1/15 12:30:45") == "20260115"
    assert string_transform.format_date_string("1-15-2026") == "20260115"
    assert string_transform.format_date_string("15-1-2026") == "20260115"


def test_format_date_8digit_and_digits():
    assert string_transform.format_date_string("20260115") == "20260115"
    assert string_transform.format_date_string("46037") == "46037"
    assert string_transform.format_date_string("abc") == "abc"


def test_config_regexes_compile():
    # Sanity: config regexes are valid and match expected forms.
    assert config.Regex.chinese_section.match("第一部分内容") is not None
    assert config.Regex.chinese_number.match("一二、条目") is not None
    assert config.Regex.single_letter.fullmatch("B") is not None
    assert config.Regex.row_col.fullmatch("3-B") is not None
    assert config.Regex.folder_name_pattern.fullmatch("12-项目A")
    assert config.Regex.letters_only.fullmatch("AB") is not None
    assert config.Regex.eight_digit.fullmatch("20260115") is not None


def test_console_display_width_cjk_emoji():
    """Console width: ASCII=1, CJK=2, emoji presentation=2."""
    from exconverter import console

    assert console.display_width(of="abc") == 3
    assert console.display_width(of="底稿") == 4
    assert console.display_width(of="一、项") == 6  # 、 is wide (CJK punct)
    # emoji (🙂 U+1F642 in the 1F600-1FAFF presentation block) counts as 2
    assert console.display_width(of="\U0001F642") == 2
