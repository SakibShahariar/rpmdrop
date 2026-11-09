import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from rpmdrop.package import PackageInspectionError, inspect_package, inspect_signature


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
    metadata = "sample\\x1f1.2.3\\x1f4.fc44\\x1fx86_64\\x1fA sample package\\x1fA longer description.\\nWith multiple lines.\\x1fExample Vendor\\x1fExample Packager\\x1fMIT"
    mock_run.return_value = subprocess.CompletedProcess([], 0, metadata, "")
    with patch("rpmdrop.package.inspect_signature", return_value="Signature OK"):
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


@patch("rpmdrop.package.shutil.which", return_value="/usr/bin/rpmkeys")
@patch("rpmdrop.package._run")
def test_unsigned_package_is_not_reported_as_signature_verified(mock_run, _which, tmp_path):
    mock_run.return_value = subprocess.CompletedProcess([], 0, "digests OK", "")
    result = inspect_signature(tmp_path / "unsigned.rpm")
    assert "no trusted signature was confirmed" in result


@patch("rpmdrop.package.shutil.which", return_value="/usr/bin/rpmkeys")
@patch("rpmdrop.package._run")
def test_unknown_signing_key_is_not_trusted(mock_run, _which, tmp_path):
    mock_run.return_value = subprocess.CompletedProcess([], 0, "NOKEY", "")
    result = inspect_signature(tmp_path / "unknown-key.rpm")
    assert "not trusted or unavailable" in result


@patch("rpmdrop.package.shutil.which", return_value="/usr/bin/rpmkeys")
@patch("rpmdrop.package._run")
def test_valid_signature_is_reported(mock_run, _which, tmp_path):
    mock_run.return_value = subprocess.CompletedProcess([], 0, "digests signatures OK", "")
    result = inspect_signature(tmp_path / "signed.rpm")
    assert result.startswith("Signature and digest checks passed")
