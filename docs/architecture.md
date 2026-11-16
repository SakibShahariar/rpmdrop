# Architecture

RpmDrop separates its GTK interface from system-tool adapters.

- **Application/UI** (`rpmdrop.application`): file selection, package details, transaction preview, explicit installation acknowledgement, progress, cancellation, and result states. It never runs as root.
- **Nautilus integration** (`data/nautilus-rpmdrop.py`): a file-manager menu provider that passes selected local RPM files to the unprivileged application through Gio.
- **Package inspection** (`rpmdrop.package`): read-only metadata and signature inspection through RPM tooling. It never installs or modifies packages.
- **Transaction backend** (`rpmdrop.dnf5`): DNF5 daemon D-Bus integration for local RPM goal creation, dependency resolution, structured preview, revalidation, execution, progress signals, and cancellation.

## Installation safety requirements

1. Inspecting a file must never install it or execute code from it.
2. Signature status must distinguish trusted, unsigned, unknown-key, digest-failed, signature-failed, unavailable, and indeterminate results. Unknown trust must never be displayed as verified.
3. Unsigned and unknown-key packages require a separate explicit warning acknowledgement before installation. Failed digest or signature checks are blocked. Unavailable or indeterminate verification is also blocked.
4. Resolve dependencies with DNF5 and show the complete proposed transaction, including removals, before confirmation.
5. Re-resolve the same DNF5 goal immediately before execution. If package actions, metadata, or warnings differ from the preview, abort and require a new review.
6. Require an explicit user action before starting a transaction. DNF5 handles privileged execution and Polkit authorization; the GUI must remain unprivileged.
7. Never construct shell command strings from package metadata or file names. Use D-Bus methods and argument arrays.
8. Never use sudo or run the graphical application as root.
9. Report authorization failure, repository/network errors, package-manager failures, and cancellation distinctly.
10. DNF5 cancellation is supported during package downloads. Once the RPM transaction begins, DNF5 does not allow cancellation; the UI must communicate this limitation.

## Current milestones

1. Local RPM inspection and signature reporting — implemented.
2. DNF5 transaction resolution and structured preview — implemented; requires real-system validation.
3. Explicitly confirmed installation, transaction revalidation, progress, and download-phase cancellation — implemented; requires real-system validation.
4. Desktop file association and Nautilus context action — implemented; Fedora RPM build/install/removal is covered by CI.
5. Installation history and richer integration tests — planned.

The application and RPM package build in Fedora 44 CI. Automated tests cover package metadata, signature classifications, DNF5 goal resolution/revalidation, transaction execution boundaries, progress conversion, cancellation requests, and package installation/removal. Manual validation with a real DNF5 daemon and Polkit authentication agent is still required before calling the installer production-ready.
