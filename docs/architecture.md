# Initial architecture

RpmDrop separates its GTK interface from system-tool adapters.

- **Application/UI** (`rpmdrop.application`): file selection, package details, and user-facing state. It must not execute privileged commands.
- **Package inspection** (`rpmdrop.package`): read-only metadata and signature inspection through RPM tooling. It never installs or modifies packages.
- **Transaction backend** (`rpmdrop.dnf5`): DNF5 daemon D-Bus integration for local RPM goal creation and dependency resolution. It converts DNF5 transaction items into immutable preview records. It must never call `Goal.do_transaction()` during preview.\n- **Transaction execution** (planned): a separate, explicit user-confirmed operation using the same reviewed goal, with revalidation before execution.
- **Privilege boundary** (planned): privileged work must be explicit and mediated by Polkit or the supported DNF5 system service. The GUI must never run as root.

## Installation safety requirements

1. Inspecting a file must never install it or execute code from it.
2. Signature status must distinguish valid, unsigned, unknown-key, and failed verification. Unknown trust must never be displayed as verified.
3. Resolve dependencies with DNF5 and show the complete proposed transaction before confirmation.
4. Require an explicit user action before starting a transaction.
5. Never construct shell command strings from package metadata or file names. Use argument arrays.
6. Never use sudo or run the graphical application as root.
7. Report cancellation, authorization failure, repository/network errors, and package-manager failures distinctly.

## Planned milestones

1. Local RPM inspection and signature reporting.
2. DNF5 transaction preview and explicit install confirmation.
3. Privileged transaction execution with progress and cancellation.
4. Desktop integration, file association, and installation history.

The application currently resolves and previews transactions but does not execute them. The DNF5 daemon may request Polkit authorization when loading a local RPM; this authorizes the daemon operation, not package installation. The GUI remains unprivileged.
