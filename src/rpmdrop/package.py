"Read metadata and signature information from a local RPM file."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class PackageInspectionError(RuntimeError):
    """Raised when a package cannot be inspected."""


@dataclass(frozen=True, slots=True)
class PackageInfo:
    path: Path
    name: str
    version: str
    release: str
    architecture: str
    summary: str
    description: str
    vendor: str
    packager: str
    license: str
    signature: str


_SEPARATOR = "\x1f"
_QUERY_FIELDS = (
    "%{NAME}", "%{VERSION}", "%{RELEASE}", "%{ARCH}", "%{SUMMARY}",
    "%{DESCRIPTION}", "%{VENDOR}", "%{PACKAGER}", "%{LICENSE}",
)
_QUERY_FORMAT = _SEPARATOR.join(_QUERY_FIELDS)


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command, check=False, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=20,
        )
    except FileNotFoundError as error:
        raise PackageInspectionError(
            f"Required system tool '{command[0]}' was not found."
        ) from error
    except subprocess.TimeoutExpired as error:
        raise PackageInspectionError("RPM inspection timed out.") from error


def inspect_package(package_path: str | Path) -> PackageInfo:
    """Inspect an RPM without installing it or changing the system."""
    path = Path(package_path).expanduser().resolve()
    if path.suffix.lower() != ".rpm":
        raise PackageInspectionError("The selected file does not have an .rpm extension.")
    if not path.is_file():
        raise PackageInspectionError("The selected RPM file does not exist.")
    if not os.access(path, os.R_OK):
        raise PackageInspectionError("The selected RPM file is not readable.")
    rpm = shutil.which("rpm")
    if rpm is None:
        raise PackageInspectionError("The 'rpm' command is not installed.")

    result = _run([rpm, "-qp", "--queryformat", _QUERY_FORMAT, str(path)])
    if result.returncode != 0:
        raise PackageInspectionError(result.stderr.strip() or "rpm could not read this package.")
    fields = result.stdout.split(_SEPARATOR)
    if len(fields) != len(_QUERY_FIELDS):
        raise PackageInspectionError("The RPM returned incomplete package metadata.")

    return PackageInfo(
        path=path, name=fields[0] or "Unknown", version=fields[1] or "Unknown",
        release=fields[2] or "Unknown", architecture=fields[3] or "Unknown",
        summary=fields[4] or "No summary provided",
        description=fields[5] or "No description provided",
        vendor=fields[6] or "Unknown", packager=fields[7] or "Unknown",
        license=fields[8] or "Unknown", signature=inspect_signature(path),
    )


def inspect_signature(package_path: Path) -> str:
    """Report digest and signature results without overstating package trust."""
    tool = shutil.which("rpmkeys") or shutil.which("rpm")
    if tool is None:
        return "Could not verify: rpmkeys is unavailable"

    result = _run([tool, "--checksig", "--verbose", str(package_path)])
    output = (result.stdout + result.stderr).strip()
    lowered = output.lower()

    if result.returncode != 0:
        return f"Verification failed: {output or 'signature check returned an error'}"
    if "nokey" in lowered or "not trusted" in lowered:
        return f"Signing key is not trusted or unavailable: {output}"
    if "digests signatures ok" in lowered or "signatures ok" in lowered:
        return f"Signature and digest checks passed: {output}"
    if "digests ok" in lowered:
        return f"Package digests passed; no trusted signature was confirmed: {output}"
    return f"Verification result requires review: {output or 'no details returned'}"
