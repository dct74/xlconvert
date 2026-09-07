"""Phase 4 tests: CLI entry point (console_io + cli menu flow)."""

import os

import pytest

from exconverter import cli, console_io


def test_is_ipo_template():
    assert console_io.is_ipo_template("某IPO项目模板.xlsx") is True
    assert console_io.is_ipo_template("/x/某IPO项目模板.xlsx") is True
    assert console_io.is_ipo_template("普通底稿.xlsx") is False
    assert console_io.is_ipo_template("ipo项目模板-其他.xlsx") is True


def test_get_excel_file_explicit(shared_xlsx_writer, tmp_path, capsys):
    path = shared_xlsx_writer(tmp_path / "a.xlsx", {"S": [["序号"]]})
    got = console_io.get_excel_file(input_fn=lambda: f"'{path}'")
    assert got is not None
    assert os.path.basename(got) == "a.xlsx"


def test_get_excel_file_not_found(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)  # empty dir, no xlsx
    got = console_io.get_excel_file(input_fn=lambda: "")
    assert got is None
    assert "No Excel file found." in capsys.readouterr().out


def test_get_excel_file_cwd_search(shared_xlsx_writer, tmp_path, monkeypatch):
    shared_xlsx_writer(tmp_path / "s.xlsx", {"S": [["序号"]]})
    monkeypatch.chdir(tmp_path)
    got = console_io.get_excel_file(input_fn=lambda: "")  # Enter -> search cwd
    assert got is not None
    assert os.path.basename(got) == "s.xlsx"


def test_ipo_autodetect_flow(shared_xlsx_writer, tmp_path, monkeypatch):
    """IPO template is processed without the menu, then the program exits."""
    path = shared_xlsx_writer(
        tmp_path / "IPO项目模板.xlsx",
        {"IPO": [[None], [None], ["第一章"], ["第一条", "定义", "含义"]]},
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", lambda: path)
    with pytest.raises(SystemExit) as e:
        cli.main()
    assert e.value.code == 0
    assert (tmp_path / "IPO项目模板" / "01 第一章" / "第一条 定义").is_dir()


def test_menu_wpsheet_then_exit(shared_xlsx_writer, tmp_path, monkeypatch, capsys):
    path = shared_xlsx_writer(
        tmp_path / "底稿.xlsx",
        {"底稿": [["A"], ["第一部分"], ["一、甲"], ["数据A"]]},
    )
    monkeypatch.chdir(tmp_path)
    answers = iter([path, "1"])
    monkeypatch.setattr("builtins.input", lambda: next(answers))
    # Menu WPSheet path completes then returns normally (no sys.exit).
    cli.main()
    out = capsys.readouterr().out
    assert "WPSheet processing completed successfully" in out
    assert (tmp_path / "底稿" / "底稿" / "01 第一部分").is_dir()


# --- Regression tests for review fixes -----------------------------------

def test_get_excel_file_eof_returns_none(capsys):
    """EOF at the drag prompt behaves like Swift readLine()==nil (no crash,
    silent None)."""
    def _eof():
        raise EOFError

    assert console_io.get_excel_file(input_fn=_eof) is None
    assert "No Excel file found." not in capsys.readouterr().out


def test_safe_read_line_eof_returns_none():
    def _eof():
        raise EOFError

    assert console_io.safe_read_line(_eof) is None
    assert console_io.safe_read_line(lambda: "hi") == "hi"


def test_show_menu_eof_returns_quit(capsys):
    """EOF at the menu prints 'EOF detected' and returns 'q' (Swift parity)."""
    def _eof():
        raise EOFError

    assert cli.show_menu(_eof) == "q"
    assert "EOF detected, exiting." in capsys.readouterr().out


def test_show_menu_invalid_then_valid(capsys):
    """Empty/invalid lines keep prompting; only valid choices return."""
    answers = iter(["", "x", "9", "2"])
    assert cli.show_menu(lambda: next(answers)) == "2"
    out = capsys.readouterr().out
    assert out.count("Invalid option. Please try again.") == 3


def test_main_eof_stdin_exits_zero(shared_xlsx_writer, tmp_path, monkeypatch, capsys):
    """Empty stdin must not print a Python traceback; ends quietly (exit 0,
    mirroring Swift where no file selection runs nothing)."""
    monkeypatch.chdir(tmp_path)

    def _eof():
        raise EOFError

    monkeypatch.setattr("builtins.input", _eof)
    cli.main()  # returns normally instead of raising SystemExit
    assert "Traceback" not in capsys.readouterr().out


def test_backup_delete_prompt_eof_preserves(shared_xlsx_writer, tmp_path, monkeypatch, capsys):
    """EOF at 'Delete backup directory?' keeps the backup (default n)."""
    path = shared_xlsx_writer(
        tmp_path / "保.xlsx", {"S": [["序号"], ["数据"]]}
    )
    backup = tmp_path / "保_backup_"
    backup.mkdir()
    (backup / "x.txt").write_text("dummy")

    monkeypatch.chdir(tmp_path)
    answers = iter([path, "q"])

    def _in():
        try:
            return next(answers)
        except StopIteration:
            raise EOFError

    monkeypatch.setattr("builtins.input", _in)
    cli.main()
    assert backup.is_dir()
    assert "Backup directory preserved" in capsys.readouterr().out


def test_backup_delete_prompt_yes_deletes(shared_xlsx_writer, tmp_path, monkeypatch, capsys):
    path = shared_xlsx_writer(
        tmp_path / "删.xlsx", {"S": [["序号"], ["数据"]]}
    )
    backup = tmp_path / "删_backup_"
    backup.mkdir()
    (backup / "x.txt").write_text("dummy")

    monkeypatch.chdir(tmp_path)
    answers = iter([path, "q", "y"])
    monkeypatch.setattr("builtins.input", lambda: next(answers))
    cli.main()
    assert not backup.exists()
    assert "Backup directory deleted." in capsys.readouterr().out
