# RpmDrop

A lightweight native GNOME application for inspecting and installing local RPM packages.

RpmDrop is designed as a focused local-package installer first, with an architecture that can grow into a broader RPM management application later.

## Goals

- Open local `.rpm` files from the app or the file manager.
- Inspect package metadata before installation.
- Show signature-verification results clearly.
- Resolve dependencies and present the package-manager transaction before making system changes.
- Install through the system package manager with explicit user consent and privileged authorization.
- Report progress and useful errors.
- Keep a local history of actions initiated by RpmDrop.

## Initial scope

The first milestone targets Fedora and other DNF5-based RPM systems. The initial implementation will focus on package inspection and a safe install flow. Repository browsing, updates, and general package management are intentionally out of scope for the first milestone.

## Technology

- Python and PyGObject
- GTK 4 and libadwaita
- DNF5 for system package transactions
- Polkit for privileged operations

## Development

The application requires Python 3, GTK 4, libadwaita, and PyGObject.

Run the application from a checkout with:

```sh
python -m rpmdrop
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for development expectations and [docs/architecture.md](docs/architecture.md) for the initial design.

## Status

Early development. The repository is being bootstrapped; installation and transaction behavior must be validated on a real DNF5 system before being considered production-ready.

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).
