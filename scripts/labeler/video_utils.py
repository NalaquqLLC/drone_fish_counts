"""Video-to-frame and raw-image conversion utilities for the labeling tool.

Uses a bundled ffmpeg binary via `imageio-ffmpeg` so end users don't need to
install ffmpeg themselves. Falls back to the system `ffmpeg` on PATH if the
package isn't available (useful for dev without the dep installed).

Raw image conversion (DNG, CR2, NEF, etc.) uses `rawpy` + `Pillow`.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Optional

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".mpg", ".mpeg", ".wmv"}
RAW_EXTENSIONS = {".dng", ".cr2", ".cr3", ".nef", ".arw", ".orf", ".rw2", ".raf"}


def get_ffmpeg_exe() -> str:
    """Return a path to an ffmpeg executable.

    Prefer the bundled binary from `imageio-ffmpeg`; fall back to `ffmpeg` on PATH.
    Raises RuntimeError if neither is available.
    """
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        path = shutil.which("ffmpeg")
        if path:
            return path
        raise RuntimeError(
            "ffmpeg is not available. Install the `imageio-ffmpeg` Python "
            "package (pip install imageio-ffmpeg) or a system ffmpeg."
        )


def list_videos(video_dir: Path) -> list[Path]:
    """Return sorted list of video files in a directory (non-recursive)."""
    return sorted(
        p for p in video_dir.iterdir()
        if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
    )


def probe_duration_seconds(ffmpeg: str, video_path: Path) -> Optional[float]:
    """Return duration of a video in seconds, or None if it can't be determined."""
    result = subprocess.run(
        [ffmpeg, "-i", str(video_path)],
        capture_output=True, text=True,
    )
    # ffmpeg writes "Duration: HH:MM:SS.xx" to stderr
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", result.stderr)
    if not match:
        return None
    h, m, s = match.groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


def extract_frames_from_video(
    video_path: Path,
    output_dir: Path,
    fps: float = 1.0,
    ffmpeg: Optional[str] = None,
    progress_callback: Optional[Callable[[int, Optional[float]], None]] = None,
) -> int:
    """Extract frames from a single video into `output_dir / <video_stem>/`.

    Args:
        video_path: path to the video file
        output_dir: parent dir; a subfolder named after the video stem will be created
        fps: frames per second to extract (default 1)
        ffmpeg: ffmpeg executable path (resolved automatically if omitted)
        progress_callback: called periodically with (seconds_processed, duration_seconds)

    Returns the number of frames written.
    """
    ffmpeg = ffmpeg or get_ffmpeg_exe()
    video_name = video_path.stem
    dest = output_dir / video_name
    dest.mkdir(parents=True, exist_ok=True)

    duration = probe_duration_seconds(ffmpeg, video_path)

    cmd = [
        ffmpeg,
        "-i", str(video_path),
        "-vf", f"fps={fps}",
        "-q:v", "1",
        str(dest / f"{video_name}_%04d.png"),
        "-y",
        "-progress", "pipe:1",
        "-nostats",
        "-loglevel", "error",
    ]

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert proc.stdout is not None

    # ffmpeg -progress emits key=value lines; `out_time_ms` is the current
    # output time in microseconds (confusingly named) and `frame` is the
    # running count of frames written.
    frames_written = None
    for line in proc.stdout:
        line = line.strip()
        if not line or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key == "frame":
            try:
                frames_written = int(value)
            except ValueError:
                pass
        elif key == "out_time_ms" and progress_callback is not None:
            try:
                seconds = int(value) / 1_000_000
                progress_callback(seconds, duration)
            except ValueError:
                pass

    proc.wait()
    if proc.returncode != 0:
        err = proc.stderr.read() if proc.stderr else ""
        raise RuntimeError(f"ffmpeg failed on {video_path.name}: {err.strip()}")

    # Count what this run wrote, not what happens to be sitting in the folder —
    # a previous extraction at a different fps leaves stale frames behind.
    if frames_written is not None:
        return frames_written
    return len(list(dest.glob("*.png")))


def extract_batch(
    video_dir: Path,
    output_dir: Path,
    fps: float = 1.0,
    progress_callback: Optional[Callable[[dict], None]] = None,
) -> dict:
    """Extract frames from every video in `video_dir` into `output_dir`.

    Each video gets its own subfolder. The `progress_callback` is invoked with
    a dict describing current status whenever state advances:
        {
            "video_index": int,       # 0-based index of current video
            "video_total": int,
            "video_name": str,
            "video_progress": float,  # 0.0–1.0, or None if duration unknown
            "overall_progress": float,# 0.0–1.0
            "frames_done": int,       # total frames written so far
            "status": "running" | "done" | "error",
            "message": str,
        }

    Returns a summary dict.
    """
    ffmpeg = get_ffmpeg_exe()
    videos = list_videos(video_dir)
    if not videos:
        raise RuntimeError(f"No video files found in {video_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    total = len(videos)
    total_frames = 0

    def emit(video_index: int, video_name: str, video_progress: Optional[float], frames_done: int, status: str, message: str = ""):
        if progress_callback is None:
            return
        vp = 0.0 if video_progress is None else max(0.0, min(1.0, video_progress))
        overall = (video_index + vp) / total if total else 0.0
        progress_callback({
            "video_index": video_index,
            "video_total": total,
            "video_name": video_name,
            "video_progress": vp,
            "overall_progress": overall,
            "frames_done": frames_done,
            "status": status,
            "message": message,
        })

    for i, video in enumerate(videos):
        emit(i, video.name, 0.0, total_frames, "running", f"Processing {video.name}")

        def cb(seconds_processed: float, duration: Optional[float], _i=i, _name=video.name):
            vp = (seconds_processed / duration) if (duration and duration > 0) else None
            emit(_i, _name, vp, total_frames, "running", f"Processing {_name}")

        count = extract_frames_from_video(video, output_dir, fps=fps, ffmpeg=ffmpeg, progress_callback=cb)
        total_frames += count
        emit(i, video.name, 1.0, total_frames, "running", f"Finished {video.name} ({count} frames)")

    emit(total - 1, videos[-1].name, 1.0, total_frames, "done", f"Extracted {total_frames} frames from {total} videos")
    return {"video_count": total, "total_frames": total_frames, "output_dir": str(output_dir)}


def list_raw_images(image_dir: Path) -> list[Path]:
    """Return sorted list of raw image files (DNG, CR2, etc.) in a directory."""
    return sorted(
        p for p in image_dir.iterdir()
        if p.is_file() and p.suffix.lower() in RAW_EXTENSIONS
    )


def convert_raw_image(raw_path: Path, output_dir: Path, quality: int = 95) -> Path:
    """Convert a single raw image to JPG. Returns the output path."""
    import rawpy
    from PIL import Image

    with rawpy.imread(str(raw_path)) as raw:
        rgb = raw.postprocess()
    img = Image.fromarray(rgb)
    dest = output_dir / f"{raw_path.stem}.jpg"
    img.save(str(dest), "JPEG", quality=quality)
    return dest


def convert_raw_batch(
    image_dir: Path,
    output_dir: Path,
    quality: int = 95,
    progress_callback: Optional[Callable[[dict], None]] = None,
) -> dict:
    """Convert all raw images in `image_dir` to JPG in `output_dir`."""
    raws = list_raw_images(image_dir)
    if not raws:
        return {"raw_count": 0, "output_dir": str(output_dir)}

    output_dir.mkdir(parents=True, exist_ok=True)
    total = len(raws)

    for i, raw_path in enumerate(raws):
        if progress_callback:
            progress_callback({
                "raw_index": i,
                "raw_total": total,
                "raw_name": raw_path.name,
                "raw_progress": i / total,
                "message": f"Converting {raw_path.name}",
            })
        convert_raw_image(raw_path, output_dir, quality=quality)

    if progress_callback:
        progress_callback({
            "raw_index": total - 1,
            "raw_total": total,
            "raw_name": raws[-1].name,
            "raw_progress": 1.0,
            "message": f"Converted {total} raw images",
        })

    return {"raw_count": total, "output_dir": str(output_dir)}


def flatten_output(output_dir: Path) -> int:
    """Move all PNGs from per-video subfolders up into `output_dir` itself.

    Useful when you want a single flat directory for the labeler. Existing files
    with name collisions are suffixed to avoid overwrites. Returns the number
    of files moved.
    """
    moved = 0
    for sub in list(output_dir.iterdir()):
        if not sub.is_dir():
            continue
        for img in sub.glob("*.png"):
            dest = output_dir / img.name
            if dest.exists():
                stem, suffix = dest.stem, dest.suffix
                n = 1
                while True:
                    alt = output_dir / f"{stem}_{n}{suffix}"
                    if not alt.exists():
                        dest = alt
                        break
                    n += 1
            img.rename(dest)
            moved += 1
        # Remove now-empty subdir
        try:
            sub.rmdir()
        except OSError:
            pass
    return moved
