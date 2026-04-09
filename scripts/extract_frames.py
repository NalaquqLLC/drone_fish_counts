#!/usr/bin/env python3
"""Extract frames from fish count/species videos at 1 fps as PNG images."""

import subprocess
import sys
from pathlib import Path

BASE_DIR = Path("/mnt/d/AOOS Files")

SOURCES = [
    ("Count only", "count_only"),
    ("Species", "species"),
]


def extract_frames(video_path: Path, output_dir: Path) -> int:
    """Extract frames at 1 fps from a single video. Returns frame count."""
    # Create a subfolder per video (strip extension)
    video_name = video_path.stem
    dest = output_dir / video_name
    dest.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-i", str(video_path),
        "-vf", "fps=1",
        "-q:v", "1",
        str(dest / f"{video_name}_%04d.png"),
        "-y",
        "-loglevel", "warning",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ERROR: {result.stderr.strip()}")
        return 0

    frame_count = len(list(dest.glob("*.png")))
    return frame_count


def main():
    total_frames = 0

    for source_name, output_name in SOURCES:
        source_dir = BASE_DIR / source_name
        output_dir = BASE_DIR / "frames" / output_name

        videos = sorted(source_dir.glob("*.mp4"))
        if not videos:
            print(f"No .mp4 files found in {source_dir}")
            continue

        print(f"\n=== {source_name} ({len(videos)} videos) ===")

        for video in videos:
            print(f"  Processing: {video.name} ...", end=" ", flush=True)
            count = extract_frames(video, output_dir)
            total_frames += count
            print(f"{count} frames")

    print(f"\nDone. Total frames extracted: {total_frames}")


if __name__ == "__main__":
    main()
