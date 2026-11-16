"""DNF5 daemon integration for read-only local RPM transaction resolution.

The daemon resolves dependencies and returns structured transaction items.
This module never calls Goal.do_transaction(), so resolving a preview cannot
install or remove packages.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class TransactionResolutionError(RuntimeError):
    """Raised when DNF5 cannot resolve a local RPM transaction."""


@dataclass(frozen=True, slots=True)
class TransactionItem:
    action: str
    reason: str
    name: str
    epoch: str
    version: str
    release: str
    architecture: str
    repository: str
    download_size: int
    install_size: int


@dataclass(frozen=True, slots=True)
class TransactionPreview:
    package_path: Path
    items: tuple[TransactionItem, ...]
    warnings: tuple[str, ...]


def _dbus_module() -> Any:
    try:
        return importlib.import_module("dbus")
    except ImportError as error:
        raise TransactionResolutionError(
            "Python D-Bus bindings are unavailable. Install the system dbus-python package."
        ) from error


def resolve_local_rpm(package_path: str | Path) -> TransactionPreview:
    """Resolve a local RPM with dnf5daemon without executing the transaction."""
    path = Path(package_path).expanduser().resolve()
    if path.suffix.lower() != ".rpm" or not path.is_file():
        raise TransactionResolutionError("Choose an existing local .rpm file.")

    dbus = _dbus_module()
    bus_name = "org.rpm.dnf.v0"
    object_path = "/" + bus_name.replace(".", "/")
    try:
        bus = dbus.SystemBus()
        session_manager = dbus.Interface(
            bus.get_object(bus_name, object_path),
            dbus_interface=f"{bus_name}.SessionManager",
        )
        session_path = session_manager.open_session(
            dbus.Dictionary({}, signature="sv")
        )
        session_object = bus.get_object(bus_name, session_path)
        rpm = dbus.Interface(
            session_object,
            dbus_interface=f"{bus_name}.rpm.Rpm",
        )
        goal = dbus.Interface(
            session_object,
            dbus_interface=f"{bus_name}.Goal",
        )

        # Loading a local RPM through the daemon may require Polkit
        # authorization. This queues a goal only; it does not execute it.
        rpm.install(
            [str(path)],
            dbus.Dictionary({"interactive": True}, signature="sv"),
        )
        raw_items, result = goal.resolve(
            dbus.Dictionary({}, signature="sv")
        )
        warnings: tuple[str, ...] = ()
        if int(result) == 2:
            problems = tuple(str(problem) for problem in goal.get_transaction_problems_string())
            raise TransactionResolutionError(
                "\n".join(problems) or "DNF5 could not resolve this transaction."
            )
        if int(result) == 1:
            warnings = tuple(
                str(problem) for problem in goal.get_transaction_problems_string()
            )

        items: list[TransactionItem] = []
        for object_type, action, reason, _attributes, package in raw_items:
            if str(object_type).lower() != "package":
                continue
            values = dict(package)
            items.append(
                TransactionItem(
                    action=str(action),
                    reason=str(reason),
                    name=str(values.get("name", "Unknown")),
                    epoch=str(values.get("epoch", "0")),
                    version=str(values.get("version", "Unknown")),
                    release=str(values.get("release", "Unknown")),
                    architecture=str(values.get("arch", "Unknown")),
                    repository=str(values.get("repo_id", "")),
                    download_size=int(values.get("package_size", 0)),
                    install_size=int(values.get("install_size", 0)),
                )
            )
        if not items and not warnings:
            raise TransactionResolutionError(
                "DNF5 resolved an empty transaction. Nothing will be installed."
            )
        return TransactionPreview(path, tuple(items), warnings)
    except TransactionResolutionError:
        raise
    except Exception as error:
        raise TransactionResolutionError(
            f"DNF5 transaction resolution failed: {error}"
        ) from error
