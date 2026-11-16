# Fedora validation checklist

The GitHub workflow builds the RPM, checks its file manifest, installs/removes it in an isolated Fedora 44 container, runs unit tests, and smoke-tests GTK startup. It does not exercise a live system DNF5 daemon or a desktop Polkit authentication agent.

Before calling RpmDrop ready for normal use, validate these paths on a disposable Fedora 44 system or VM.

## Prerequisites

Install the runtime integration packages:

```sh
sudo dnf install ./rpmdrop-0.1.0-1.fc44.noarch.rpm ./rpmdrop-nautilus-0.1.0-1.fc44.noarch.rpm
```

Confirm that the DNF5 daemon service is available:

```sh
busctl --system list | grep org.rpm.dnf.v0
```

The daemon may be D-Bus activated on first use, so an empty result before activation is not conclusive.

## Manual test cases

- [ ] Launch RpmDrop from the application grid.
- [ ] Open a valid local RPM with **Open RPM**.
- [ ] Drag a local RPM onto the welcome area.
- [ ] Open an RPM through GNOME Files **Open With**.
- [ ] Select multiple RPM files in Files and use **Inspect with RpmDrop**.\n- [ ] Remove `rpmdrop-nautilus` while keeping `rpmdrop` installed; verify the context action disappears. Reinstall it and verify the action returns.
- [ ] Confirm package metadata, declared requirements, and signature classification.
- [ ] Resolve a local RPM and verify that the transaction preview includes all dependencies, actions, architectures, versions, and reported sizes.
- [ ] Close the preview and confirm that no package was installed or removed.
- [ ] Re-open the preview and confirm installation; verify the Polkit authentication prompt appears when required.
- [ ] Confirm a changed transaction or changed warning aborts execution and requires a fresh preview.
- [ ] Confirm an unsigned or unknown-key RPM requires explicit acknowledgement.
- [ ] Confirm digest/signature failures and unavailable/indeterminate verification block installation.
- [ ] Observe download and RPM transaction progress.
- [ ] Cancel during package downloads and verify the cancellation result is reported.
- [ ] Verify the UI explains that cancellation is unavailable after the RPM transaction begins.
- [ ] Verify success and failure dialogs reflect the DNF5 daemon result.
- [ ] Confirm the GUI process runs as the logged-in user, never as root.

## Security notes

Use a disposable VM for installation tests. Prefer a small, known RPM from a trusted source. Do not test failed-signature or unknown-key behavior with important system packages. The installer must never silently treat a digest-only result as a trusted signature.
