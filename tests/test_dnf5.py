from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from rpmdrop.dnf5 import TransactionResolutionError, resolve_local_rpm


class FakeDBus:
    class Dictionary(dict):
        def __init__(self, value, signature):
            super().__init__(value)
            self.signature = signature

    def __init__(self, result=0, items=None, problems=()):
        self.bus = MagicMock()
        self.session_manager = MagicMock()
        self.session_manager.open_session.return_value = "/session/1"
        self.rpm = MagicMock()
        self.goal = MagicMock()
        self.goal.resolve.return_value = (items or [], result)
        self.goal.get_transaction_problems_string.return_value = problems
        self.interfaces = [
            self.session_manager,
            self.rpm,
            self.goal,
        ]

    def SystemBus(self):
        return self.bus

    def Interface(self, _object, dbus_interface):
        if dbus_interface.endswith("SessionManager"):
            return self.session_manager
        if dbus_interface.endswith("rpm.Rpm"):
            return self.rpm
        return self.goal


def make_package():
    return {
        "name": "example",
        "epoch": "0",
        "version": "2.0",
        "release": "3.fc44",
        "arch": "x86_64",
        "repo_id": "fedora",
        "package_size": 1024,
        "install_size": 4096,
    }


def test_requires_existing_rpm_file(tmp_path: Path):
    with pytest.raises(TransactionResolutionError, match="existing local"):
        resolve_local_rpm(tmp_path / "missing.rpm")


def test_reports_missing_python_dbus(tmp_path: Path):
    rpm = tmp_path / "example.rpm"
    rpm.write_bytes(b"rpm")
    with patch("rpmdrop.dnf5._dbus_module", side_effect=TransactionResolutionError("missing")):
        with pytest.raises(TransactionResolutionError, match="missing"):
            resolve_local_rpm(rpm)


def test_returns_structured_transaction_without_executing(tmp_path: Path):
    rpm_file = tmp_path / "example with spaces.rpm"
    rpm_file.write_bytes(b"rpm")
    fake = FakeDBus(items=[
        ("package", "Install", "User", {}, make_package()),
        ("package", "Install", "Dependency", {}, {
            **make_package(), "name": "dependency", "repo_id": "updates"
        }),
    ])
    with patch("rpmdrop.dnf5._dbus_module", return_value=fake):
        preview = resolve_local_rpm(rpm_file)

    assert [item.name for item in preview.items] == ["example", "dependency"]
    assert preview.items[0].action == "Install"
    assert preview.items[1].reason == "Dependency"
    assert preview.items[0].download_size == 1024
    fake.goal.resolve.assert_called_once()
    assert not hasattr(fake.goal, "do_transaction") or not fake.goal.do_transaction.called


def test_reports_solver_problems(tmp_path: Path):
    rpm_file = tmp_path / "example.rpm"
    rpm_file.write_bytes(b"rpm")
    fake = FakeDBus(result=2, problems=["Unsatisfied dependency: missing-lib"])
    with patch("rpmdrop.dnf5._dbus_module", return_value=fake):
        with pytest.raises(TransactionResolutionError, match="missing-lib"):
            resolve_local_rpm(rpm_file)


def test_preserves_solver_warnings(tmp_path: Path):
    rpm_file = tmp_path / "example.rpm"
    rpm_file.write_bytes(b"rpm")
    fake = FakeDBus(
        result=1,
        items=[("package", "Install", "User", {}, make_package())],
        problems=["A repository warning"],
    )
    with patch("rpmdrop.dnf5._dbus_module", return_value=fake):
        preview = resolve_local_rpm(rpm_file)
    assert preview.warnings == ("A repository warning",)
