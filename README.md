# ASTERISM

Free scientific graphing and statistics for labs. Native desktop app for macOS, Windows and Linux (Qt / PySide6).

## Download

Get the latest version from the [Releases page](https://github.com/EpilepsyCenter/asterism/releases).

| System | File |
|---|---|
| macOS 12 or later, Apple Silicon (M1 and newer) | `ASTERISM-<version>-mac.dmg` |
| Windows 10 or 11, 64-bit | `ASTERISM-<version>-windows-setup.exe` |
| Linux, x86-64 | `ASTERISM-<version>-linux-x86_64.AppImage` |

**Updates install from inside the app.** ASTERISM checks for new versions when it starts (at
most once a day; you can turn this off in **Settings**) and from **Help › Check for Updates**.
When there's a new version, **Install Update** opens an *Updating ASTERISM* window that shows
each step: the download (size and time left, with **Cancel**), the check against the release's
checksums, and then **Restart and Install** or **Later**. Restarting asks you to save your
work; on Windows the installer shows its progress, and ASTERISM opens again by itself. You only
download from the Releases page once.

### The apps are not signed

ASTERISM is free and isn't signed with paid developer certificates, so each system asks
once before opening it. This is expected.

**macOS**

1. Open the `.dmg` and drag **ASTERISM** onto **Applications**.
2. Open ASTERISM from Applications. macOS says it can't check the app; click **Done**.
3. Open **System Settings › Privacy & Security**, scroll down to *"ASTERISM was blocked…"*,
   click **Open Anyway** and confirm with your password.

After that it opens normally, and double-clicking `.asterism` files opens them in ASTERISM.

**Windows**

1. Run `ASTERISM-<version>-windows-setup.exe`. If Windows shows *"Windows protected your
   PC"*, click **More info**, then **Run anyway**.
2. The installer doesn't need administrator rights. It adds ASTERISM to the Start menu,
   opens `.asterism` files with it, and offers it under **Open with** for Prism files.
   Uninstall from **Settings › Apps**.

**Linux**

1. Make the file executable: `chmod +x ASTERISM-*.AppImage` (or Properties › Permissions).
2. Run it. On some distributions Qt needs `libxcb-cursor0`
   (`sudo apt install libxcb-cursor0` on Debian and Ubuntu).

## What it does

- **Data tables** of eight types (column, XY, grouped, contingency, survival, parts of
  whole, multiple variables, nested), with replicates or entered means and errors.
- **Analyses**: t tests and nonparametric tests, one- and two-way ANOVA with multiple
  comparisons, nested analyses, normality and outlier tests, linear and nonlinear
  regression, correlation, contingency tables, survival, transforms and more. Results
  stay live as data change.
- **Graphs** with Prism's range of styles and formatting, significance brackets, and
  **figures** (pages of live panels). Export PDF, SVG, PNG and TIFF, or copy as a vector
  picture to Word, PowerPoint, Keynote or Illustrator.
- **Import** from spreadsheets, lab instruments (QuantStudio qPCR) and **Prism files**
  (`.prism`, `.pzfx`), with their analyses and graph formatting.
- Built-in **help** (Help › ASTERISM Help) and an explanation of how every result is
  calculated.

## Run from source

Needs Python 3.12 or later.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt     # requirements.txt alone runs the app
.venv/bin/python -m asterism [file.asterism]      # or ./start-asterism.sh
```

On Windows: `py -m venv .venv`, `.venv\Scripts\pip install -r requirements-dev.txt`,
`.venv\Scripts\python -m asterism`.

## Test

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m asterism --selftest                      # what the packaged apps check
.venv/bin/python -m asterism --shots /tmp/asterism-shots     # screenshot tour for visual review
```

`tests/test_golden.py` and the `test_*prism*` tests compare statistics with real Prism
output. The Prism projects they come from stay local in `sample_data/` (not in the
repository), so those tests skip elsewhere.

## Build and release

The apps are built with PyInstaller (`packaging/asterism.spec`):

```bash
.venv/bin/pyinstaller packaging/asterism.spec --noconfirm    # dist/ASTERISM.app or dist/ASTERISM/
packaging/make_dmg.sh                                        # macOS disk image
```

The Windows installer (`packaging/windows/asterism.iss`, Inno Setup) and the Linux AppImage
(`packaging/linux/make_appimage.sh`) are built by GitHub Actions. To release: set the
version in `asterism/__init__.py`, push a tag like `v0.1.0`, and the **Release** workflow
builds all three apps, runs `--selftest` on each, and attaches them to a draft release to
publish from the Releases page.

## Design

The design, principles and build history are in [`SPEC.md`](SPEC.md).

## Licence

Free for noncommercial use under the PolyForm Noncommercial License 1.0.0 (see
[`LICENSE`](LICENSE)): personal research and study, and use by universities, hospitals, public
research organisations, charities and government bodies. Commercial use needs a commercial
licence from the copyright holder. Contributions are accepted only if their author agrees
that they may also be offered under other licences.

The apps include Qt (LGPL v3), Lucide icons (ISC) and other
open-source libraries listed in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
