"""Tests for review fixes in state.py and EOF handling in rename."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
from exconverter.state import RenameStateManager


def _make_manager(history_json: str) -> RenameStateManager:
    sm = RenameStateManager.__new__(RenameStateManager)
    sm.history_file_url = "/tmp/exconverter_test_history_probe.json"
    if os.path.exists(sm.history_file_url):
        os.remove(sm.history_file_url)
    with open(sm.history_file_url, "w", encoding="utf-8") as f:
        f.write(history_json)
    sm._rename_history: list = []
    sm._backup_directory = None
    return sm


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    p = "/tmp/exconverter_test_history_probe.json"
    if os.path.exists(p):
        os.remove(p)


def test_empty_history_loads_cleanly(capsys):
    """Regression: an empty '[]' history file must load as empty without
    being treated as a version mismatch (Swift allSatisfy on [] is true)."""
    sm = _make_manager("[]")
    sm._load_history()
    assert sm._rename_history == []
    assert os.path.exists(sm.history_file_url)
    assert "version mismatch" not in capsys.readouterr().out


def test_version_mismatch_wipes_file(capsys):
    sm = _make_manager('[{"version": 99, "operations": [], "backupDirName": "x"}]')
    sm._load_history()
    assert sm._rename_history == []
    assert not os.path.exists(sm.history_file_url)
    assert "version mismatch" in capsys.readouterr().out


def test_valid_history_loads():
    payload = json.dumps(
        [
            {
                "version": 1,
                "operations": [
                    {
                        "oldRelativePath": "a.txt",
                        "newRelativePath": "b.txt",
                        "relativeBackupPath": "a.txt",
                        "status": "success",
                        "errorMessage": None,
                        "isRestored": False,
                    }
                ],
                "backupDirName": "台账_backup_",
            }
        ]
    )
    sm = _make_manager(payload)
    sm._load_history()
    assert len(sm._rename_history) == 1
    batch = sm._rename_history[0]
    assert batch.backup_dir_name == "台账_backup_"
    assert batch.operations[0].old_relative_path == "a.txt"
    assert batch.operations[0].status.value == "success"


def test_corrupt_history_wipes_file(capsys):
    sm = _make_manager("{not valid json")
    sm._load_history()
    assert sm._rename_history == []
    assert not os.path.exists(sm.history_file_url)
