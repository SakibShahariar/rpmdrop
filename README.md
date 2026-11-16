# RpmDrop

A lightweight native GNOME application for inspecting and installing local RPM packages.

RpmDrop is a focused local-package installer for Fedora and other DNF5-based RPM systems. Its design prioritizes a clear review step before any system changes.

## Current implementation

- Open local RPM files from the application or through the desktop's **Open With** integration.
- Inspect package metadata, including version, architecture, vendor, packager, license, summary, and description.
- Review the package's declared RPM requirements.
- See signature and digest verification results without treating unknown signing keys as trusted.
- Keep the GTK interface responsive while package inspection runs in the background.
- Queue multiple files opened together and inspect them one at a time.

The application does **not install packages yet**. Dependency resolution, transaction preview, privileged installation, progress/cancellation, and installation history remain planned work. The requirements shown during inspection are the RPM's declared requirements; they are not yet a DNF5-resolved transaction.

## Initial scope

The first milestone targets Fedora and other DNF5-based RPM systems. Repository browsing, updates, and general package management are intentionally out of scope.

## Technology

- Python and PyGObject
- GTK 4 and libadwaita
- RPM tooling for read-only package inspection
- DNF5 for the planned transaction backend
- Polkit or the supported DNF5 system service for the planned privilege boundary

## Development

The application requires Python 3, GTK 4, libadwaita, PyGObject, and the RPM command-line tools.

Run the application from a checkout with:

```sh
python -m rpmdrop
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for development expectations and [docs/architecture.md](docs/architecture.md) for the security model and planned implementation.

## Status

Early development. Package inspection is implemented, but installation and transaction behavior must be validated on a real DNF5 system before RpmDrop can be considered a usable package installer.

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).
