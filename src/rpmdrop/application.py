"""GTK 4/libadwaita application window."""

from __future__ import annotations

import sys
from pathlib import Path

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, Gio, Gtk

from rpmdrop.package import PackageInfo, PackageInspectionError, inspect_package


class RpmDropWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("RpmDrop")
        self.set_default_size(680, 560)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_content(outer)
        header = Adw.HeaderBar()
        outer.append(header)
        open_button = Gtk.Button(label="Open RPM")
        open_button.add_css_class("suggested-action")
        open_button.connect("clicked", self._on_open_clicked)
        header.pack_end(open_button)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18,
                          margin_top=24, margin_bottom=24, margin_start=24, margin_end=24)
        outer.append(content)
        self.heading = Gtk.Label(label="Inspect a package")
        self.heading.add_css_class("title-1")
        self.heading.set_xalign(0)
        content.append(self.heading)
        self.status = Gtk.Label(label="Choose a local .rpm file to review its details before installation.")
        self.status.set_xalign(0)
        self.status.set_wrap(True)
        self.status.add_css_class("dim-label")
        content.append(self.status)
        self.details = Adw.PreferencesGroup(title="Package details")
        content.append(self.details)
        self.description = Gtk.Label()
        self.description.set_xalign(0)
        self.description.set_wrap(True)
        self.description.set_selectable(True)
        self.description.set_visible(False)
        content.append(self.description)
        self._rows: list[Adw.ActionRow] = []

    def _clear_details(self) -> None:
        for row in self._rows:
            self.details.remove(row)
        self._rows.clear()
        self.description.set_visible(False)

    def _add_row(self, title: str, value: str) -> None:
        row = Adw.ActionRow(title=title, subtitle=value)
        row.set_subtitle_selectable(True)
        self.details.add(row)
        self._rows.append(row)

    def _on_open_clicked(self, _button: Gtk.Button) -> None:
        chooser = Gtk.FileChooserNative.new("Open an RPM package", self,
            Gtk.FileChooserAction.OPEN, "Open", "Cancel")
        rpm_filter = Gtk.FileFilter()
        rpm_filter.set_name("RPM packages")
        rpm_filter.add_pattern("*.rpm")
        chooser.add_filter(rpm_filter)
        chooser.connect("response", self._on_file_selected)
        chooser.show()

    def _on_file_selected(self, chooser: Gtk.FileChooserNative, response: int) -> None:
        if response == Gtk.ResponseType.ACCEPT:
            selected = chooser.get_file()
            if selected is not None and selected.get_path():
                self.inspect_path(selected.get_path())
        chooser.destroy()

    def inspect_path(self, path: str) -> None:
        self.status.set_text(f"Inspecting {Path(path).name}…")
        try:
            info = inspect_package(path)
        except PackageInspectionError as error:
            self._clear_details()
            self.heading.set_text("Could not inspect package")
            self.status.set_text(str(error))
            return
        self._display_package(info)

    def _display_package(self, info: PackageInfo) -> None:
        self._clear_details()
        self.heading.set_text(info.name)
        self.status.set_text(f"{info.version}-{info.release} · {info.architecture}")
        for title, value in (
            ("Version", f"{info.version}-{info.release}"), ("Architecture", info.architecture),
            ("Vendor", info.vendor), ("Packager", info.packager), ("License", info.license),
            ("Signature", info.signature), ("File", str(info.path)),
        ):
            self._add_row(title, value)
        self.description.set_text(f"{info.summary}\n\n{info.description}")
        self.description.set_visible(True)


class RpmDropApplication(Adw.Application):
    def __init__(self):
        super().__init__(application_id="io.github.sakibshahariar.RpmDrop",
                         flags=Gio.ApplicationFlags.HANDLES_OPEN)
        self.window: RpmDropWindow | None = None

    def do_activate(self) -> None:
        if self.window is None:
            self.window = RpmDropWindow(application=self)
        self.window.present()

    def do_open(self, files: list[Gio.File], _n_files: int, _hint: str) -> None:
        self.do_activate()
        if self.window and files:
            path = files[0].get_path()
            if path:
                self.window.inspect_path(path)


def main() -> int:
    Adw.init()
    return RpmDropApplication().run(sys.argv)
