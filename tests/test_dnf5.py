import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from rpmdrop.dnf5 import TransactionResolutionError, resolve_local_rpm


def test_requires_existing_rpm_file(tmp_path: Path):
    with pytest.raises(TransactionResolutionError, match="existing local"):
        resolve_local_rpm(tmp_path / "missing.rpm")


@patch("rpmdrop.dnf5.shutil.which", return_value=None)
def test_reports_missing_dnf5(_which, tmp_path: Path):
    rpm = tmp_path / "package.rpm"
    rpm.write_bytes(b"rpm")
    with pytest.raises(TransactionResolutionError, match="DNF5 was not found"):
        resolve_local_rpm(rpm)


@patch("rpmdrop.dnf5.shutil.which", return_value="/usr/bin/dnf5")
@patch("rpmdrop.dnf5.subprocess.run")
def test_resolves_without_confirming_install(mock_run, _which, tmp_path: Path):
    rpm = tmp_path / "package with spaces.rpm"
    rpm.write_bytes(b"rpm")
    mock_run.return_value = subprocess.CompletedProcess(
        [], 1, "Install  package-1-1.x86_64\nOperation aborted.", ""
    )

    preview = resolve_local_rpm(rpm)

    assert preview.package_path == rpm.resolve()
    assert preview.command[:3] == ("/usr/bin/dnf5", "--assumeno", "install")
    assert preview.command[-1] == str(rpm.resolve())
    assert "--" in preview.command
    mock_run.assert_called_once()
    assert mock_run.call_args.kwargs["check"] is False
    assert mock_run.call_args.kwargs["env"]["LC_ALL"] == "C"


@patch("rpmdrop.dnf5.shutil.which", return_value="/usr/bin/dnf5")
@patch("rpmdrop.dnf5.subprocess.run")
def test_reports_solver_errors(mock_run, _which, tmp_path: Path):
    rpm = tmp_path / "package.rpm"
    rpm.write_bytes(b"rpm")
    mock_run.return_value = subprocess.CompletedProcess(
        [], 1, "", "Error: Unable to find a match"
    )
    with pytest.raises(TransactionResolutionError, match="Unable to find a match"):
        resolve_local_rpm(rpm)


@patch("rpmdrop.dnf5.shutil.which", return_value="/usr/bin/dnf5")
@patch("rpmdrop.dnf5.subprocess.run")
def test_reports_timeout(mock_run, _which, tmp_path: Path):
    rpm = tmp_path / "package.rpm"
    rpm.write_bytes(b"rpm")
    mock_run.side_effect = subprocess.TimeoutExpired(["dnf5"], 180)
    with pytest.raises(TransactionResolutionError, match="timed out"):
        resolve_local_rpm(rpm)
