#!/usr/bin/env python3
"""Extract frames from video files as PNG images.

Thin CLI wrapper around `labeler/video_utils.py`. Most users will drive this
through the FishLabeler app's "Prepare Dataset" screen; use this script when
you want to automate extraction from the command line.

Examples:
    # Extract at 1 fps from every video in a folder
    python extract_frames.py --input /path/to/videos --output /path/to/frames

    # Pick a different frame rate and flatten per-video subfolders
    python extract_frames.py -i videos -o frames --fps 2 --flatten
"""

import argparse
import sys
from pathlib import Path

# Make the labeler module importable without installing the package.
sys.path.insert(0, str(Path(__file__).parent / "labeler"))

from video_utils import extract_batch, flatten_output  # noqa: E402


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

    def on_progress(state):
        pct = int(state["overall_progress"] * 100)
        print(f"  [{pct:3d}%] {state['message']}", flush=True)

    try:
        summary = extract_batch(input_dir, output_dir, fps=args.fps, progress_callback=on_progress)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if args.flatten:
        moved = flatten_output(output_dir)
        print(f"Flattened {moved} files into {output_dir}")

    print(f"\nDone. {summary['video_count']} videos, {summary['total_frames']} frames → {summary['output_dir']}")


if __name__ == "__main__":
    main()
