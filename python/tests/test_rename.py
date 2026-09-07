"""Phase 3 tests: file rename + undo (FileRenameProcessor).

NOTE: history files persist in the system temp dir keyed by the Excel file
basename. Tests must use unique Excel filenames (or clean up) so a stale
history from an earlier run is not loaded.
"""

import os
import sys

from exconverter.processors.rename import FileRenameProcessor
from exconverter.state import RenameStateManager

sys.path.insert(0, os.path.dirname(__file__))


def _run_rename(tmp_path, filename, grid, files, sort_answer="n"):
    excel = tmp_path / filename
    from xlsx_util import write_shared_string_xlsx

    write_shared_string_xlsx(str(excel), grid)
    stem = os.path.splitext(filename)[0]
    # files live under <exceldir>/<stem>/<sheet>/  (or just under excel dir)
    return excel, stem


def test_rename_and_undo_roundtrip(shared_xlsx_writer, tmp_path, monkeypatch):
    filename = "rename_roundtrip_test.xlsx"
    excel = shared_xlsx_writer(
        tmp_path / filename,
        {
            "合同清单": [
                ["序号", "合同名称", "金额"],
                ["", "合同A", "100"],
                ["", "合同B", "200"],
            ]
        },
    )
    folder = tmp_path / "rename_roundtrip_test" / "合同清单"
    folder.mkdir(parents=True)
    (folder / "2-AB.txt").write_text("x")
    (folder / "3-AB.txt").write_text("y")

    co = RenameStateManager(excel)
    p = FileRenameProcessor(excel, coordinator=co, input_fn=lambda: "n")
    p.process()

    renamed = sorted(os.listdir(folder))
    assert renamed == ["序号-合同名称.txt", "序号-合同名称_1.txt"]
    # Backup dir must exist with hard-linked originals.
    backup_dirs = [x for x in os.listdir(tmp_path) if x.endswith("_backup_")]
    assert backup_dirs

    # Undo restores original names.
    p.undo_last_batch()
    assert sorted(os.listdir(folder)) == ["2-AB.txt", "3-AB.txt"]


def test_rename_no_files_warns(shared_xlsx_writer, tmp_path, capsys):
    filename = "no_files_rename.xlsx"
    excel = shared_xlsx_writer(tmp_path / filename, {"S": [["序号"], ["a"]]})
    co = RenameStateManager(excel)
    p = FileRenameProcessor(excel, coordinator=co, input_fn=lambda: "n")
    p.process()
    out = capsys.readouterr().out
    assert "No files found to rename." in out


def test_undo_empty_history(shared_xlsx_writer, tmp_path, capsys):
    filename = "empty_hist_undo.xlsx"
    excel = shared_xlsx_writer(tmp_path / filename, {"S": [["序号"], ["a"]]})
    co = RenameStateManager(excel)
    p = FileRenameProcessor(excel, coordinator=co, input_fn=lambda: "n")
    p.undo_last_batch()
    out = capsys.readouterr().out
    assert "Nothing to undo." in out


def test_rename_custom_sort(shared_xlsx_writer, tmp_path):
    filename = "rename_custom_sort.xlsx"
    excel = shared_xlsx_writer(
        tmp_path / filename,
        {
            "合同清单": [
                ["序号", "合同名称", "金额"],
                ["", "合同A", "100"],
                ["", "合同B", "200"],
                ["", "合同C", "50"],
            ]
        },
    )
    folder = tmp_path / "rename_custom_sort" / "合同清单"
    folder.mkdir(parents=True)
    for row in ["2-AB", "3-AB", "4-AB"]:
        (folder / f"{row}.txt").write_text("x")
    answers = iter(["y", "C"])
    co = RenameStateManager(excel)
    p = FileRenameProcessor(excel, coordinator=co, input_fn=lambda: next(answers))
    p.process()
    # sort by C (金额: 50,100,200) -> row4,#2,#3 ordering
    assert sorted(os.listdir(folder)) == [
        "1-序号-合同名称.txt",
        "2-序号-合同名称.txt",
        "3-序号-合同名称.txt",
    ]


def test_rename_sort_prompt_eof_is_no_sort(shared_xlsx_writer, tmp_path, capsys):
    """Regression: EOF at the y/n sort prompt must not raise; treated as 'n'."""
    filename = "rename_eof_sort.xlsx"
    excel = shared_xlsx_writer(
        tmp_path / filename,
        {"S": [["序号", "名称"], ["", "合同A"], ["", "合同B"]]},
    )
    folder = tmp_path / "rename_eof_sort" / "S"
    folder.mkdir(parents=True)
    (folder / "2-AB.txt").write_text("x")

    def _eof():
        raise EOFError

    co = RenameStateManager(excel)
    p = FileRenameProcessor(excel, coordinator=co, input_fn=_eof)
    p.process()  # must not raise; EOF -> no sort
    assert sorted(os.listdir(folder)) == ["序号-名称.txt"]


def test_ask_sort_column_eof_returns_none(shared_xlsx_writer, tmp_path):
    """Regression: EOF while choosing the sort column returns None gracefully."""
    filename = "rename_eof_col.xlsx"
    excel = shared_xlsx_writer(
        tmp_path / filename,
        {"S": [["序号", "名称"], ["", "合同A"], ["", "合同B"]]},
    )
    from exconverter import excel_parser
    from exconverter.excel_parser import open_workbook

    wb = open_workbook(excel)
    try:
        ctx = excel_parser.read_excel_to_grid(excel, "S", workbook=wb)
    finally:
        wb.close()

    def _eof():
        raise EOFError

    co = RenameStateManager(excel)
    p = FileRenameProcessor(excel, coordinator=co, input_fn=_eof)
    assert p._ask_sort_column(ctx, "S") is None
