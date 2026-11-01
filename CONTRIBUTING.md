# Contributing to PackScope

PackScope targets Ubuntu and provides a PyQt5 interface for software managed by
APT, Snap, Flatpak, AppImage, and supported developer tools. The application
uses selected modules from bauh; keep their attribution and license intact.

## Report a bug

Open an issue with the PackScope version, Ubuntu version, installation method,
steps to reproduce, expected and actual results, and relevant output from the
operation panel. Remove personal information from logs before posting.

## Propose a change

Explain the user-facing problem and the scope of the change. Keep package
manager operations explicit and preserve the distinction between detected
files, installed packages, and their original installation source.

Run the tests before submitting a pull request:

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -p 'test_packscope*.py'
```

Changes to authentication, installation, updating, or removal should also be
validated in an Ubuntu desktop environment; see `packscope/SAFETY.md`.
