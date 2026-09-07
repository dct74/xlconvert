"""Phase 2 tests: folder processors (WPSheet / ControlSheet / IPO).

Uses shared-string xlsx fixtures (xlsx_util) so input matches what real
Excel/WPS writes and what the Swift reference binary can read. Tree shapes
below were verified byte-identical against the Swift build.
"""

from exconverter.processors.control_sheet import ControlSheetProcessor
from exconverter.processors.ipo import IPOTemplateProcessor
from exconverter.processors.wp_sheet import WPSheetProcessor


# --------------------------------------------------------------------------
# WPSheet
# --------------------------------------------------------------------------
def test_wpsheet_builds_tree(shared_xlsx_writer, tmp_path):
    path = shared_xlsx_writer(
        tmp_path / "wp.xlsx",
        {
            "底稿": [
                ["A", "B", "C", "D", "E"],  # header row1
                ["第一部分"],  # row2 section
                ["一、资产"],  # row3 number
                ["资产A", "子项1", "明细x", None, None],  # row4 A-logic
                ["资产B", "子项2", None, None, None],  # row5 A-logic
            ]
        },
    )
    WPSheetProcessor(path).process()
    base = tmp_path / "wp"
    assert (base / "底稿" / "01 第一部分" / "01 一、资产" / "资产A" / "子项1 明细x").is_dir()
    assert (base / "底稿" / "01 第一部分" / "01 一、资产" / "资产B" / "子项2").is_dir()


def test_wpsheet_no_a_logic(shared_xlsx_writer, tmp_path):
    path = shared_xlsx_writer(
        tmp_path / "nob.xlsx",
        {
            "底稿": [
                ["A", "B", "C", "D", "E"],
                ["第一部分"],
                ["一、甲"],
                # A empty -> no-A: lvl4 = B+C, lvl5 = D+E
                [None, "无A项", "说明", "D1", "E1"],
            ]
        },
    )
    WPSheetProcessor(path).process()
    assert (
        tmp_path
        / "nob"
        / "底稿"
        / "01 第一部分"
        / "01 一、甲"
        / "无A项 说明"
        / "D1 E1"
    ).is_dir()


# --------------------------------------------------------------------------
# ControlSheet
# --------------------------------------------------------------------------
def test_control_sheet_column_rule(shared_xlsx_writer, tmp_path):
    path = shared_xlsx_writer(
        tmp_path / "ctl.xlsx",
        {"项目表": [["名称", "编号"], ["项目A", "X001"], ["项目B", "X002"]]},
    )
    csp = ControlSheetProcessor(path, input_fn=lambda: "B")
    csp.process()
    base = tmp_path / "ctl" / "项目表"
    assert (base / "2-X001").is_dir()
    assert (base / "3-X002").is_dir()


def test_control_sheet_enter_skips_subfolders(shared_xlsx_writer, tmp_path):
    path = shared_xlsx_writer(
        tmp_path / "c2.xlsx", {"表1": [["h"], ["数据"]]}
    )
    ControlSheetProcessor(path, input_fn=lambda: "").process()
    assert (tmp_path / "c2" / "表1").is_dir()
    assert not [d for d in (tmp_path / "c2" / "表1").iterdir()]


# --------------------------------------------------------------------------
# IPO
# --------------------------------------------------------------------------
def test_ipo_builds_chapter_subsection_detail(shared_xlsx_writer, tmp_path):
    path = shared_xlsx_writer(
        tmp_path / "某项目IPO项目模板.xlsx",
        {
            "IPO": [
                [None],  # row1
                [None],  # row2
                ["第一章"],  # row3 chapter
                ["第一条", "定义", "本协议含义"],  # row4 subsection+detail
                [None, None, "解释规则"],  # row5 detail
            ]
        },
    )
    IPOTemplateProcessor(path).process()
    base = tmp_path / "某项目IPO项目模板"
    assert (base / "01 第一章").is_dir()
    assert (base / "01 第一章" / "第一条 定义").is_dir()
    assert (base / "01 第一章" / "第一条 定义" / "本协议含义").is_dir()
    assert (base / "01 第一章" / "第一条 定义" / "解释规则").is_dir()


def test_control_sheet_rule_prompt_eof_no_subfolders(shared_xlsx_writer, tmp_path):
    """Regression: EOF at the per-sheet rule prompt skips subfolders (Swift
    `guard let input = readLine() else { break }`), not a crash."""
    from exconverter.processors.control_sheet import ControlSheetProcessor

    path = shared_xlsx_writer(
        tmp_path / "c_eof.xlsx",
        {"项目表": [["名称", "编号"], ["项目A", "X001"]]},
    )

    def _eof():
        raise EOFError

    ControlSheetProcessor(path, input_fn=_eof).process()
    base = tmp_path / "c_eof" / "项目表"
    assert base.is_dir()
    # no numbered subfolder was created (rule loop broke on EOF)
    assert not [d for d in base.iterdir() if d.is_dir()]
