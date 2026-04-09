#!/usr/bin/env python3
"""
Build the Fish Labeling Tool as a standalone .exe using PyInstaller.

Usage:
    pip install pyinstaller flask
    python build_exe.py

Output: dist/FishLabeler.exe
"""

import subprocess
import sys


def main():
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", "FishLabeler",
        "--add-data", "templates:templates",
        "--add-data", "static:static",
        "--hidden-import", "flask",
        "--hidden-import", "jinja2",
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
