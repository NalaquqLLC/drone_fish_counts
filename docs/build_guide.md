# Building FishLabeler.exe

How to build a fresh `FishLabeler.exe` from source on Windows using PowerShell. The end user only needs the resulting `.exe` — they do **not** need Python or ffmpeg installed.

## Prerequisites

Install these once on the build machine:

1. **Python 3.12 or newer** — [https://www.python.org/downloads/](https://www.python.org/downloads/)
   During installation, check **"Add python.exe to PATH"**.
2. **The repository** — clone or copy `drone_fish_counts/` somewhere on the machine (a native Windows drive like `C:\` is faster than building from a WSL path).

Verify Python is reachable from PowerShell:

```powershell
python --version
```

If that errors, use `py -3 --version` instead and substitute `py -3` for `python` in every command below.

## Build Steps

Open **PowerShell** and run:

```powershell
cd C:\path\to\drone_fish_counts\scripts\labeler
python -m pip install -r requirements.txt pyinstaller
python build_exe.py
```

Replace `C:\path\to\drone_fish_counts` with the actual location of the repo.

### What each command does

| Step | Command | Purpose |
|------|---------|---------|
| 1 | `cd ...\scripts\labeler` | Switch to the labeler source directory |
| 2 | `python -m pip install -r requirements.txt pyinstaller` | Install Flask, imageio-ffmpeg, and PyInstaller |
| 3 | `python build_exe.py` | Run the build script |

### Building from the WSL copy

If the repo lives in WSL instead of a Windows drive, you can point PowerShell at it via the `\\wsl.localhost` UNC path:

```powershell
cd \\wsl.localhost\Ubuntu-20.04\home\nalkuq\drone_fish_counts\scripts\labeler
python -m pip install -r requirements.txt pyinstaller
python build_exe.py
```

Swap `Ubuntu-20.04` for your distro name if different (`wsl -l` lists them). Use `\\wsl.localhost\` — the older `\\wsl$\` form breaks in PowerShell because `$` is treated as a variable prefix. Builds from WSL paths work but are noticeably slower — prefer a native Windows copy for regular builds.

## Output

The build produces a single file:

```
scripts\labeler\dist\FishLabeler.exe
```

This `.exe` is fully self-contained. It bundles:
- Python runtime
- Flask + Jinja2
- All HTML/CSS/JS templates and static assets
- **ffmpeg** (via the `imageio-ffmpeg` Python package)

Copy `FishLabeler.exe` to wherever the end user should run it from (e.g., the root of the data drive). No further installation is required on their machine.

## Testing the Build

Double-click the new `FishLabeler.exe`. A browser should open to `http://localhost:5555` showing the home screen with two cards: **Prepare Dataset** and **Label Imagery**.

Quick smoke test:

1. Click **Prepare Dataset**.
2. Pick a small folder of videos and an empty output folder.
3. Click **Start Extraction** — the progress bar should advance.
4. When done, click **Label These Now** — the labeler should open with the new image folder pre-filled.

If **Prepare Dataset** reports an ffmpeg error, `imageio-ffmpeg` did not get bundled — see **Troubleshooting** below.

## Troubleshooting

**`python` not recognized** — Use the Python launcher instead: `py -3 -m pip ...` and `py -3 build_exe.py`.

**`pip install` fails with SSL / proxy errors** — If you're on a restricted network, you may need to pass `--proxy http://your.proxy:port` to `pip install`, or download the wheels ahead of time.

**PyInstaller warnings about missing modules** — Safe to ignore unless the resulting `.exe` fails to launch. If the `.exe` crashes on startup, run it from PowerShell (`.\dist\FishLabeler.exe`) to see the error message.

**"ffmpeg is not available" when extracting** — The `imageio-ffmpeg` binary wasn't collected. Rebuild after confirming `pip show imageio-ffmpeg` reports it as installed. `build_exe.py` passes `--collect-binaries imageio_ffmpeg` to PyInstaller — if you modified that script, make sure those flags are still there.

**Antivirus flags the `.exe`** — PyInstaller `.exe` files are occasionally flagged as false positives. You may need to whitelist the file or add an exception for the build output folder.

**`.exe` is very large (~80–100 MB)** — Expected. The bundle includes the Python runtime, Flask, and a statically-linked ffmpeg. Do not try to use `--exclude-module` to shrink it unless you know what you're doing.

## Clean Rebuild

If a build misbehaves, delete the caches and try again:

```powershell
Remove-Item -Recurse -Force build, dist, __pycache__, FishLabeler.spec -ErrorAction SilentlyContinue
python build_exe.py
```

(The repo's committed `FishLabeler.spec` will be regenerated.)
