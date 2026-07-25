#!/usr/bin/env python3
"""
Build the Fish Labeling Tool as a standalone executable using PyInstaller.

Usage:
    pip install -r requirements.txt pyinstaller
    python build_exe.py

Output: dist/FishLabeler.exe on Windows, dist/FishLabeler elsewhere.

PyInstaller does not cross-compile — it only ever produces a binary for the
platform it runs on. Building the Windows .exe that students download requires
running this on Windows. A Linux or macOS build is still useful for testing the
packaging itself (bundled templates, static files, and ffmpeg).

The ffmpeg binary shipped by `imageio-ffmpeg` is bundled into the executable so
end users do not need to install ffmpeg themselves.
"""

import shutil
import subprocess
import sys
from pathlib import Path

APP_NAME = "FishLabeler"


def output_name() -> str:
    """Name PyInstaller will give the built binary on this platform."""
    return f"{APP_NAME}.exe" if sys.platform == "win32" else APP_NAME


def clean(script_dir: Path) -> None:
    """Remove stale build artifacts so PyInstaller starts fresh.

    Anything in dist/ that isn't this platform's output is left alone. dist/ is
    gitignored, so a Windows .exe sitting there is often the only copy — a Linux
    build has no business deleting it.
    """
    build_dir = script_dir / "build"
    if build_dir.is_dir():
        shutil.rmtree(build_dir)
        print(f"  Removed {build_dir}")

    pycache = script_dir / "__pycache__"
    if pycache.is_dir():
        shutil.rmtree(pycache)
        print(f"  Removed {pycache}")

    dist_dir = script_dir / "dist"
    if dist_dir.is_dir():
        ours = output_name()
        for item in dist_dir.iterdir():
            if item.name == ours:
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
                print(f"  Removed {item}")
            else:
                print(f"  Kept {item.name} (not this platform's output)")

    spec = script_dir / f"{APP_NAME}.spec"
    if spec.exists():
        spec.unlink()
        print(f"  Removed {spec}")


def main():
    script_dir = Path(__file__).resolve().parent

    if sys.platform != "win32":
        print(
            f"NOTE: building on {sys.platform}. PyInstaller cannot cross-compile, so\n"
            f"      this produces a {sys.platform} binary, not a Windows .exe.\n"
            f"      Run this script on Windows to build the .exe for students.\n"
        )

    print("Cleaning old build artifacts ...")
    clean(script_dir)

    # On Windows PyInstaller uses ';' to separate src/dest in --add-data;
    # on macOS/Linux it uses ':'. Pick the right one for whoever is building.
    sep = ";" if sys.platform == "win32" else ":"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--console",
        "--name", APP_NAME,
        f"--add-data=templates{sep}templates",
        f"--add-data=static{sep}static",
        "--hidden-import", "flask",
        "--hidden-import", "jinja2",
        "--hidden-import", "imageio_ffmpeg",
        "--hidden-import", "rawpy",
        "--hidden-import", "rawpy._rawpy",
        # Pulls in the bundled ffmpeg executable that ships with imageio-ffmpeg.
        "--collect-binaries", "imageio_ffmpeg",
        "--collect-data", "imageio_ffmpeg",
        "--collect-binaries", "rawpy",
        "run.py",
    ]

    print(f"\nBuilding {output_name()} ...")
    print(f"Command: {' '.join(cmd)}\n")
    result = subprocess.run(cmd, cwd=str(script_dir))

    if result.returncode != 0:
        print(f"\nBuild failed with exit code {result.returncode}")
        sys.exit(1)

    exe = script_dir / "dist" / output_name()
    if not exe.exists():
        print(f"\nBuild reported success but {exe} is missing")
        sys.exit(1)

    print(f"\nBuild successful! Output: {exe}")
    print(f"Size: {exe.stat().st_size / 1_048_576:.1f} MB")


if __name__ == "__main__":
    main()
