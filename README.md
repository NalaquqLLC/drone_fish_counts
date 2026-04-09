# AOOS Fish Count — Training Data Pipeline

Video-to-image pipeline and labeling tool for building a YOLO object detection model to count and classify salmon from underwater video. Developed for KRITFC / Kuskokwim River monitoring by Nalaquq LLC.

## Quick Start (for students)

1. Double-click **`FishLabeler.exe`** in this folder
2. Your browser will open to the setup screen
3. Set **Input Directory** to the `dataset` folder on this drive
4. Set **Output Directory** to wherever you want your labels saved (e.g., a new `labels` folder on this drive)
5. Confirm the label classes (king, red, silver, chum, pink) and click **Start Labeling**
6. Label images, delete empty ones, and export to YOLO format when done

See [`docs/labeling_guide.md`](docs/labeling_guide.md) for detailed instructions.

## Directory Structure

```
AOOS Files/
├── FishLabeler.exe        # Labeling tool — double-click to run
├── dataset/               # 2,594 extracted frames (PNG) ready for labeling
├── raw_videos/            # Original source video files
│   ├── Count only/        #   9 fish counting sample videos
│   └── Species/           #   4 species identification sample videos
├── scripts/               # Processing and utility scripts
│   ├── extract_frames.py  #   Video-to-frame extraction (1 fps, PNG)
│   └── labeler/           #   Labeling tool source code
├─��� docs/                  # Documentation
│   └── labeling_guide.md  #   Step-by-step student guide
├── CHANGELOG.md           # Log of all work performed
└── README.md              # This file
```

## About the Data

The `dataset/` folder contains **2,594 PNG images** extracted at 1 frame per second from 13 underwater fish monitoring videos (1920x1080, 24fps). The source videos are in `raw_videos/`.

| Source | Videos | Frames |
|--------|--------|--------|
| Count only (2022 + 2024) | 9 | 2,184 |
| Species (2024) | 4 | 410 |

## Label Classes

| ID | Class | Description |
|----|-------|-------------|
| 0 | king | King (Chinook) salmon |
| 1 | red | Red (Sockeye) salmon |
| 2 | silver | Silver (Coho) salmon |
| 3 | chum | Chum salmon |
| 4 | pink | Pink salmon |

## Frame Extraction

If you need to re-extract frames from the source videos, you will need Python 3 and `ffmpeg` installed:

```bash
python scripts/extract_frames.py
```

This extracts 1 frame per second as PNG from every `.mp4` in `raw_videos/Count only/` and `raw_videos/Species/`.

## Building the Labeling Tool

The pre-built `FishLabeler.exe` is included and ready to use. If you need to rebuild it:

1. Install Python 3.12+ on Windows
2. Install dependencies: `pip install pyinstaller flask`
3. From the `scripts/labeler/` directory, run: `python build_exe.py`
4. The new exe will be in `scripts/labeler/dist/`

## Output Format

The labeling tool exports annotations in **YOLO format**:

- `labels/*.txt` — one file per image, each line: `class_id center_x center_y width height` (normalized 0-1)
- `classes.txt` — class name list
- `dataset.yaml` — YOLO training configuration file

These outputs are ready to use directly with [Ultralytics YOLOv8](https://docs.ultralytics.com/) or similar frameworks.
