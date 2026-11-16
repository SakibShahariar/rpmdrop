"""Safe live DNF5 daemon integration test; resolves but never executes a transaction."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import dbus


def main() -> None:
    rpm_path = Path(sys.argv[1]).resolve()
    if not rpm_path.is_file():
        raise SystemExit(f"Test RPM not found: {rpm_path}")

    installed_before = subprocess.run(
        ["rpm", "-q", "rpmdrop-dbus-smoke"], check=False, capture_output=True
    )
    if installed_before.returncode == 0:
        raise SystemExit("The DNF5 smoke-test package must not already be installed.")

    bus_name = "org.rpm.dnf.v0"
    manager_path = "/org/rpm/dnf/v0"
    bus = dbus.SystemBus()
    manager = dbus.Interface(
        bus.get_object(bus_name, manager_path),
        dbus_interface=f"{bus_name}.SessionManager",
    )
    session_path = manager.open_session(
        dbus.Dictionary({"load_available_repos": False}, signature="sv")
    )
    try:
        session = bus.get_object(bus_name, session_path)
        rpm = dbus.Interface(
            session,
            dbus_interface=f"{bus_name}.rpm.Rpm",
        )
        goal = dbus.Interface(session, dbus_interface=f"{bus_name}.Goal")
        rpm.install([str(rpm_path)], dbus.Dictionary({}, signature="sv"))
        items, result = goal.resolve(
            dbus.Dictionary({"allow_erasing": True}, signature="sv")
        )
        if int(result) == 2:
            problems = goal.get_transaction_problems_string()
            raise SystemExit("DNF5 could not resolve the smoke-test RPM: " + "; ".join(problems))
        package_names = {
            str(package.get("name"))
            for object_type, _action, _reason, _attrs, package in items
            if str(object_type).lower() == "package"
        }
        if "rpmdrop-dbus-smoke" not in package_names:
            raise SystemExit(
                "DNF5 resolved a transaction without the requested local RPM: "
                + ", ".join(sorted(package_names))
            )
    finally:
        if not manager.close_session(session_path):
            raise SystemExit("DNF5 did not close the smoke-test session.")

    installed_after = subprocess.run(
        ["rpm", "-q", "rpmdrop-dbus-smoke"], check=False, capture_output=True
    )
    if installed_after.returncode == 0:
        raise SystemExit("The preview unexpectedly installed the smoke-test package.")


if __name__ == "__main__":
    main()
