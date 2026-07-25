# Changelog

## 2026-07-25
- Fixed `/api/list-dir` returning a 500 when enumerating `/mnt` on WSL — a mapped-but-disconnected drive raised `OSError` and broke the whole folder picker
- Data APIs now return `409 {"needs_setup": true}` instead of a 500 traceback when no session is configured; the labeling page redirects to Setup when it sees that flag, which is what happens when a remembered input folder has moved
- Frame counts now come from ffmpeg's own `frame=` progress output instead of counting PNGs on disk, so re-extracting into a folder that already has frames no longer reports inflated totals
- YOLO export clamps coordinates to 0–1; boxes are clamped at the edges and the center re-derived so it stays consistent with the clamped width/height, and fully offscreen boxes are dropped rather than exported as zero-area
- `/api/delete-image` strips directory components from the filename so a crafted path can't move files from outside the input folder
- Added regression tests for all of the above (50 tests total)

## 2026-04-14
- Added a **home screen** as the app's landing page with two modes: **Prepare Dataset** and **Label Imagery**
- Added a **Prepare Dataset** flow that turns a folder of videos into a folder of still images directly from the UI
  - Browse-based pickers for the video source and image destination folders (same picker used by the labeler setup)
  - Configurable frame rate (default 1 fps) and optional "flatten into one folder" toggle
  - Live progress bar with per-video status, frame count, and overall percentage (uses `ffmpeg -progress` output)
  - Extraction runs on a background thread so the UI stays responsive; status survives page reloads
  - "Label These Now" shortcut jumps straight from a finished extraction into the labeler setup with the output folder pre-filled
- **Bundled ffmpeg** via `imageio-ffmpeg` so end users no longer need to install ffmpeg themselves; `build_exe.py` now collects the binary into the packaged `.exe`
- Refactored `scripts/extract_frames.py` into a shared `labeler/video_utils.py` module; removed the hardcoded `BASE_DIR` and turned the CLI into a flexible `--input / --output / --fps / --flatten` tool
- Added `scripts/labeler/requirements.txt`
- Added **Home**, **Prepare Dataset**, and **Setup** navigation links to the labeler header so users can move between screens without restarting the app
- Updated README and labeling guide to cover the new home screen, Prepare Dataset flow, and segmentation masks
- Added `docs/build_guide.md` with PowerShell instructions for building `FishLabeler.exe` from source, including WSL-path builds, smoke testing, and troubleshooting; README links to it from the Building section
- Output directory is now fixed at `labeling_output/` next to the app/.exe and created automatically
  - Removed the Output Directory picker from the setup screen to prevent users from accidentally selecting a different folder each session
  - Setup screen now shows the output location as a read-only info line
  - Previous session (input dir + labels) is restored automatically on startup
- Added polygon segmentation mask annotation to the labeling tool
  - Box/Polygon mode toggle in the sidebar (<kbd>B</kbd>/<kbd>P</kbd> shortcuts)
  - Click to add vertices, double-click or <kbd>Enter</kbd> to finalize, <kbd>Esc</kbd> to cancel
  - Select a polygon to drag individual vertices for adjustment
  - Polygon annotations export as YOLO-seg format (`class x1 y1 x2 y2 ...`); box annotations continue to export as YOLO detection format

## 2026-04-08
- Created project directory structure: `scripts/`, `docs/`, `frames/`
- Created frame extraction script (`scripts/extract_frames.py`)
- Extracted frames at 1 fps (PNG) from all videos in `Count only/` and `Species/`
- Built standalone labeling tool (`scripts/labeler/`)
  - Setup screen: select input/output dirs, define custom labels
  - Bounding box annotation with draw, resize, move
  - Delete image feature (moves to `deleted/` folder) for removing frames without fish
  - Scroll-to-zoom and pan for inspecting fine detail
  - Progress tracking — saved to disk, survives restarts
  - YOLO format export (labels/*.txt + dataset.yaml + classes.txt)
  - PyInstaller build script for .exe packaging
- Built and packaged `FishLabeler.exe` (Windows standalone, no Python required)
- Replaced tkinter directory picker with built-in browser-based file navigator
- Added auto-restore of last session across restarts
- Merged all frames into flat `dataset/` directory (2,594 images)
- Consolidated source videos into `raw_videos/`
- Cleaned up test artifacts
- Wrote full README and student labeling guide (`docs/labeling_guide.md`)
