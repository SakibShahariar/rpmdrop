"""Read metadata and signature information from a local RPM file."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class PackageInspectionError(RuntimeError):
    """Raised when a package cannot be inspected."""


@dataclass(frozen=True, slots=True)
class SignatureInfo:
    status: str
    summary: str
    explanation: str
    details: str


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
    signature: SignatureInfo
    requirements: tuple[str, ...]
    provides: tuple[str, ...]
    requirements_error: str | None
    provides_error: str | None


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

    requirements_result = _run([rpm, "-qp", "--requires", str(path)])
    requirements_error = None
    if requirements_result.returncode != 0:
        requirements = ()
        requirements_error = (
            requirements_result.stderr.strip() or "Could not read package requirements."
        )
    else:
        requirements = tuple(
            line.strip()
            for line in requirements_result.stdout.splitlines()
            if line.strip()
        )

    provides_result = _run([rpm, "-qp", "--provides", str(path)])
    provides_error = None
    if provides_result.returncode != 0:
        provides = ()
        provides_error = (
            provides_result.stderr.strip() or "Could not read package capabilities."
        )
    else:
        provides = tuple(
            line.strip()
            for line in provides_result.stdout.splitlines()
            if line.strip()
        )

    return PackageInfo(
        path=path, name=fields[0] or "Unknown", version=fields[1] or "Unknown",
        release=fields[2] or "Unknown", architecture=fields[3] or "Unknown",
        summary=fields[4] or "No summary provided",
        description=fields[5] or "No description provided",
        vendor=fields[6] or "Unknown", packager=fields[7] or "Unknown",
        license=fields[8] or "Unknown", signature=inspect_signature(path),
        requirements=requirements,
        provides=provides,
        requirements_error=requirements_error,
        provides_error=provides_error,
    )


def inspect_signature(package_path: Path) -> SignatureInfo:
    """Classify RPM digest integrity separately from signing-key trust."""
    tool = shutil.which("rpmkeys") or shutil.which("rpm")
    if tool is None:
        return SignatureInfo(
            "unavailable",
            "Signature verification unavailable",
            "Install the RPM tooling to check package signatures and digests.",
            "",
        )

    try:
        result = _run([tool, "--checksig", "--verbose", str(package_path)])
    except PackageInspectionError as error:
        return SignatureInfo(
            "unavailable",
            "Signature verification unavailable",
            str(error),
            "",
        )

    output = (result.stdout + result.stderr).strip()
    lowered = output.lower()

    if "nokey" in lowered or "not trusted" in lowered or "nottrusted" in lowered:
        return SignatureInfo(
            "unknown-key",
            "Signed with an unknown or untrusted key",
            "The signing key is missing or not trusted by the RPM key database. Verify "
            "the publisher and key fingerprint independently before considering installation.",
            output,
        )
    if any(marker in lowered for marker in (
        "bad signature", "signatures bad", "signatures not ok", "signature not ok",
        "signature verification failed",
    )):
        return SignatureInfo(
            "signature-failed",
            "Package signature verification failed",
            "The cryptographic signature did not verify. Do not install this package.",
            output,
        )
    if any(marker in lowered for marker in (
        "bad digest", "digests bad", "digest bad", "digests not ok",
        "digest not ok", "digest verification failed",
    )):
        return SignatureInfo(
            "digest-failed",
            "Package digest verification failed",
            "The package contents may be corrupted or altered. Do not install this package.",
            output,
        )
    if result.returncode != 0:
        return SignatureInfo(
            "verification-failed",
            "RPM verification failed",
            "RPM could not complete verification. Treat this package as unverified.",
            output or "rpmkeys returned an error without details.",
        )
    if "digests signatures ok" in lowered or "digests signature ok" in lowered:
        return SignatureInfo(
            "trusted",
            "Signature verified with a trusted key",
            "The package signature and file digests both passed verification.",
            output,
        )
    if "digests ok" in lowered and "signature" not in lowered:
        return SignatureInfo(
            "unsigned",
            "Unsigned package",
            "The file digests passed, but no cryptographic signature was confirmed. "
            "Digest integrity does not establish who published the package.",
            output,
        )
    return SignatureInfo(
        "indeterminate",
        "Signature status could not be determined",
        "RPM returned an ambiguous verification result. Treat this package as unverified.",
        output or "No verification details were returned.",
    )
