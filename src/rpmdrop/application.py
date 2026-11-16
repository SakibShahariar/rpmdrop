"""GTK 4/libadwaita application window."""

from __future__ import annotations

import sys
import threading
from pathlib import Path

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from rpmdrop.dnf5 import TransactionPreview, TransactionResolutionError, resolve_local_rpm
from rpmdrop.package import PackageInfo, PackageInspectionError, inspect_package


class RpmDropWindow(Adw.ApplicationWindow):
    """Main window for selecting and inspecting local RPM packages."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("RpmDrop")
        self.set_default_size(680, 600)
        self.set_size_request(480, 420)

        self._pending_paths: list[str] = []
        self._inspection_active = False
        self.current_package_path: Path | None = None

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_content(outer)

        header = Adw.HeaderBar()
        outer.append(header)
        self.open_button = Gtk.Button(label="Open RPM")
        self.open_button.add_css_class("suggested-action")
        self.open_button.connect("clicked", self._on_open_clicked)
        header.pack_end(self.open_button)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_child(Gtk.Box(orientation=Gtk.Orientation.VERTICAL))
        outer.append(scroller)

        content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=18,
            margin_top=24,
            margin_bottom=24,
            margin_start=28,
            margin_end=28,
        )
        scroller.set_child(content)

        intro = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        content.append(intro)
        self.package_icon = Gtk.Image.new_from_icon_name("package-x-generic-symbolic")
        self.package_icon.set_pixel_size(48)
        self.package_icon.add_css_class("dim-label")
        intro.append(self.package_icon)

        titles = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        intro.append(titles)
        self.heading = Gtk.Label(label="Install RPM packages with ease")
        self.heading.add_css_class("title-1")
        self.heading.set_xalign(0)
        self.heading.set_wrap(True)
        titles.append(self.heading)
        self.status = Gtk.Label(
            label="Choose a local .rpm file to inspect it before making system changes."
        )
        self.status.set_xalign(0)
        self.status.set_wrap(True)
        self.status.add_css_class("dim-label")
        titles.append(self.status)

        self.spinner = Gtk.Spinner()
        self.spinner.set_halign(Gtk.Align.START)
        self.spinner.set_visible(False)
        content.append(self.spinner)

        self.drop_area = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=10,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=True,
            margin_top=12,
            margin_bottom=12,
        )
        self.drop_area.add_css_class("card")
        self.drop_area.set_size_request(-1, 170)
        content.append(self.drop_area)
        drop_target = Gtk.DropTarget.new(Gio.File, Gdk.DragAction.COPY)
        drop_target.connect("drop", self._on_drop)
        self.drop_area.add_controller(drop_target)

        drop_icon = Gtk.Image.new_from_icon_name("folder-download-symbolic")
        drop_icon.set_pixel_size(40)
        drop_icon.add_css_class("dim-label")
        self.drop_area.append(drop_icon)
        drop_label = Gtk.Label(label="Open an RPM package")
        drop_label.add_css_class("title-3")
        self.drop_area.append(drop_label)
        drop_hint = Gtk.Label(label="Use Open RPM above or open an .rpm file from Files.")
        drop_hint.add_css_class("dim-label")
        drop_hint.set_wrap(True)
        drop_hint.set_justify(Gtk.Justification.CENTER)
        self.drop_area.append(drop_hint)

        self.details = Adw.PreferencesGroup(title="Package details")
        self.details.set_visible(False)
        content.append(self.details)

        self.requirements_group = Adw.PreferencesGroup(title="Package requirements")
        self.requirements_group.set_visible(False)
        content.append(self.requirements_group)
        self.requirements_row: Adw.ActionRow | None = None

        self.preview_button = Gtk.Button(label="Preview transaction")
        self.preview_button.add_css_class("suggested-action")
        self.preview_button.set_halign(Gtk.Align.END)
        self.preview_button.set_visible(False)
        self.preview_button.connect("clicked", self._on_preview_clicked)
        content.append(self.preview_button)

        self.description = Gtk.Label()
        self.description.set_xalign(0)
        self.description.set_wrap(True)
        self.description.set_selectable(True)
        self.description.set_visible(False)
        content.append(self.description)
        self._rows: list[Adw.ActionRow] = []

        footer = Gtk.Label(
            label="RpmDrop inspects packages first. Nothing is installed during inspection."
        )
        footer.set_wrap(True)
        footer.set_xalign(0)
        footer.add_css_class("dim-label")
        footer.add_css_class("caption")
        content.append(footer)

    def _on_drop(self, _target: Gtk.DropTarget, value: Gio.File, _x: float, _y: float) -> bool:
        path = value.get_path() if isinstance(value, Gio.File) else None
        if path is None or not path.lower().endswith(".rpm"):
            return False
        self.inspect_paths([path])
        return True

    def _clear_details(self) -> None:
        for row in self._rows:
            self.details.remove(row)
        self._rows.clear()
        if self.requirements_row is not None:
            self.requirements_group.remove(self.requirements_row)
            self.requirements_row = None
        self.details.set_visible(False)
        self.requirements_group.set_visible(False)
        self.description.set_visible(False)
        self.preview_button.set_visible(False)
        self.current_package_path = None

    def _add_row(self, title: str, value: str) -> None:
        row = Adw.ActionRow(title=title, subtitle=value)
        row.set_subtitle_selectable(True)
        self.details.add(row)
        self._rows.append(row)

    def _on_open_clicked(self, _button: Gtk.Button) -> None:
        chooser = Gtk.FileChooserNative.new(
            "Open an RPM package",
            self,
            Gtk.FileChooserAction.OPEN,
            "Open",
            "Cancel",
        )
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
                self.inspect_paths([selected.get_path()])
        chooser.destroy()

    def inspect_path(self, path: str) -> None:
        """Queue one path for inspection; retained for desktop file opening."""
        self.inspect_paths([path])

    def inspect_paths(self, paths: list[str]) -> None:
        """Inspect paths sequentially without blocking the GTK main loop."""
        valid_paths = [str(Path(path).expanduser()) for path in paths if path]
        if not valid_paths:
            return
        self._pending_paths.extend(valid_paths)
        if not self._inspection_active:
            self._start_next_inspection()

    def _start_next_inspection(self) -> None:
        if not self._pending_paths:
            self._inspection_active = False
            self.spinner.stop()
            self.spinner.set_visible(False)
            self.open_button.set_sensitive(True)
            return

        path = self._pending_paths.pop(0)
        self._inspection_active = True
        self.open_button.set_sensitive(False)
        self.spinner.set_visible(True)
        self.spinner.start()
        self.drop_area.set_visible(False)
        self._clear_details()
        self.package_icon.set_from_icon_name("package-x-generic-symbolic")
        self.heading.set_text("Inspecting package")
        self.status.set_text(Path(path).name)

        thread = threading.Thread(
            target=self._inspect_in_background,
            args=(path,),
            daemon=True,
        )
        thread.start()

    def _inspect_in_background(self, path: str) -> None:
        info: PackageInfo | None = None
        error: str | None = None
        try:
            info = inspect_package(path)
        except PackageInspectionError as inspection_error:
            error = str(inspection_error)
        except (OSError, RuntimeError, ValueError) as unexpected_error:
            error = f"Unexpected inspection error: {unexpected_error}"
        GLib.idle_add(self._inspection_finished, path, info, error)

    def _inspection_finished(
        self,
        path: str,
        info: PackageInfo | None,
        error: str | None,
    ) -> bool:
        if error is not None:
            self._clear_details()
            self.heading.set_text("Could not inspect package")
            self.status.set_text(error)
            self.package_icon.set_from_icon_name("dialog-error-symbolic")
        elif info is not None:
            self._display_package(info)

        self._inspection_active = False
        self._start_next_inspection()
        return GLib.SOURCE_REMOVE

    def _on_preview_clicked(self, _button: Gtk.Button) -> None:
        if self.current_package_path is None:
            return
        path = self.current_package_path
        self.preview_button.set_sensitive(False)
        self.status.set_text("Resolving dependencies with DNF5…")
        self.spinner.set_visible(True)
        self.spinner.start()
        threading.Thread(
            target=self._resolve_in_background,
            args=(path,),
            daemon=True,
        ).start()

    def _resolve_in_background(self, path: Path) -> None:
        preview: TransactionPreview | None = None
        error: str | None = None
        try:
            preview = resolve_local_rpm(path)
        except TransactionResolutionError as resolution_error:
            error = str(resolution_error)
        GLib.idle_add(self._preview_finished, preview, error)

    def _preview_finished(
        self,
        preview: TransactionPreview | None,
        error: str | None,
    ) -> bool:
        self.spinner.stop()
        self.spinner.set_visible(False)
        self.preview_button.set_sensitive(True)
        if error is not None:
            self.status.set_text(f"Could not resolve transaction: {error}")
            return GLib.SOURCE_REMOVE
        if preview is not None:
            self._show_transaction_preview(preview)
        return GLib.SOURCE_REMOVE

    def _show_transaction_preview(self, preview: TransactionPreview) -> None:
        dialog = Gtk.Dialog(title="Transaction Preview", transient_for=self, modal=True)
        dialog.set_default_size(560, 440)
        dialog.add_button("Close", Gtk.ResponseType.CLOSE)
        content = dialog.get_content_area()
        content.set_spacing(12)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)

        intro = Gtk.Label(
            label="Review the changes DNF5 resolved. Nothing has been installed."
        )
        intro.set_xalign(0)
        intro.set_wrap(True)
        content.append(intro)

        lines = []
        for item in preview.items:
            nevra = (
                f"{item.name}-{item.epoch}:{item.version}-{item.release}."
                f"{item.architecture}"
            )
            lines.append(f"{item.action:<12} {nevra}  [{item.reason}]")
        if preview.warnings:
            lines.extend(("", "Warnings:"))
            lines.extend(f"- {warning}" for warning in preview.warnings)

        download_size = sum(item.download_size for item in preview.items)
        install_size = sum(item.install_size for item in preview.items)
        lines.extend((
            "",
            f"Packages in transaction: {len(preview.items)}",
            f"Download size (reported): {download_size:,} bytes",
            f"Installed size (reported): {install_size:,} bytes",
            "",
            "Preview only. Installation is not available yet.",
        ))

        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        text_view = Gtk.TextView()
        text_view.set_editable(False)
        text_view.set_cursor_visible(False)
        text_view.set_monospace(True)
        text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        text_view.get_buffer().set_text("\n".join(lines))
        scroller.set_child(text_view)
        content.append(scroller)
        dialog.connect("response", lambda window, _response: window.destroy())
        dialog.present()

    def _display_package(self, info: PackageInfo) -> None:
        self._clear_details()
        self.package_icon.set_from_icon_name("package-x-generic-symbolic")
        self.heading.set_text(info.name)
        self.status.set_text(f"{info.version}-{info.release} · {info.architecture}")
        for title, value in (
            ("Version", f"{info.version}-{info.release}"),
            ("Architecture", info.architecture),
            ("Vendor", info.vendor),
            ("Packager", info.packager),
            ("License", info.license),
            ("Signature verification", info.signature),
            ("File", str(info.path)),
        ):
            self._add_row(title, value)

        requirement_text = "\n".join(info.requirements) if info.requirements else "No requirements listed"
        self.requirements_row = Adw.ActionRow(
            title=f"Requires ({len(info.requirements)})",
            subtitle=requirement_text,
        )
        self.requirements_row.set_subtitle_selectable(True)
        self.requirements_group.add(self.requirements_row)
        self.details.set_visible(True)
        self.requirements_group.set_visible(True)
        self.description.set_text(f"{info.summary}\n\n{info.description}")
        self.description.set_visible(True)
        self.drop_area.set_visible(False)
        self.current_package_path = info.path
        self.preview_button.set_visible(True)


class RpmDropApplication(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="io.github.sakibshahariar.RpmDrop",
            flags=Gio.ApplicationFlags.HANDLES_OPEN,
        )
        self.window: RpmDropWindow | None = None

    def do_activate(self) -> None:
        if self.window is None:
            self.window = RpmDropWindow(application=self)
        self.window.present()

    def do_open(self, files: list[Gio.File], _n_files: int, _hint: str) -> None:
        self.do_activate()
        if self.window:
            paths = [file.get_path() for file in files if file.get_path()]
            self.window.inspect_paths(paths)


def main() -> int:
    Adw.init()
    return RpmDropApplication().run(sys.argv)
