"""Headless GTK smoke test for the real package-details widgets."""

from pathlib import Path

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, GLib

from rpmdrop.application import RpmDropApplication, RpmDropWindow
from rpmdrop.package import PackageInfo, SignatureInfo


def main() -> None:
    Adw.init()
    application = RpmDropApplication()
    application.register(None)
    window = RpmDropWindow(application=application)
    info = PackageInfo(
        path=Path("/tmp/example.rpm"),
        name="example",
        version="1.0",
        release="1.fc44",
        architecture="x86_64",
        summary="Example package",
        description="A GTK smoke-test package.",
        vendor="Example",
        packager="RpmDrop CI",
        license="MIT",
        signature=SignatureInfo("trusted", "Trusted", "Verified.", ""),
        requirements=("glibc", "python(abi) = 3.14"),
        provides=("example = 1.0-1.fc44",),
        requirements_error=None,
        provides_error=None,
    )
    window._display_package(info)
    assert window.requirements_row is not None
    assert window.provides_row is not None
    assert window.preview_button.get_visible()
    window.present()
    while GLib.MainContext.default().iteration(False):
        pass
    window.destroy()
    application.quit()


if __name__ == "__main__":
    main()
