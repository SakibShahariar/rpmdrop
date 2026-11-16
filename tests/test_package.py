import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from rpmdrop.package import (\n    PackageInspectionError,\n    SignatureInfo,\n    inspect_package,\n    inspect_signature,\n)


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
    ]
    with patch(\n        "rpmdrop.package.inspect_signature",\n        return_value=SignatureInfo("trusted", "Trusted", "Verified.", ""),\n    ):
        info = inspect_package(rpm_file)
    assert info.name == "sample"
    assert info.version == "1.2.3"
    assert info.architecture == "x86_64"
    assert "multiple lines" in info.description
    assert info.requirements == ("glibc", "python(abi) = 3.12")


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
def test_reports_requirement_query_errors(mock_run, _which, tmp_path: Path):
    rpm_file = tmp_path / "broken.rpm"
    rpm_file.write_bytes(b"broken")
    metadata = "sample\x1f1\x1f1\x1fx86_64\x1fsummary\x1fdescription\x1fvendor\x1fpackager\x1fMIT"
    mock_run.side_effect = [
        subprocess.CompletedProcess([], 0, metadata, ""),
        subprocess.CompletedProcess([], 1, "", "cannot read requirements"),
    ]
    with pytest.raises(PackageInspectionError, match="cannot read requirements"):
        inspect_package(rpm_file)


@patch("rpmdrop.package.shutil.which", return_value="/usr/bin/rpmkeys")
@patch("rpmdrop.package._run")
def test_unsigned_package_is_distinguished_from_trusted(mock_run, _which, tmp_path):
    mock_run.return_value = subprocess.CompletedProcess([], 0, "digests OK", "")
    result = inspect_signature(tmp_path / "unsigned.rpm")
    assert result.status == "unsigned"
    assert "no cryptographic signature" in result.explanation


@patch("rpmdrop.package.shutil.which", return_value="/usr/bin/rpmkeys")
@patch("rpmdrop.package._run")
def test_unknown_signing_key_is_not_trusted(mock_run, _which, tmp_path):
    mock_run.return_value = subprocess.CompletedProcess(
        [], 1, "Header V4 RSA/SHA256 Signature, key ID 1234: NOKEY", ""
    )
    result = inspect_signature(tmp_path / "unknown-key.rpm")
    assert result.status == "unknown-key"
    assert "not trusted" in result.explanation


@patch("rpmdrop.package.shutil.which", return_value="/usr/bin/rpmkeys")
@patch("rpmdrop.package._run")
def test_valid_signature_requires_digest_and_signature_success(mock_run, _which, tmp_path):
    mock_run.return_value = subprocess.CompletedProcess([], 0, "digests signatures OK", "")
    result = inspect_signature(tmp_path / "signed.rpm")
    assert result.status == "trusted"


@pytest.mark.parametrize(
    ("output", "status"),
    [
        ("BAD signature", "signature-failed"),
        ("BAD digest", "digest-failed"),
        ("digests NOT OK", "digest-failed"),
    ],
)
@patch("rpmdrop.package.shutil.which", return_value="/usr/bin/rpmkeys")
@patch("rpmdrop.package._run")
def test_failed_signature_and_digest_checks_are_distinct(
    mock_run, _which, tmp_path, output, status
):
    mock_run.return_value = subprocess.CompletedProcess([], 1, output, "")
    result = inspect_signature(tmp_path / "broken.rpm")
    assert result.status == status


@patch("rpmdrop.package.shutil.which", return_value=None)
def test_reports_unavailable_signature_tool(_which, tmp_path):
    result = inspect_signature(tmp_path / "unknown.rpm")
    assert result.status == "unavailable"
