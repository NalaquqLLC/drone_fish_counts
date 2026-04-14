# Fish Labeling Guide

Step-by-step instructions for labeling salmon images using the FishLabeler tool.

## What You're Doing

You are drawing bounding boxes around individual fish in underwater video frames and identifying their species. This labeled data will be used to train a YOLO object detection model that can automatically count and classify salmon.

## Getting Started

### 1. Launch the Tool

Double-click **`FishLabeler.exe`** in the root of the drive. Your web browser will open automatically to the **home screen**.

If the browser doesn't open, manually go to: `http://localhost:5000`

### 2. Home Screen

The home screen has two options:

- **Prepare Dataset** — Use this if you have raw video files and need to turn them into still images before labeling.
- **Label Imagery** — Use this if you already have a folder of images ready to label.

### 3a. Prepare Dataset (only if you have videos)

1. Click **Prepare Dataset** on the home screen.
2. **Step 1** — Click **Browse** next to "Folder containing your videos" and select the folder with your `.mp4` / `.mov` / `.avi` files.
3. **Step 2** — Click **Browse** next to "Where should the images go?" and pick a destination folder. A new folder will be created if it doesn't exist.
4. **Step 3** — Set frames per second. `1` is a good default for fish counting.
5. Leave **"Put all frames in one folder"** checked (recommended — makes labeling easier).
6. Click **Start Extraction**. A progress bar shows how far along it is.
7. When it finishes, click **Label These Now** to jump straight into the labeler with the new folder pre-filled.

You do not need to install ffmpeg yourself — the tool ships with everything it needs.

### 3b. Label Imagery Setup

From the home screen, click **Label Imagery**. You need to configure two things:

**Input Directory** — Click **Browse** and navigate to the folder that contains your images (e.g., the `dataset` folder, or whatever you chose in **Prepare Dataset**).

**Labels** — The five salmon species should already be listed:
- king (Chinook)
- red (Sockeye)
- silver (Coho)
- chum
- pink

You can add, remove, or rename labels if needed.

The **Output Directory** is managed for you — annotations, YOLO label files, and deleted images are written to a `labeling_output/` folder next to the app. You don't need to set it.

Click **Start Labeling** when ready.

### 4. Resuming a Previous Session

When you relaunch the tool, it remembers your last session. Click **Label Imagery** on the home screen and your previous input folder and labels will be pre-filled — click **Start Labeling** to continue where you left off.

## Labeling Images

### The Interface

- **Left sidebar** — Species labels, annotation list, navigation, and action buttons
- **Center** — The image you're labeling with a canvas for drawing boxes
- **Top bar** — Progress tracker

### Drawing a Bounding Box

1. **Select a species** from the sidebar (or press `1`-`5` on your keyboard)
2. **Click and drag** on the image to draw a rectangle around a fish
3. The box appears with the species label and color

Draw the box as tight as possible around the fish body. Include the full fish from nose to tail, but don't include excessive background.

### Editing Boxes

- **Select a box** — Click on an existing box to select it (highlighted with handles)
- **Move a box** — Click and drag a selected box to reposition it
- **Resize a box** — Drag the corner handles of a selected box
- **Change species** — Select a box, then click a different species button (or press `1`-`5`)
- **Delete a box** — Select a box and press `Delete` or `Backspace`

### Zooming In

For small or hard-to-see fish:

- **Scroll wheel** — Zoom in and out toward your cursor
- **Ctrl + drag** — Pan around when zoomed in
- **Double-click** — Reset zoom to fit the full image

### Navigating Images

- **Left/Right arrow keys** — Move to previous/next image
- **Prev/Next buttons** — Same as arrow keys
- Annotations are auto-saved when you navigate away

### Handling Images Without Fish

Many frames won't have any fish visible. For these:

- Click **Delete Image (No Fish)** or press `D`
- This moves the image to a `deleted/` folder (it's not permanently destroyed)
- The tool automatically advances to the next image

### Saving Your Work

- **Auto-save** — Annotations save automatically when you navigate to another image or close the browser
- **Manual save** — Press `Ctrl+S` or click **Save** at any time
- **Done button** — Click **Done** (or press `Enter`) to mark the current image as completed and move to the next one
- **Skip button** — Press `S` to skip an image you're unsure about and come back later

Your progress is saved to disk, so you can close the tool and come back anytime.

## Annotation Modes

The sidebar has a **Box** / **Polygon** toggle:

- **Box mode** (press `B`) — click and drag a rectangle. Best for most fish.
- **Polygon mode** (press `P`) — click to place vertices around the fish, double-click or press `Enter` to finish, `Esc` to cancel. Use this when you need a tight segmentation mask instead of a rectangle. Select a finished polygon to drag individual vertices.

Box annotations export as YOLO detection format; polygon annotations export as YOLO-seg format. You can mix the two in the same dataset.

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `1`-`5` | Select species (king, red, silver, chum, pink) |
| `B` / `P` | Switch between Box and Polygon annotation modes |
| Left / Right arrow | Previous / next image |
| `Ctrl+S` | Save annotations |
| `Enter` | Mark done and go to next image |
| `S` | Skip image |
| `D` | Delete image (no fish) |
| `Delete` / `Backspace` | Remove selected bounding box |
| `Escape` | Cancel drawing or deselect box |
| Scroll wheel | Zoom in/out |
| `Ctrl` + drag | Pan when zoomed |
| Double-click | Reset zoom |

## Exporting

When you've finished labeling (or want to checkpoint your work):

1. Click the **Export YOLO** button in the sidebar
2. This generates:
   - `labels/*.txt` — YOLO-format label files (one per image)
   - `classes.txt` — List of class names
   - `dataset.yaml` — YOLO training config

These files are written to your output directory and are ready for model training.

## Tips for Good Labels

- **Be consistent** — Label every visible fish in every frame, even if partially obscured
- **Tight boxes** — Draw boxes as close to the fish as possible, not oversized
- **Partial fish** — If a fish is partially in frame, still label the visible portion
- **Overlapping fish** — Draw separate boxes for each individual fish, even if they overlap
- **Uncertain species** — If you can't identify the species, skip the image and come back later
- **Delete aggressively** — Frames with no fish are useless for training; delete them to keep the dataset clean
- **Take breaks** — Labeling fatigue leads to mistakes. Quality matters more than speed.

## Troubleshooting

**Browser didn't open** — Go to `http://localhost:5000` manually.

**"No images found"** — Make sure your input directory points to a folder containing `.png` (or `.jpg`) files directly, not a folder of subfolders. If you prepared the dataset yourself, leave the "Put all frames in one folder" checkbox ticked.

**"No video files found"** (Prepare Dataset) — The tool looks for `.mp4`, `.mov`, `.avi`, `.mkv`, `.m4v`, `.mpg`, `.mpeg`, and `.wmv` files directly in the folder you selected. Make sure you're pointing at the folder, not a parent folder.

**Extraction is slow** — Long videos take a few minutes each. The progress bar updates as ffmpeg processes each video. Leave it running; you can close the browser and reopen it later — the app keeps working in the background.

**Images look dark/unclear** — Use scroll-to-zoom to inspect details. Some frames from the underwater video will naturally be murky.

**Lost work** — Check the `labeling_output/` folder next to the app. All annotations are saved as JSON files in the `annotations/` subfolder. YOLO labels are in `labels/`. The `progress.json` file tracks what you've completed.

**Accidentally deleted an image** — Deleted images are moved to the `deleted/` subfolder in the `labeling_output/` folder. You can manually move them back to the input folder.
