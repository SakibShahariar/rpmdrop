from pathlib import Path
from unittest.mock import patch
import subprocess

import pytest

from rpmdrop.package import PackageInspectionError, inspect_package


def test_rejects_non_rpm_extension(tmp_path: Path):
    file_path = tmp_path / "notes.txt"
    file_path.write_text("not an rpm")
    with pytest.raises(PackageInspectionError, match="does not have"):
        inspect_package(file_path)


def test_rejects_missing_file(tmp_path: Path):
    with pytest.raises(PackageInspectionError, match="does not exist"):
        inspect_package(tmp_path / "missing.rpm")


@patch("rpmdrop.package.shutil.which", return_value="/usr/bin/rpm")
@patch("rpmdrop.package._run")
def test_parses_package_metadata(mock_run, _which, tmp_path: Path):
    rpm_file = tmp_path / "sample.rpm"
    rpm_file.write_bytes(b"test fixture")
    metadata = "\x1f".join(["sample", "1.2.3", "4.fc44", "x86_64", "A sample package",
        "A longer description.\nWith multiple lines.", "Example Vendor", "Example Packager", "MIT"])
    mock_run.return_value = subprocess.CompletedProcess([], 0, metadata, "")
    with patch("rpmdrop.package.inspect_signature", return_value="Digest/signature check passed"):
        info = inspect_package(rpm_file)
    assert info.name == "sample"
    assert info.version == "1.2.3"
    assert info.architecture == "x86_64"
    assert "multiple lines" in info.description


@patch("rpmdrop.package.shutil.which", return_value="/usr/bin/rpm")
@patch("rpmdrop.package._run")
def test_reports_rpm_query_errors(mock_run, _which, tmp_path: Path):
    rpm_file = tmp_path / "broken.rpm"
    rpm_file.write_bytes(b"broken")
    mock_run.return_value = subprocess.CompletedProcess([], 1, "", "not an rpm")
    with pytest.raises(PackageInspectionError, match="not an rpm"):
        inspect_package(rpm_file)
