import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from rpmdrop.package import (
    PackageInspectionError,
    SignatureInfo,
    inspect_package,
    inspect_signature,
)


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
def test_parses_package_metadata_and_requirements(mock_run, _which, tmp_path: Path):
    rpm_file = tmp_path / "sample.rpm"
    rpm_file.write_bytes(b"test fixture")
    metadata = (
        "sample\x1f1.2.3\x1f4.fc44\x1fx86_64\x1fA sample package"
        "\x1fA longer description.\nWith multiple lines."
        "\x1fExample Vendor\x1fExample Packager\x1fMIT"
    )
    mock_run.side_effect = [
        subprocess.CompletedProcess([], 0, metadata, ""),
        subprocess.CompletedProcess([], 0, "glibc\npython(abi) = 3.12\n", ""),
        subprocess.CompletedProcess([], 0, "sample = 1.2.3-4.fc44\npython3.12dist(sample)\n", ""),
    ]
    with patch(
        "rpmdrop.package.inspect_signature",
        return_value=SignatureInfo("trusted", "Trusted", "Verified.", ""),
    ):
        info = inspect_package(rpm_file)
    assert info.name == "sample"
    assert info.version == "1.2.3"
    assert info.architecture == "x86_64"
    assert "multiple lines" in info.description
    assert info.requirements == ("glibc", "python(abi) = 3.12")
    assert info.provides == ("sample = 1.2.3-4.fc44", "python3.12dist(sample)")


@patch("rpmdrop.package.shutil.which", return_value="/usr/bin/rpm")
@patch("rpmdrop.package._run")
def test_reports_rpm_query_errors(mock_run, _which, tmp_path: Path):
    rpm_file = tmp_path / "broken.rpm"
    rpm_file.write_bytes(b"broken")
    mock_run.return_value = subprocess.CompletedProcess([], 1, "", "not an rpm")
    with pytest.raises(PackageInspectionError, match="not an rpm"):
        inspect_package(rpm_file)


@patch("rpmdrop.package.shutil.which", return_value="/usr/bin/rpm")
@patch("rpmdrop.package._run")
def test_requirement_metadata_errors_do_not_break_inspection(mock_run, _which, tmp_path: Path):
    rpm_file = tmp_path / "broken-requirements.rpm"
    rpm_file.write_bytes(b"rpm")
    metadata = "sample\x1f1\x1f1\x1fx86_64\x1fsummary\x1fdescription\x1fvendor\x1fpackager\x1fMIT"
    mock_run.side_effect = [
        subprocess.CompletedProcess([], 0, metadata, ""),
        subprocess.CompletedProcess([], 1, "", "cannot read requirements"),
        subprocess.CompletedProcess([], 0, "sample = 1.0-1", ""),
    ]
    with patch(
        "rpmdrop.package.inspect_signature",
        return_value=SignatureInfo("trusted", "Trusted", "Verified.", ""),
    ):
        info = inspect_package(rpm_file)
    assert info.requirements == ()
    assert info.requirements_error == "cannot read requirements"
    assert info.provides == ("sample = 1.0-1",)


@patch("rpmdrop.package.shutil.which", return_value="/usr/bin/rpm")
@patch("rpmdrop.package._run")
def test_provides_metadata_errors_do_not_break_inspection(mock_run, _which, tmp_path: Path):
    rpm_file = tmp_path / "broken-provides.rpm"
    rpm_file.write_bytes(b"rpm")
    metadata = "sample\x1f1\x1f1\x1fx86_64\x1fsummary\x1fdescription\x1fvendor\x1fpackager\x1fMIT"
    mock_run.side_effect = [
        subprocess.CompletedProcess([], 0, metadata, ""),
        subprocess.CompletedProcess([], 0, "glibc", ""),
        subprocess.CompletedProcess([], 1, "", "cannot read provides"),
    ]
    with patch(
        "rpmdrop.package.inspect_signature",
        return_value=SignatureInfo("trusted", "Trusted", "Verified.", ""),
    ):
        info = inspect_package(rpm_file)
    assert info.requirements == ("glibc",)
    assert info.provides == ()
    assert info.provides_error == "cannot read provides"


@patch("rpmdrop.package.shutil.which", return_value="/usr/bin/rpm")
@patch("rpmdrop.package._run")
def test_accepts_empty_requirements_and_provides(mock_run, _which, tmp_path: Path):
    rpm_file = tmp_path / "minimal.rpm"
    rpm_file.write_bytes(b"rpm")
    metadata = "minimal\x1f1\x1f1\x1fx86_64\x1fsummary\x1fdescription\x1fvendor\x1fpackager\x1fMIT"
    mock_run.side_effect = [
        subprocess.CompletedProcess([], 0, metadata, ""),
        subprocess.CompletedProcess([], 0, "", ""),
        subprocess.CompletedProcess([], 0, "", ""),
    ]
    with patch(
        "rpmdrop.package.inspect_signature",
        return_value=SignatureInfo("unsigned", "Unsigned", "Not signed.", ""),
    ):
        info = inspect_package(rpm_file)
    assert info.requirements == ()
    assert info.provides == ()
