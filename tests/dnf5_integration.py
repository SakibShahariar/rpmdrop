"""Disposable Fedora DNF5 daemon integration test for the real installer backend."""

from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path

from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

from rpmdrop.dnf5 import (
    TransactionExecutionError,
    close_session,
    execute_transaction,
    resolve_local_rpm,
)


def main() -> None:
    DBusGMainLoop(set_as_default=True)
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

    loop = GLib.MainLoop()
    progress_messages: list[str] = []
    errors: list[Exception] = []

    def install_in_worker() -> None:
        try:
            execute_transaction(
                preview,
                progress_callback=lambda message, _fraction: progress_messages.append(message),
            )
        except TransactionExecutionError as error:
            errors.append(error)
        finally:
            try:
                close_session(preview)
            except TransactionExecutionError as error:
                errors.append(error)
            GLib.idle_add(loop.quit)

    worker = threading.Thread(target=install_in_worker, daemon=True)
    worker.start()
    loop.run()
    worker.join(timeout=10)
    if worker.is_alive():
        raise SystemExit("The DNF5 transaction worker did not finish.")
    if errors:
        raise SystemExit(f"The DNF5 transaction failed: {errors[0]}")
    if not any(
        marker in message
        for message in progress_messages
        for marker in ("Starting RPM transaction", "Starting package action", "Processing")
    ):
        raise SystemExit("The DNF5 daemon did not emit transaction progress signals.")

    installed_after = subprocess.run(
        ["rpm", "-q", "rpmdrop-dbus-smoke"], check=False, capture_output=True
    )
    if installed_after.returncode != 0:
        raise SystemExit("The DNF5 daemon returned without installing the smoke-test RPM.")

    subprocess.run(["rpm", "-e", "rpmdrop-dbus-smoke"], check=True)


if __name__ == "__main__":
    main()
