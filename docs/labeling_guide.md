# Fish Labeling Guide

Step-by-step instructions for labeling salmon images using the FishLabeler tool.

## What You're Doing

You are drawing bounding boxes around individual fish in underwater video frames and identifying their species. This labeled data will be used to train a YOLO object detection model that can automatically count and classify salmon.

## Getting Started

### 1. Launch the Tool

Double-click **`FishLabeler.exe`** in the root of the drive. Your web browser will open automatically to the setup screen.

If the browser doesn't open, manually go to: `http://localhost:5000`

### 2. Setup Screen

You need to configure three things:

**Input Directory** — Click **Browse** and navigate to the `dataset` folder on this drive. This is where the images are.

**Output Directory** — Click **Browse** and choose where you want your annotations saved. A good choice is to create a new `labels` folder on this drive. The tool will create subfolders inside it automatically.

**Labels** — The five salmon species should already be listed:
- king (Chinook)
- red (Sockeye)
- silver (Coho)
- chum
- pink

You can add, remove, or rename labels if needed.

Click **Start Labeling** when ready.

### 3. Resuming a Previous Session

When you relaunch the tool, it remembers your last session and will take you straight to labeling. If you need to change directories, click the **Setup** link in the top-right corner.

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

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `1`-`5` | Select species (king, red, silver, chum, pink) |
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

**"No images found"** — Make sure your input directory points to a folder containing `.png` (or `.jpg`) files directly, not a folder of subfolders.

**Images look dark/unclear** — Use scroll-to-zoom to inspect details. Some frames from the underwater video will naturally be murky.

**Lost work** — Check the output directory. All annotations are saved as JSON files in the `annotations/` subfolder. YOLO labels are in `labels/`. The `progress.json` file tracks what you've completed.

**Accidentally deleted an image** — Deleted images are moved to the `deleted/` subfolder in your output directory. You can manually move them back to the input folder.
