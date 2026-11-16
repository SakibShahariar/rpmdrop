"""Smoke-test the installed Nautilus menu provider without launching Nautilus."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import gi

gi.require_version("Nautilus", "4.1")
from gi.repository import Gio


class FakeFileInfo:
    def __init__(self, path: str, scheme: str = "file", directory: bool = False):
        self.path = path
        self.scheme = scheme
        self.directory = directory

    def get_uri_scheme(self):
        return self.scheme

    def is_directory(self):
        return self.directory

    def get_name(self):
        return Path(self.path).name

    def get_location(self):
        return Gio.File.new_for_path(self.path)


def main() -> None:
    extension_path = Path(
        "/usr/share/nautilus-python/extensions/nautilus-rpmdrop.py"
    )
    spec = importlib.util.spec_from_file_location("nautilus_rpmdrop", extension_path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"Could not load Nautilus extension: {extension_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    provider = module.RpmDropMenuProvider()
    selected_paths = [
        "/tmp/first package.rpm",
        "/tmp/বাংলা-package.RPM",
    ]
    selected = [
        FakeFileInfo(selected_paths[0]),
        FakeFileInfo(selected_paths[1]),
        FakeFileInfo("/remote/ignored.rpm", scheme="sftp"),
        FakeFileInfo("/tmp/directory.rpm", directory=True),
        FakeFileInfo("/tmp/not-a-package.txt"),
    ]
    menu_items = provider.get_file_items(selected)
    if len(menu_items) != 1:
        raise SystemExit("The Nautilus provider did not create exactly one menu item.")
    if menu_items[0].get_label() != "Inspect with RpmDrop":
        raise SystemExit("The Nautilus context-menu label is incorrect.")

    app_info = MagicMock()
    fake_gio = SimpleNamespace(
        AppInfo=SimpleNamespace(
            create_from_commandline=MagicMock(return_value=app_info),
            AppInfoCreateFlags=Gio.AppInfoCreateFlags,
        )
    )
    original_gio = module.Gio
    module.Gio = fake_gio
    try:
        locations = [Gio.File.new_for_path(path) for path in selected_paths]
        module.RpmDropMenuProvider._on_activate(menu_items[0], locations)
    finally:
        module.Gio = original_gio

    fake_gio.AppInfo.create_from_commandline.assert_called_once_with(
        "rpmdrop",
        "RpmDrop",
        Gio.AppInfoCreateFlags.SUPPORTS_FILES,
    )
    app_info.launch.assert_called_once_with(locations, None)


if __name__ == "__main__":
    main()
