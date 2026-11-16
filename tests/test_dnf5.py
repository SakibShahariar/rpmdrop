from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from rpmdrop.dnf5 import (
    TransactionExecutionError,
    TransactionPreview,
    TransactionResolutionError,
    cancel_transaction,
    close_session,
    classify_transaction_error,
    execute_transaction,
    resolve_local_rpm,
)


class FakeDBus:
    DBusException = RuntimeError
    ObjectPath = str

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
    with (
        patch("rpmdrop.dnf5._dbus_module", side_effect=TransactionResolutionError("missing")),
        pytest.raises(TransactionResolutionError, match="missing"),
    ):
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
    assert fake.goal.resolve.call_args.args[0]["allow_erasing"] is True
    assert not hasattr(fake.goal, "do_transaction") or not fake.goal.do_transaction.called


def test_reports_missing_dnf5_daemon(tmp_path: Path):
    rpm_file = tmp_path / "example.rpm"
    rpm_file.write_bytes(b"rpm")
    fake = FakeDBus()
    fake.bus.get_object.side_effect = RuntimeError("ServiceUnknown")
    with (
        patch("rpmdrop.dnf5._dbus_module", return_value=fake),
        pytest.raises(TransactionResolutionError, match="dnf5daemon-server"),
    ):
        resolve_local_rpm(rpm_file)


def test_reports_solver_problems(tmp_path: Path):
    rpm_file = tmp_path / "example.rpm"
    rpm_file.write_bytes(b"rpm")
    fake = FakeDBus(result=2, problems=["Unsatisfied dependency: missing-lib"])
    with (
        patch("rpmdrop.dnf5._dbus_module", return_value=fake),
        pytest.raises(TransactionResolutionError, match="missing-lib"),
    ):
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



def test_executes_only_after_revalidating_preview(tmp_path: Path):
    rpm_file = tmp_path / "example.rpm"
    rpm_file.write_bytes(b"rpm")
    fake = FakeDBus(items=[("package", "Install", "User", {}, make_package())])
    with patch("rpmdrop.dnf5._dbus_module", return_value=fake):
        preview = resolve_local_rpm(rpm_file)
        execute_transaction(preview)

    assert preview.session_path == "/session/1"
    assert fake.goal.resolve.call_count == 2
    assert all(
        call.args[0]["allow_erasing"] is True
        for call in fake.goal.resolve.call_args_list
    )
    fake.goal.do_transaction.assert_called_once()


def test_refuses_execution_when_transaction_changed(tmp_path: Path):
    rpm_file = tmp_path / "example.rpm"
    rpm_file.write_bytes(b"rpm")
    initial = [("package", "Install", "User", {}, make_package())]
    changed_package = {**make_package(), "version": "9.9"}
    fake = FakeDBus(items=initial)
    fake.goal.resolve.side_effect = [
        (initial, 0),
        ([("package", "Install", "User", {}, changed_package)], 0),
    ]
    with patch("rpmdrop.dnf5._dbus_module", return_value=fake):
        preview = resolve_local_rpm(rpm_file)
        with pytest.raises(TransactionExecutionError, match="transaction changed"):
            execute_transaction(preview)
    fake.goal.do_transaction.assert_not_called()


def test_cancel_requests_dnf5_goal_cancellation(tmp_path: Path):
    rpm_file = tmp_path / "example.rpm"
    rpm_file.write_bytes(b"rpm")
    fake = FakeDBus(items=[("package", "Install", "User", {}, make_package())])
    fake.goal.cancel.return_value = (True, "")
    with patch("rpmdrop.dnf5._dbus_module", return_value=fake):
        preview = resolve_local_rpm(rpm_file)
        result = cancel_transaction(preview)
    assert result == (True, "")


def test_reports_dnf5_progress_fraction(tmp_path: Path):
    rpm_file = tmp_path / "example.rpm"
    rpm_file.write_bytes(b"rpm")
    fake = FakeDBus(items=[("package", "Install", "User", {}, make_package())])
    progress = []
    with patch("rpmdrop.dnf5._dbus_module", return_value=fake):
        preview = resolve_local_rpm(rpm_file)
        execute_transaction(
            preview,
            progress_callback=lambda message, fraction: progress.append((message, fraction)),
        )

    handlers = [
        entry.args[0] for entry in fake.bus.add_signal_receiver.call_args_list
    ]
    handlers[0]("/session/1", "example-2.0-3.fc44.x86_64", 2, 4)
    assert progress == [("Preparing example-2.0-3.fc44.x86_64 (2/4)", 0.5)]


def test_refuses_execution_when_dnf5_warnings_change(tmp_path: Path):
    rpm_file = tmp_path / "example.rpm"
    rpm_file.write_bytes(b"rpm")
    items = [("package", "Install", "User", {}, make_package())]
    fake = FakeDBus(items=items)
    fake.goal.resolve.side_effect = [(items, 0), (items, 1)]
    fake.goal.get_transaction_problems_string.return_value = ["New repository warning"]
    with patch("rpmdrop.dnf5._dbus_module", return_value=fake):
        preview = resolve_local_rpm(rpm_file)
        with pytest.raises(TransactionExecutionError, match="warnings changed"):
            execute_transaction(preview)
    fake.goal.do_transaction.assert_not_called()


def test_reports_failed_rpm_transaction_completion(tmp_path: Path):
    rpm_file = tmp_path / "example.rpm"
    rpm_file.write_bytes(b"rpm")
    fake = FakeDBus(items=[("package", "Install", "User", {}, make_package())])

    def fail_transaction(*_args, **_kwargs):
        completed = fake.bus.add_signal_receiver.call_args_list[-1].args[0]
        completed("/session/1", False)

    fake.goal.do_transaction.side_effect = fail_transaction
    with (
        patch("rpmdrop.dnf5._dbus_module", return_value=fake),
        pytest.raises(TransactionExecutionError, match="did not complete"),
    ):
        preview = resolve_local_rpm(rpm_file)
        execute_transaction(preview, progress_callback=lambda _message, _fraction: None)



def test_closes_dnf5_session(tmp_path: Path):
    rpm_file = tmp_path / "example.rpm"
    rpm_file.write_bytes(b"rpm")
    fake = FakeDBus(items=[("package", "Install", "User", {}, make_package())])
    fake.session_manager.close_session.return_value = True
    with patch("rpmdrop.dnf5._dbus_module", return_value=fake):
        preview = resolve_local_rpm(rpm_file)
        assert close_session(preview) is True
    fake.session_manager.close_session.assert_called_once_with("/session/1")


def test_reports_download_byte_progress(tmp_path: Path):
    rpm_file = tmp_path / "example.rpm"
    rpm_file.write_bytes(b"rpm")
    fake = FakeDBus(items=[("package", "Install", "User", {}, make_package())])
    progress = []
    with patch("rpmdrop.dnf5._dbus_module", return_value=fake):
        preview = resolve_local_rpm(rpm_file)
        execute_transaction(
            preview,
            progress_callback=lambda message, fraction: progress.append((message, fraction)),
        )
    download_receiver = next(
        entry for entry in fake.bus.add_signal_receiver.call_args_list
        if entry.kwargs.get("signal_name") == "download_progress"
    )
    assert download_receiver.kwargs["dbus_interface"] == "org.rpm.dnf.v0.Base"
    download_handler = download_receiver.args[0]
    download_handler("/session/1", "example.rpm", 100, 50)
    assert progress == [("Downloading example.rpm (50/100 bytes)", 0.5)]


def test_empty_preview_cannot_be_executed():
    preview = TransactionPreview(
        package_path=Path("/tmp/empty.rpm"),
        items=(),
        warnings=("No package changes",),
        session_path="/session/1",
    )
    with pytest.raises(TransactionExecutionError, match="no package changes"):
        execute_transaction(preview)



@pytest.mark.parametrize(
    ("message", "expected_category"),
    [
        ("NotAuthorized: PolicyKit denied request", "authorization"),
        ("No space left on device", "disk-space"),
        ("Could not resolve host mirror.example", "network"),
        ("Failed to download repomd.xml", "network"),
        ("No enabled repositories", "repository"),
        ("File conflicts with an existing package", "package-conflict"),
        ("Nothing provides libexample.so.1", "dependency"),
        ("Unexpected daemon error", "generic"),
    ],
)
def test_classifies_transaction_failures(message, expected_category):
    category, title, explanation = classify_transaction_error(message)
    assert category == expected_category
    assert title
    assert explanation
