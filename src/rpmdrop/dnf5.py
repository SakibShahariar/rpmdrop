"""DNF5 daemon integration for read-only local RPM transaction resolution.

The daemon resolves dependencies and returns structured transaction items.
This module never calls Goal.do_transaction(), so resolving a preview cannot
install or remove packages.
"""

from __future__ import annotations

import importlib
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class TransactionResolutionError(RuntimeError):
    """Raised when DNF5 cannot resolve a local RPM transaction."""


class TransactionExecutionError(RuntimeError):
    """Raised when a confirmed DNF5 transaction cannot be executed."""


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
    session_path: str


def _dbus_module() -> Any:
    try:
        return importlib.import_module("dbus")
    except ImportError as error:
        raise TransactionResolutionError(
            "Python D-Bus bindings are unavailable. Install the system dbus-python package."
        ) from error


def _items_from_raw(raw_items: Any) -> tuple[TransactionItem, ...]:
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
    return tuple(items)


def _goal_for_session(dbus: Any, session_path: str) -> tuple[Any, Any]:
    bus_name = "org.rpm.dnf.v0"
    bus = dbus.SystemBus()
    session_object = bus.get_object(bus_name, session_path)
    goal = dbus.Interface(session_object, dbus_interface=f"{bus_name}.Goal")
    return bus, goal


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

        items = _items_from_raw(raw_items)
        if not items and not warnings:
            raise TransactionResolutionError(
                "DNF5 resolved an empty transaction. Nothing will be installed."
            )
        return TransactionPreview(path, items, warnings, str(session_path))
    except TransactionResolutionError:
        raise
    except Exception as error:
        message = str(error)
        dbus_name = getattr(error, "get_dbus_name", lambda: "")()
        if dbus_name == "org.freedesktop.DBus.Error.ServiceUnknown" or "ServiceUnknown" in message:
            raise TransactionResolutionError(
                "The DNF5 daemon is unavailable. Install the dnf5daemon-server package "
                "and make sure its system D-Bus service is available."
            ) from error
        raise TransactionResolutionError(
            f"DNF5 transaction resolution failed: {message}"
        ) from error



def execute_transaction(
    preview: TransactionPreview,
    progress_callback: Any | None = None,
) -> None:
    """Revalidate and execute the exact previewed DNF5 goal after user approval."""
    dbus = _dbus_module()
    receivers = []
    try:
        bus, goal = _goal_for_session(dbus, preview.session_path)
        raw_items, result = goal.resolve(dbus.Dictionary({}, signature="sv"))
        if int(result) == 2:
            problems = tuple(str(problem) for problem in goal.get_transaction_problems_string())
            raise TransactionExecutionError(
                "\n".join(problems) or "DNF5 could not revalidate the transaction."
            )
        current_items = _items_from_raw(raw_items)
        if current_items != preview.items:
            raise TransactionExecutionError(
                "The DNF5 transaction changed since the preview. Review a new preview "
                "before installing."
            )

        if progress_callback is not None:
            def report(label: str):
                def handler(_session, *values):
                    progress_callback(label.format(*values))
                return handler

            signal_handlers = (
                ("transaction_elem_progress", "Preparing {} ({}/{})"),
                ("transaction_action_start", "{}: {}"),
                ("transaction_transaction_progress", "Downloading packages ({}/{})"),
                ("transaction_action_progress", "Installing {} ({}/{})"),
            )
            for signal_name, message in signal_handlers:
                handler = report(message)
                bus.add_signal_receiver(
                    handler,
                    signal_name=signal_name,
                    dbus_interface="org.rpm.dnf.v0.SessionManager",
                    path=preview.session_path,
                )
                receivers.append(handler)

        goal.do_transaction(
            dbus.Dictionary({"interactive": True}, signature="sv"),
            timeout=3600,
        )
    except TransactionExecutionError:
        raise
    except Exception as error:
        raise TransactionExecutionError(
            f"DNF5 installation failed: {error}"
        ) from error
    finally:
        if "bus" in locals():
            for handler in receivers:
                with suppress(dbus.DBusException):
                    bus.remove_signal_receiver(
                        handler,
                        dbus_interface="org.rpm.dnf.v0.SessionManager",
                        path=preview.session_path,
                    )


def cancel_transaction(preview: TransactionPreview) -> tuple[bool, str]:
    """Ask DNF5 to cancel an active download phase, if cancellation is still possible."""
    dbus = _dbus_module()
    try:
        _bus, goal = _goal_for_session(dbus, preview.session_path)
        success, message = goal.cancel()
        return bool(success), str(message)
    except Exception as error:
        raise TransactionExecutionError(
            f"Could not cancel the DNF5 transaction: {error}"
        ) from error
