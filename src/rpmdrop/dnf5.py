"""Read-only DNF5 transaction resolution for local RPM files.

The backend deliberately uses DNF5's --assumeno mode. It can resolve and
display a proposed transaction, but it cannot execute that transaction.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class TransactionResolutionError(RuntimeError):
    """Raised when DNF5 cannot resolve a local RPM transaction."""


@dataclass(frozen=True, slots=True)
class TransactionPreview:
    package_path: Path
    output: str
    command: tuple[str, ...]


def resolve_local_rpm(package_path: str | Path) -> TransactionPreview:
    """Ask DNF5 to resolve a local RPM while automatically declining changes."""
    path = Path(package_path).expanduser().resolve()
    if path.suffix.lower() != ".rpm" or not path.is_file():
        raise TransactionResolutionError("Choose an existing local .rpm file.")

    dnf5 = shutil.which("dnf5")
    if dnf5 is None:
        raise TransactionResolutionError(
            "DNF5 was not found. Install the dnf5 package to preview transactions."
        )

    command = (dnf5, "--assumeno", "install", "--", str(path))
    environment = os.environ.copy()
    environment["LC_ALL"] = "C"
    environment["LANG"] = "C"
    environment["DNF5_FORCE_COLUMNS"] = "100"

    try:
        result = subprocess.run(
            list(command),
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
            env=environment,
        )
    except subprocess.TimeoutExpired as error:
        raise TransactionResolutionError(
            "DNF5 transaction resolution timed out. No packages were installed."
        ) from error
    except OSError as error:
        raise TransactionResolutionError(f"Could not start DNF5: {error}") from error

    output = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
    if not output:
        raise TransactionResolutionError(
            "DNF5 returned no transaction details. No packages were installed."
        )

    lowered = output.lower()
    if "error:" in lowered or "failed to" in lowered or "cannot " in lowered:
        raise TransactionResolutionError(output)

    # DNF5's --assumeno intentionally declines the final confirmation. A
    # non-zero exit status is therefore expected for a successfully resolved
    # transaction; the captured output is shown verbatim for user review.
    if "operation aborted" not in lowered and "nothing to do" not in lowered:
        if result.returncode != 0:
            raise TransactionResolutionError(output)

    return TransactionPreview(package_path=path, output=output, command=command)
