#!/usr/bin/env python3
"""Extract frames from video files and convert raw images for labeling.

Thin CLI wrapper around `labeler/video_utils.py`. Most users will drive this
through the FishLabeler app's "Prepare Dataset" screen; use this script when
you want to automate extraction from the command line.

Videos are sampled to PNG frames; raw images (DNG, CR2, NEF, ARW, ...) are
converted 1:1 to JPG. A folder may contain either or both.

Examples:
    # Extract at 1 fps from every video in a folder
    python extract_frames.py --input /path/to/videos --output /path/to/frames

    # Pick a different frame rate and flatten per-video subfolders
    python extract_frames.py -i videos -o frames --fps 2 --flatten

    # Convert a folder of raw stills
    python extract_frames.py -i /path/to/dng --output /path/to/images
"""

import argparse
import sys
from pathlib import Path

# Make the labeler module importable without installing the package.
sys.path.insert(0, str(Path(__file__).parent / "labeler"))

from video_utils import (  # noqa: E402
    convert_raw_batch,
    extract_batch,
    flatten_output,
    list_raw_images,
    list_videos,
    raw_support_available,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-i", "--input", required=True, help="Directory containing video files")
    parser.add_argument("-o", "--output", required=True, help="Directory to write extracted PNGs")
    parser.add_argument("--fps", type=float, default=1.0, help="Frames per second to extract (default: 1)")
    parser.add_argument("--flatten", action="store_true", help="After extraction, move all PNGs into the output root")
    args = parser.parse_args()

    input_dir = Path(args.input).expanduser().resolve()
    output_dir = Path(args.output).expanduser().resolve()

    if not input_dir.is_dir():
        print(f"ERROR: input directory not found: {input_dir}", file=sys.stderr)
        sys.exit(1)

    videos = list_videos(input_dir)
    raws = list_raw_images(input_dir)

    if not videos and not raws:
        print(f"ERROR: no video or raw image files found in {input_dir}", file=sys.stderr)
        sys.exit(1)

    if raws and not raw_support_available():
        print(
            f"ERROR: found {len(raws)} raw image file(s), but raw conversion is "
            "unavailable.\n       Install the dependencies with: pip install rawpy Pillow",
            file=sys.stderr,
        )
        sys.exit(1)

    def on_progress(state):
        pct = int(state["overall_progress"] * 100)
        print(f"  [{pct:3d}%] {state['message']}", flush=True)

    def on_raw_progress(state):
        pct = int(state["raw_progress"] * 100)
        print(f"  [{pct:3d}%] {state['message']}", flush=True)

    frames = 0
    converted = 0
    failed = []
    try:
        if videos:
            summary = extract_batch(input_dir, output_dir, fps=args.fps, progress_callback=on_progress)
            frames = summary["total_frames"]
        if raws:
            result = convert_raw_batch(input_dir, output_dir, progress_callback=on_raw_progress)
            converted = result["raw_count"]
            failed = result["failed"]
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if args.flatten:
        moved = flatten_output(output_dir)
        print(f"Flattened {moved} files into {output_dir}")

    parts = []
    if videos:
        parts.append(f"{len(videos)} video(s), {frames} frames")
    if raws:
        parts.append(f"{converted} raw image(s)")
    print(f"\nDone. {'; '.join(parts)} → {output_dir}")

    if failed:
        print(f"\nSkipped {len(failed)} unreadable raw file(s):", file=sys.stderr)
        for name, err in failed:
            print(f"  {name}: {err}", file=sys.stderr)


if __name__ == "__main__":
    main()
