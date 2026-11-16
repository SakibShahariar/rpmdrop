import stat
from pathlib import Path

import pytest

from rpmdrop.history import HistoryStore


def test_records_and_lists_recent_operations(tmp_path: Path):
    store = HistoryStore(tmp_path / "data" / "history.sqlite3")
    store.record(
        "success",
        ["Install example-1.0-1.fc44.x86_64", "Install dependency-2.0-1.noarch"],
    )
    store.record("failed", ["Install broken-1.0-1.noarch"], "Missing dependency")

    records = store.list_recent()
    assert len(records) == 2
    assert records[0].status == "failed"
    assert records[0].details == "Missing dependency"
    assert records[1].status == "success"
    assert records[1].packages[0].startswith("Install example")
    assert records[0].created_at.tzinfo is not None


def test_history_is_private_on_posix(tmp_path: Path):
    store = HistoryStore(tmp_path / "private" / "history.sqlite3")
    store.record("success", ["Install example"])
    assert stat.S_IMODE(store.path.stat().st_mode) == 0o600
    assert stat.S_IMODE(store.path.parent.stat().st_mode) == 0o700


def test_history_rejects_unknown_status(tmp_path: Path):
    store = HistoryStore(tmp_path / "history.sqlite3")
    with pytest.raises(ValueError, match="Unsupported operation status"):
        store.record("pending", ["Install example"])


def test_history_is_bounded_to_one_hundred_records(tmp_path: Path):
    store = HistoryStore(tmp_path / "history.sqlite3")
    for index in range(105):
        store.record("success", [f"Install package-{index}"])
    records = store.list_recent(limit=200)
    assert len(records) == 100
    assert records[0].packages == ("Install package-104",)
    assert records[-1].packages == ("Install package-5",)
