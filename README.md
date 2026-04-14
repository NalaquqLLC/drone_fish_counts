# AOOS Fish Count — Training Data Pipeline

Video-to-image pipeline and labeling tool for building a YOLO object detection model to count and classify salmon from underwater video. Developed for KRITFC / Kuskokwim River monitoring by Nalaquq LLC.

Demo video: https://youtu.be/iGXpuL3Rk6w

## Quick Start (for students)

1. Double-click **`FishLabeler.exe`** in this folder
2. Your browser will open to the **home screen** with two options:
   - **Prepare Dataset** — turn videos into still images
   - **Label Imagery** — draw boxes or polygons on fish

### If you already have images

Click **Label Imagery**, point it at your `dataset` folder, confirm the salmon species labels, and click **Start Labeling**.

### If you only have videos

Click **Prepare Dataset**:

1. Select the folder containing your `.mp4` (or `.mov`, `.avi`, etc.) videos
2. Select where the extracted images should go (the folder will be created if it doesn't exist)
3. Pick a frame rate (1 fps is a good default)
4. Click **Start Extraction** and watch the progress bar
5. When done, click **Label These Now** to jump straight into labeling

See [`docs/labeling_guide.md`](docs/labeling_guide.md) for detailed instructions.

## Directory Structure

```
AOOS Files/
├── FishLabeler.exe        # Labeling tool — double-click to run
├── dataset/               # Extracted frames (PNG) ready for labeling
├── raw_videos/            # Original source video files
│   ├── Count only/        #   Fish counting sample videos
│   └── Species/           #   Species identification sample videos
├── scripts/               # Processing and utility scripts
│   ├── extract_frames.py  #   Command-line frame extraction (optional)
│   └── labeler/           #   Labeling tool source code
├── docs/                  # Documentation
│   └── labeling_guide.md  #   Step-by-step student guide
├── CHANGELOG.md           # Log of all work performed
└── README.md              # This file
```

## Label Classes

| ID | Class | Description |
|----|-------|-------------|
| 0 | king | King (Chinook) salmon |
| 1 | red | Red (Sockeye) salmon |
| 2 | silver | Silver (Coho) salmon |
| 3 | chum | Chum salmon |
| 4 | pink | Pink salmon |

## Frame Extraction

The easiest way to extract frames is through the app's **Prepare Dataset** screen — no installation required. A command-line version is available for automation:

```bash
pip install imageio-ffmpeg
python scripts/extract_frames.py --input /path/to/videos --output /path/to/frames --fps 1
```

Add `--flatten` to move all PNGs into a single output folder (matches the app's default behavior).

`ffmpeg` is bundled with the `imageio-ffmpeg` Python package, so you do **not** need to install `ffmpeg` separately.

## Building the Labeling Tool

The pre-built `FishLabeler.exe` is included and ready to use. See [`docs/build_guide.md`](docs/build_guide.md) for full step-by-step build instructions. Short version:

```powershell
cd C:\path\to\drone_fish_counts\scripts\labeler
python -m pip install -r requirements.txt pyinstaller
python build_exe.py
```

Output: `scripts\labeler\dist\FishLabeler.exe`. The bundled ffmpeg binary from `imageio-ffmpeg` is automatically packaged — end users do not need to install anything.

## Output Format

The labeling tool exports annotations in **YOLO format**:

- `labels/*.txt` — one file per image
  - Boxes: `class_id center_x center_y width height` (normalized 0–1)
  - Polygons: `class_id x1 y1 x2 y2 ...` (YOLO-seg format, normalized 0–1)
- `classes.txt` — class name list
- `dataset.yaml` — YOLO training configuration file

These outputs are ready to use directly with [Ultralytics YOLOv8](https://docs.ultralytics.com/) or similar frameworks.
