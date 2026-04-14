# Changelog

## 2026-04-14
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
