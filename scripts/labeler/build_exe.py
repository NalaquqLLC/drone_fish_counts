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

import subprocess
import sys


def main():
    # On Windows PyInstaller uses ';' to separate src/dest in --add-data;
    # on macOS/Linux it uses ':'. Pick the right one for whoever is building.
    sep = ";" if sys.platform == "win32" else ":"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", "FishLabeler",
        f"--add-data=templates{sep}templates",
        f"--add-data=static{sep}static",
        "--hidden-import", "flask",
        "--hidden-import", "jinja2",
        "--hidden-import", "imageio_ffmpeg",
        # Pulls in the bundled ffmpeg executable that ships with imageio-ffmpeg.
        "--collect-binaries", "imageio_ffmpeg",
        "--collect-data", "imageio_ffmpeg",
        "run.py",
    ]

    print("Building FishLabeler.exe ...")
    print(f"Command: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(__import__("pathlib").Path(__file__).parent))

    if result.returncode == 0:
        print("\nBuild successful! Output: dist/FishLabeler.exe")
    else:
        print(f"\nBuild failed with exit code {result.returncode}")
        sys.exit(1)


if __name__ == "__main__":
    main()
