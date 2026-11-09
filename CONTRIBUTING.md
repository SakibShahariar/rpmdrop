# Contributing

Thanks for helping with RpmDrop.

## Development principles

- Keep the first release focused on installing local RPM files.
- Prefer GTK 4 and libadwaita patterns over custom widgets.
- Keep package inspection separate from package installation.
- Never run the GUI as root or invoke privileged commands through a shell.
- Show users what a transaction will change before asking them to authorize it.
- Treat unknown signature trust as unknown, not as success.

## Checks

Install the development extras and run:

```sh
python -m pip install -e '.[dev]'
pytest
ruff check .
```

GUI development additionally requires system GTK 4, libadwaita, and PyGObject packages.

Keep commits focused and use clear conventional commit messages. Include an issue number when a commit resolves a tracked issue.
