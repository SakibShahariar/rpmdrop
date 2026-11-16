# Initial architecture

RpmDrop separates its GTK interface from system-tool adapters.

- **Application/UI** (`rpmdrop.application`): file selection, package details, transaction preview, and user-facing state. It must not execute privileged commands.
- **Nautilus integration** (`data/nautilus-rpmdrop.py`): a file-manager menu provider that passes selected local RPM files to the unprivileged application through Gio.
- **Package inspection** (`rpmdrop.package`): read-only metadata and signature inspection through RPM tooling. It never installs or modifies packages.
- **Transaction backend** (`rpmdrop.dnf5`): DNF5 daemon D-Bus integration for local RPM goal creation and dependency resolution. It converts DNF5 transaction items into immutable preview records. It must never call `Goal.do_transaction()` during preview.
- **Transaction execution** (planned): a separate, explicit user-confirmed operation using the same reviewed goal, with revalidation before execution.
- **Privilege boundary** (planned): privileged work must be explicit and mediated by Polkit or the supported DNF5 system service. The GUI must never run as root.

## Installation safety requirements

1. Inspecting a file must never install it or execute code from it.
2. Signature status must distinguish trusted, unsigned, unknown-key, digest-failed, signature-failed, unavailable, and indeterminate results. Unknown trust must never be displayed as verified.
3. Unsigned and unknown-key packages require a separate explicit warning acknowledgement before installation; failed digest or signature checks are blocked. Unavailable or indeterminate verification is also blocked until the package can be checked.
4. Resolve dependencies with DNF5 and show the complete proposed transaction before confirmation.
5. Require an explicit user action before starting a transaction.
6. Never construct shell command strings from package metadata or file names. Use argument arrays.
7. Never use sudo or run the graphical application as root.
8. Report cancellation, authorization failure, repository/network errors, and package-manager failures distinctly.

## Planned milestones

1. Local RPM inspection and signature reporting.
2. DNF5 transaction preview and explicit install confirmation.
3. Privileged transaction execution with progress and cancellation.
4. Desktop integration and file association (Nautilus context action implemented; installation history remains planned).

The application currently resolves and previews transactions but does not execute them. The DNF5 daemon may request Polkit authorization when loading a local RPM; this authorizes the daemon operation, not package installation. The GUI remains unprivileged.
