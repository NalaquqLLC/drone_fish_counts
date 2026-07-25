#!/usr/bin/env python3
"""
Build the Fish Labeling Tool as a standalone .exe using PyInstaller.

Usage:
    pip install pyinstaller flask imageio-ffmpeg
    python build_exe.py

Output: dist/FishLabeler.exe

The ffmpeg binary shipped by `imageio-ffmpeg` is bundled into the .exe so end
users do not need to install ffmpeg themselves.
"""

import shutil
import subprocess
import sys
from pathlib import Path


def clean(script_dir: Path) -> None:
    """Remove stale build artifacts so PyInstaller starts fresh."""
    for name in ("build", "dist", "__pycache__"):
        p = script_dir / name
        if p.is_dir():
            shutil.rmtree(p)
            print(f"  Removed {p}")
    spec = script_dir / "FishLabeler.spec"
    if spec.exists():
        spec.unlink()
        print(f"  Removed {spec}")


def main():
    script_dir = Path(__file__).resolve().parent

    print("Cleaning old build artifacts ...")
    clean(script_dir)

    # On Windows PyInstaller uses ';' to separate src/dest in --add-data;
    # on macOS/Linux it uses ':'. Pick the right one for whoever is building.
    sep = ";" if sys.platform == "win32" else ":"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--console",
        "--name", "FishLabeler",
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

    print("\nBuilding FishLabeler.exe ...")
    print(f"Command: {' '.join(cmd)}\n")
    result = subprocess.run(cmd, cwd=str(script_dir))

    if result.returncode == 0:
        exe = script_dir / "dist" / "FishLabeler.exe"
        print(f"\nBuild successful! Output: {exe}")
        print(f"Size: {exe.stat().st_size / 1_048_576:.1f} MB")
    else:
        print(f"\nBuild failed with exit code {result.returncode}")
        sys.exit(1)


if __name__ == "__main__":
    main()
