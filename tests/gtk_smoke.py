"""Headless GTK smoke test for package details and transaction confirmation."""

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
    window._show_transaction_preview(preview)
    print("gtk-smoke: transaction preview constructed", flush=True)
    while GLib.MainContext.default().iteration(False):
        pass
    dialog = window._preview_dialog
    assert dialog is not None
    assert dialog.get_resizable()
    assert dialog.get_modal()
    assert dialog.get_transient_for() is window
    assert dialog.get_default_size() == (560, 440)
    install_button = dialog.get_widget_for_response(Gtk.ResponseType.ACCEPT)
    acknowledgement = dialog.get_content_area().get_last_child()
    assert isinstance(acknowledgement, Gtk.CheckButton)
    assert not install_button.get_sensitive()
    assert "packages will be removed" in acknowledgement.get_label()
    acknowledgement.set_active(True)
    assert install_button.get_sensitive()
    dialog.destroy()
    window._preview_dialog = None

    window.current_signature = SignatureInfo(
        "digest-failed", "Digest failed", "Do not install.", ""
    )
    window._show_transaction_preview(preview)
    print("gtk-smoke: blocked preview constructed", flush=True)
    while GLib.MainContext.default().iteration(False):
        pass
    blocked_dialog = window._preview_dialog
    assert blocked_dialog is not None
    assert blocked_dialog.get_resizable()
    assert blocked_dialog.get_modal()
    assert blocked_dialog.get_transient_for() is window
    blocked_install = blocked_dialog.get_widget_for_response(Gtk.ResponseType.ACCEPT)
    blocked_acknowledgement = blocked_dialog.get_content_area().get_last_child()
    assert not blocked_install.get_sensitive()
    assert not blocked_acknowledgement.get_sensitive()
    blocked_dialog.destroy()

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
