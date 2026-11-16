"""Nautilus context-menu integration for RpmDrop."""

from __future__ import annotations

from gi.repository import Gio, GObject, Nautilus


class RpmDropMenuProvider(GObject.GObject, Nautilus.MenuProvider):
    """Offer one safe action for selected local RPM files."""

    def get_file_items(self, files):
        rpm_files = [
            file_info.get_location()
            for file_info in files
            if file_info.get_uri_scheme() == "file"
            and not file_info.is_directory()
            and file_info.get_name().lower().endswith(".rpm")
        ]
        if not rpm_files:
            return []

        item = Nautilus.MenuItem(
            name="RpmDrop::inspect",
            label="Inspect with RpmDrop",
            tip="Review selected RPM packages with RpmDrop",
        )
        item.connect("activate", self._on_activate, rpm_files)
        return [item]

    @staticmethod
    def _on_activate(_menu_item, rpm_files):
        app_info = Gio.AppInfo.create_from_commandline(
            "rpmdrop",
            "RpmDrop",
            Gio.AppInfoCreateFlags.NONE,
        )
        app_info.launch(rpm_files, None)
