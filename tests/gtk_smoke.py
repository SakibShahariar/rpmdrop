"""Headless GTK smoke test for package details and transaction confirmation."""

import time
from pathlib import Path
from unittest.mock import patch

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, Gio, GLib, Gtk

from rpmdrop.application import RpmDropApplication, RpmDropWindow
from rpmdrop.application import main as application_main
from rpmdrop.dnf5 import TransactionItem, TransactionPreview
from rpmdrop.package import PackageInfo, SignatureInfo


def pump_until(predicate, timeout: float = 5.0) -> bool:
    """Run the main loop until predicate() holds or timeout expires.

    Adw.Dialog closes with an animation, so the widget is detached from its
    root asynchronously; a single non-blocking iteration is not enough.
    """
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            return False
        GLib.MainContext.default().iteration(False)
        time.sleep(0.01)
    return True


def main() -> None:
    print("gtk-smoke: starting", flush=True)
    Adw.init()
    with (
        patch("rpmdrop.application.os.geteuid", return_value=0),
        patch.object(RpmDropApplication, "run") as application_run,
    ):
        assert application_main() == 1
        application_run.assert_not_called()

    application = RpmDropApplication()
    application.register(None)
    window = RpmDropWindow(application=application)
    window.set_default_size(480, 420)
    assert window.get_resizable()

    info = PackageInfo(
        path=Path("/tmp/" + "long-package-path-" * 20 + ".rpm"),
        name="example",
        version="1.0",
        release="1.fc44",
        architecture="x86_64",
        summary="Example package",
        description="A long description. " * 300,
        vendor="Example",
        packager="RpmDrop CI",
        license="MIT",
        signature=SignatureInfo("trusted", "Trusted", "Verified.", ""),
        requirements=tuple(f"dependency-{index}" for index in range(80)),
        provides=tuple(f"capability-{index}" for index in range(80)),
        requirements_error=None,
        provides_error=None,
    )
    window._display_package(info)
    print("gtk-smoke: package details constructed", flush=True)

    class FakeFileList:
        def get_files(self):
            return [
                Gio.File.new_for_path("/tmp/first package.rpm"),
                Gio.File.new_for_uri("sftp://example.invalid/remote.rpm"),
            ]

    with patch.object(window, "inspect_paths") as inspect_paths:
        assert window._on_files_dropped(None, FakeFileList(), 0.0, 0.0)
        inspect_paths.assert_called_once_with(["/tmp/first package.rpm"])
    assert isinstance(window.drop_target, Gtk.DropTarget)
    assert window.requirements_row is not None
    assert window.provides_row is not None
    assert isinstance(window.requirements_row, Adw.ExpanderRow)
    assert isinstance(window.provides_row, Adw.ExpanderRow)
    assert window.description.get_wrap()
    assert window.open_button.get_can_focus()
    assert window.open_button.get_label() == "Open RPM"
    assert window.history_button.get_can_focus()
    assert window.history_button.get_label() == "History"
    assert window.preview_button.get_can_focus()
    assert window.preview_button.get_label() == "Preview transaction"
    assert window.preview_button.get_visible()

    preview = TransactionPreview(
        package_path=info.path,
        items=(
            TransactionItem(
                action="Remove",
                reason="Dependency",
                name="old-package",
                epoch="0",
                version="1.0",
                release="1.fc44",
                architecture="noarch",
                repository="installed",
                download_size=0,
                install_size=1024,
            ),
        ),
        warnings=(),
        session_path="/session/1",
    )

    window.present()
    with patch.object(window.history_store, "list_recent", return_value=()):
        window._on_history_clicked(window.history_button)
    while GLib.MainContext.default().iteration(False):
        pass
    history_dialog = window._history_dialog
    assert isinstance(history_dialog, Adw.AlertDialog)
    assert history_dialog.get_root() is window
    history_dialog.close()
    assert pump_until(lambda: history_dialog.get_root() is None)

    with patch("rpmdrop.application.threading.Thread") as thread:
        window._start_installation(preview)
        thread.assert_called_once()
    install_dialog = window._install_dialog
    assert isinstance(install_dialog, Adw.AlertDialog)
    assert install_dialog.get_root() is window
    assert not install_dialog.get_can_close()
    assert install_dialog.get_response_enabled("cancel")
    assert isinstance(window._install_spinner, Adw.Spinner)
    # Detach first: force_close() re-emits the "cancel" response, and the
    # cancel handler must not run against a detached dialog.
    window._install_dialog = None
    window._active_preview = None
    install_dialog.force_close()
    assert pump_until(lambda: install_dialog.get_root() is None)
    window._install_status = None
    window._install_spinner = None
    window._install_progress = None
    window.open_button.set_sensitive(True)
    window.preview_button.set_sensitive(True)

    window._show_install_result("Test result", "Result details. " * 200, False)
    while GLib.MainContext.default().iteration(False):
        pass
    result_dialog = window._result_dialog
    assert isinstance(result_dialog, Adw.AlertDialog)
    assert result_dialog.get_root() is window
    result_dialog.close()
    assert pump_until(lambda: result_dialog.get_root() is None)

    window._show_transaction_preview(preview)
    print("gtk-smoke: transaction preview constructed", flush=True)
    while GLib.MainContext.default().iteration(False):
        pass
    dialog = window._preview_dialog
    assert isinstance(dialog, Adw.AlertDialog)
    assert dialog.get_root() is window
    acknowledgement = window._preview_ack
    assert isinstance(acknowledgement, Gtk.CheckButton)
    assert not dialog.get_response_enabled("install")
    assert "packages will be removed" in acknowledgement.get_label()
    acknowledgement.set_active(True)
    assert dialog.get_response_enabled("install")
    dialog.close()
    assert pump_until(lambda: dialog.get_root() is None)
    window._preview_dialog = None
    window._preview_ack = None

    window.current_signature = SignatureInfo(
        "digest-failed", "Digest failed", "Do not install.", ""
    )
    window._show_transaction_preview(preview)
    print("gtk-smoke: blocked preview constructed", flush=True)
    while GLib.MainContext.default().iteration(False):
        pass
    blocked_dialog = window._preview_dialog
    assert isinstance(blocked_dialog, Adw.AlertDialog)
    assert blocked_dialog.get_root() is window
    blocked_acknowledgement = window._preview_ack
    assert not blocked_dialog.get_response_enabled("install")
    assert not blocked_acknowledgement.get_sensitive()
    blocked_dialog.close()
    assert pump_until(lambda: blocked_dialog.get_root() is None)
    window._preview_dialog = None
    window._preview_ack = None

    window.destroy()
    application.quit()


if __name__ == "__main__":
    import faulthandler

    faulthandler.enable()
    try:
        main()
    except BaseException as error:
        print(f"gtk-smoke failed: {error!r}", flush=True)
        raise
