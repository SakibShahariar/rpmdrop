"""Disposable Fedora DNF5 daemon integration test for the real installer backend."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from rpmdrop.dnf5 import close_session, execute_transaction, resolve_local_rpm


def main() -> None:
    rpm_path = Path(sys.argv[1]).resolve()
    if not rpm_path.is_file():
        raise SystemExit(f"Test RPM not found: {rpm_path}")

    installed_before = subprocess.run(
        ["rpm", "-q", "rpmdrop-dbus-smoke"], check=False, capture_output=True
    )
    if installed_before.returncode == 0:
        raise SystemExit("The DNF5 smoke-test package must not already be installed.")

    preview = resolve_local_rpm(rpm_path)
    names = {item.name for item in preview.items}
    if "rpmdrop-dbus-smoke" not in names:
        close_session(preview)
        raise SystemExit(
            "DNF5 resolved a transaction without the requested local RPM: "
            + ", ".join(sorted(names))
        )

    try:
        execute_transaction(
            preview,
            progress_callback=lambda message, _fraction: print(message, flush=True),
        )
    finally:
        close_session(preview)

    installed_after = subprocess.run(
        ["rpm", "-q", "rpmdrop-dbus-smoke"], check=False, capture_output=True
    )
    if installed_after.returncode != 0:
        raise SystemExit("The DNF5 daemon returned without installing the smoke-test RPM.")

    subprocess.run(["rpm", "-e", "rpmdrop-dbus-smoke"], check=True)


if __name__ == "__main__":
    main()
