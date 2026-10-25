import pytest
from PySide6.QtCore import Qt

from process_model import COLUMNS, CPU_COLUMN, SORT_ROLE, STATUS_COLUMN, ProcessModel


def proc(pid, **values):
    row = {"pid": pid, "name": f"proc{pid}", "username": "kali", "cpu_percent": 0.0,
           "memory_percent": 0.0, "rss": 0, "threads": 1, "status": "sleeping",
           "cmdline": "", "create_time": 1.0}
    return {**row, **values}


def pids(model):
    return [model.row_at(row)["pid"] for row in range(model.rowCount())]


def cell(model, row, key, role=Qt.DisplayRole):
    column = [k for _, k in COLUMNS].index(key)
    return model.data(model.index(row, column), role)


@pytest.fixture
def model(qapp):
    return ProcessModel()


def test_headers_are_in_english(model):
    headers = [model.headerData(i, Qt.Horizontal) for i in range(model.columnCount())]
    assert headers == ["PID", "Name", "User", "CPU %", "Memory", "RAM %", "Threads", "Status", "Command"]
    assert headers[CPU_COLUMN] == "CPU %"
    assert headers[STATUS_COLUMN] == "Status"


def test_update_adds_new_processes(model):
    model.update([proc(1)])
    model.update([proc(1), proc(2)])
    assert pids(model) == [1, 2]


def test_update_removes_exited_processes(model):
    model.update([proc(1), proc(2), proc(3)])
    model.update([proc(1), proc(3)])
    assert pids(model) == [1, 3]


def test_update_keeps_existing_rows_in_place(model):
    """Rows must not move on refresh, otherwise the selection and scroll position jump."""
    model.update([proc(1), proc(2)])
    model.update([proc(2, cpu_percent=50.0), proc(1)])
    assert pids(model) == [1, 2]
    assert cell(model, 1, "cpu_percent") == "50.0"


def test_display_formatting(model):
    model.update([proc(7, rss=1536, cpu_percent=12.34, status="disk-sleep")])
    assert cell(model, 0, "rss") == "1.5 KB"
    assert cell(model, 0, "cpu_percent") == "12.3"
    assert cell(model, 0, "status") == "I/O wait"


def test_unknown_status_is_shown_as_is(model):
    model.update([proc(7, status="something-new")])
    assert cell(model, 0, "status") == "something-new"


def test_sort_role_returns_raw_values(model):
    """Sorting must use numbers, not formatted text ("9.0 KB" would sort after "10.0 KB")."""
    model.update([proc(7, rss=1536, status="disk-sleep")])
    assert cell(model, 0, "rss", SORT_ROLE) == 1536
    assert cell(model, 0, "status", SORT_ROLE) == "disk-sleep"


def test_command_tooltip_only_when_there_is_a_command(model):
    model.update([proc(1, cmdline="python main.py"), proc(2, cmdline="")])
    assert cell(model, 0, "cmdline", Qt.ToolTipRole) == "python main.py"
    assert cell(model, 1, "cmdline", Qt.ToolTipRole) is None
