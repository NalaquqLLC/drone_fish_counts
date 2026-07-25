"""
Standalone salmon labeling tool for YOLO training data.

Provides a web UI with:
- Setup screen for selecting the input directory and defining labels
  (outputs are written to a fixed `labeling_output/` folder next to the app)
- Image review with delete capability (remove photos without fish)
- Bounding box and polygon segmentation mask annotation with user-defined labels
- YOLO detection and YOLO-seg format export
"""

import csv
import io
import json
import sys
import threading
import uuid
import webbrowser
from functools import wraps
from pathlib import Path
from threading import Timer

from flask import Flask, abort, jsonify, redirect, render_template, request, send_from_directory, url_for

from video_utils import (
    convert_raw_batch,
    extract_batch,
    flatten_output,
    list_raw_images,
    list_videos,
)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}

# Generate distinct colors for up to 20 labels
PALETTE = [
    "#e6194b", "#3cb44b", "#4363d8", "#f58231", "#f032e6",
    "#42d4f4", "#fabed4", "#469990", "#dcbeff", "#9A6324",
    "#fffac8", "#800000", "#aaffc3", "#808000", "#ffd8b1",
    "#000075", "#a9a9a9", "#e6beff", "#ffe119", "#bfef45",
]


def _app_dir() -> Path:
    """Directory where the app itself lives — used for persisting last session."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def _default_output_dir() -> Path:
    """Fixed output directory, always sibling to the app or .exe."""
    return _app_dir() / "labeling_output"


def _bundle_dir() -> Path:
    """Base directory for bundled assets (templates, static)."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).parent


def create_app():
    """Create the Flask labeling application."""
    import traceback as _tb

    base = _bundle_dir()
    app = Flask(
        __name__,
        template_folder=str(base / "templates"),
        static_folder=str(base / "static"),
    )
    app.config["SESSION"] = {}  # runtime state: input_dir, output_dir, labels, colors

    @app.errorhandler(Exception)
    def handle_exception(e):
        from werkzeug.exceptions import HTTPException
        if isinstance(e, HTTPException):
            return e
        tb = _tb.format_exception(type(e), e, e.__traceback__)
        return f"<h2>Error: {type(e).__name__}</h2><pre>{''.join(tb)}</pre>", 500

    def _session():
        return app.config["SESSION"]

    def _is_configured():
        s = _session()
        return bool(s.get("input_dir") and s.get("output_dir") and s.get("labels"))

    def _requires_setup(fn):
        """Reject API calls made before a session exists.

        Without this the session lookups below raise a bare KeyError and the
        user gets a Python traceback instead of a pointer back to Setup. This
        happens in normal use whenever a remembered input folder has moved.
        """
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not _is_configured():
                return jsonify({
                    "error": "No labeling session is configured. Run Setup first.",
                    "needs_setup": True,
                }), 409
            return fn(*args, **kwargs)
        return wrapper

    def _last_session_path() -> Path:
        """Fixed location to remember the last-used session across restarts."""
        return _app_dir() / "last_session.json"

    def _save_last_session() -> None:
        s = _session()
        _last_session_path().write_text(json.dumps({
            "input_dir": s["input_dir"],
            "labels": s["labels"],
        }, indent=2))

    def _ensure_output_dirs(output_dir: Path) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "annotations").mkdir(exist_ok=True)
        (output_dir / "labels").mkdir(exist_ok=True)
        (output_dir / "points").mkdir(exist_ok=True)
        (output_dir / "deleted").mkdir(exist_ok=True)

    def _restore_last_session() -> bool:
        """Try to restore the previous session. Returns True if successful."""
        p = _last_session_path()
        if not p.exists():
            return False
        try:
            cfg = json.loads(p.read_text())
            input_dir = cfg.get("input_dir", "")
            labels_raw = cfg.get("labels", {})
            if not input_dir or not Path(input_dir).is_dir() or not labels_raw:
                return False
            labels = {int(k): v for k, v in labels_raw.items()}
            colors = {i: PALETTE[i % len(PALETTE)] for i in range(len(labels))}
            output_dir = _default_output_dir()
            s = _session()
            s["input_dir"] = input_dir
            s["output_dir"] = str(output_dir)
            s["labels"] = labels
            s["colors"] = colors
            _ensure_output_dirs(output_dir)
            return True
        except (json.JSONDecodeError, KeyError, ValueError):
            return False

    # Auto-restore previous session on startup
    _restore_last_session()

    def _input_path():
        return Path(_session()["input_dir"])

    def _output_path():
        return Path(_session()["output_dir"])

    def _annotations_dir():
        return _output_path() / "annotations"

    def _labels_dir():
        return _output_path() / "labels"

    def _points_dir():
        return _output_path() / "points"

    def _deleted_dir():
        return _output_path() / "deleted"

    def _list_images() -> list[str]:
        """Return sorted list of image filenames in input directory."""
        files = []
        for f in sorted(_input_path().iterdir()):
            if f.suffix.lower() in IMAGE_EXTENSIONS and f.is_file():
                files.append(f.name)
        return files

    def _progress_path() -> Path:
        return _output_path() / "progress.json"

    def _config_path() -> Path:
        return _output_path() / "labeler_config.json"

    def _load_progress() -> dict:
        p = _progress_path()
        if p.exists():
            return json.loads(p.read_text())
        return {"completed": [], "skipped": [], "deleted": []}

    def _save_progress(progress: dict) -> None:
        _progress_path().write_text(json.dumps(progress, indent=2))

    def _save_config() -> None:
        """Persist session config so it can be restored."""
        s = _session()
        config_data = json.dumps({
            "input_dir": s["input_dir"],
            "labels": s["labels"],
        }, indent=2)
        _config_path().write_text(config_data)
        _save_last_session()

    def _load_config() -> dict | None:
        p = _config_path()
        if p.exists():
            return json.loads(p.read_text())
        return None

    def _annotation_path(filename: str) -> Path:
        stem = Path(filename).stem
        return _annotations_dir() / f"{stem}.json"

    def _label_path(filename: str) -> Path:
        stem = Path(filename).stem
        return _labels_dir() / f"{stem}.txt"

    def _point_path(filename: str) -> Path:
        stem = Path(filename).stem
        return _points_dir() / f"{stem}.txt"

    def _load_annotations(filename: str) -> list[dict]:
        p = _annotation_path(filename)
        if p.exists():
            return json.loads(p.read_text())
        return []

    def _save_annotations(filename: str, annotations: list[dict]) -> None:
        _annotation_path(filename).write_text(json.dumps(annotations, indent=2))
        _export_yolo(filename, annotations)
        _export_points(filename, annotations)

    def _clamp(v: float) -> float:
        """Constrain a normalized coordinate to [0, 1].

        Annotations dragged past the image edge would otherwise export
        out-of-range values, which YOLO trainers reject.
        """
        return max(0.0, min(1.0, float(v)))

    def _export_yolo(filename: str, annotations: list[dict]) -> None:
        """Write YOLO-format label file from annotations.

        Box annotations emit YOLO detection format: `class cx cy w h`.
        Polygon annotations emit YOLO-seg format: `class x1 y1 x2 y2 ...`.

        Point annotations are counting marks, not detections — YOLO has no
        representation for them and a zero-area box would poison training, so
        they are written separately by `_export_points`.
        """
        lines = []
        for ann in annotations:
            cls = ann["class_id"]
            if ann.get("type") == "point":
                continue
            if ann.get("type") == "polygon":
                pts = ann.get("points", [])
                if len(pts) < 3:
                    continue
                coords = " ".join(f"{_clamp(p[0]):.6f} {_clamp(p[1]):.6f}" for p in pts)
                lines.append(f"{cls} {coords}")
            else:
                # Clamp the box to the image first, then derive the center so
                # the center stays consistent with the clamped width/height.
                x0 = _clamp(ann["x"])
                y0 = _clamp(ann["y"])
                x1 = _clamp(ann["x"] + ann["w"])
                y1 = _clamp(ann["y"] + ann["h"])
                w = x1 - x0
                h = y1 - y0
                if w <= 0 or h <= 0:
                    continue
                lines.append(f"{cls} {x0 + w / 2:.6f} {y0 + h / 2:.6f} {w:.6f} {h:.6f}")
        _label_path(filename).write_text("\n".join(lines) + "\n" if lines else "")

    def _export_points(filename: str, annotations: list[dict]) -> None:
        """Write point annotations as `class_id x y` (normalized), one per line."""
        lines = [
            f"{ann['class_id']} {_clamp(ann['x']):.6f} {_clamp(ann['y']):.6f}"
            for ann in annotations
            if ann.get("type") == "point"
        ]
        _point_path(filename).write_text("\n".join(lines) + "\n" if lines else "")

    def _count_annotations(annotations: list[dict]) -> dict[int, dict[str, int]]:
        """Tally annotations per class, split by type."""
        tally: dict[int, dict[str, int]] = {}
        for ann in annotations:
            kind = ann.get("type") or "box"
            if kind not in ("box", "polygon", "point"):
                kind = "box"
            row = tally.setdefault(ann["class_id"], {"box": 0, "polygon": 0, "point": 0})
            row[kind] += 1
        return tally

    # ─── Prepare-dataset state (single-job, in-memory) ───
    prepare_state: dict = {
        "status": "idle",       # idle | running | done | error
        "video_index": 0,
        "video_total": 0,
        "video_name": "",
        "video_progress": 0.0,
        "overall_progress": 0.0,
        "frames_done": 0,
        "message": "",
        "output_dir": "",
    }
    prepare_lock = threading.Lock()

    def _update_prepare(**kwargs):
        with prepare_lock:
            prepare_state.update(kwargs)

    # ─── Routes ───

    @app.route("/")
    def index():
        return render_template("home.html")

    @app.route("/setup")
    def setup_page():
        # Optional ?input=... pre-fills the input directory (used when jumping
        # here from the prepare-dataset flow).
        prefill_input = request.args.get("input", "").strip()
        return render_template("setup.html", prefill_input=prefill_input)

    @app.route("/prepare")
    def prepare_page():
        return render_template("prepare.html")

    @app.route("/api/prepare/start", methods=["POST"])
    def api_prepare_start():
        data = request.get_json() or {}
        input_dir = (data.get("input_dir") or "").strip()
        output_dir = (data.get("output_dir") or "").strip()
        fps = float(data.get("fps") or 1.0)
        flatten = bool(data.get("flatten", True))

        if not input_dir or not Path(input_dir).is_dir():
            return jsonify({"error": f"Folder not found: {input_dir}"}), 400
        if not output_dir:
            return jsonify({"error": "Output folder is required"}), 400
        if fps <= 0:
            return jsonify({"error": "Frames per second must be greater than 0"}), 400

        in_path = Path(input_dir).resolve()
        out_path = Path(output_dir).resolve()

        videos = list_videos(in_path)
        raws = list_raw_images(in_path)
        if not videos and not raws:
            return jsonify({"error": f"No video or raw image files found in {in_path}"}), 400

        total_items = len(videos) + len(raws)

        with prepare_lock:
            if prepare_state["status"] == "running":
                return jsonify({"error": "An extraction is already running"}), 409
            prepare_state.update({
                "status": "running",
                "video_index": 0,
                "video_total": total_items,
                "video_name": "",
                "video_progress": 0.0,
                "overall_progress": 0.0,
                "frames_done": 0,
                "message": "Starting…",
                "output_dir": str(out_path),
            })

        def on_video_progress(state: dict) -> None:
            _update_prepare(**state, output_dir=str(out_path))

        def worker():
            try:
                out_path.mkdir(parents=True, exist_ok=True)
                total_frames = 0

                if videos:
                    video_summary = extract_batch(in_path, out_path, fps=fps, progress_callback=on_video_progress)
                    total_frames += video_summary["total_frames"]

                if raws:
                    def on_raw_progress(state: dict) -> None:
                        ri = state["raw_index"]
                        offset = len(videos)
                        overall = (offset + ri + state["raw_progress"]) / total_items
                        _update_prepare(
                            video_index=offset + ri,
                            video_total=total_items,
                            video_name=state["raw_name"],
                            video_progress=state["raw_progress"],
                            overall_progress=overall,
                            frames_done=total_frames + ri,
                            status="running",
                            message=state["message"],
                            output_dir=str(out_path),
                        )

                    result = convert_raw_batch(in_path, out_path, progress_callback=on_raw_progress)
                    total_frames += result["raw_count"]

                if flatten:
                    _update_prepare(status="running", message="Organizing files…")
                    flatten_output(out_path)

                parts = []
                if videos:
                    parts.append(f"{len(videos)} video{'s' if len(videos) != 1 else ''}")
                if raws:
                    parts.append(f"{len(raws)} raw image{'s' if len(raws) != 1 else ''}")
                summary = " and ".join(parts)
                _update_prepare(
                    status="done",
                    message=f"Done! Processed {summary}. Images saved to {out_path}",
                    output_dir=str(out_path),
                    overall_progress=1.0,
                    frames_done=total_frames,
                )
            except Exception as e:
                _update_prepare(status="error", message=str(e))

        threading.Thread(target=worker, daemon=True).start()
        return jsonify({"status": "started", "video_count": len(videos), "raw_count": len(raws)})

    @app.route("/api/prepare/status", methods=["GET"])
    def api_prepare_status():
        with prepare_lock:
            return jsonify(dict(prepare_state))

    @app.route("/api/setup", methods=["POST"])
    def api_setup():
        data = request.get_json()
        input_dir = data.get("input_dir", "").strip()
        labels = data.get("labels", [])

        if not input_dir or not Path(input_dir).is_dir():
            return jsonify({"error": f"Input directory not found: {input_dir}"}), 400
        if not labels:
            return jsonify({"error": "At least one label is required"}), 400

        labels = [l.strip() for l in labels if l.strip()]
        if not labels:
            return jsonify({"error": "At least one non-empty label is required"}), 400

        colors = {i: PALETTE[i % len(PALETTE)] for i in range(len(labels))}
        output_dir = _default_output_dir()

        s = _session()
        s["input_dir"] = str(Path(input_dir).resolve())
        s["output_dir"] = str(output_dir)
        s["labels"] = {i: name for i, name in enumerate(labels)}
        s["colors"] = colors

        _ensure_output_dirs(output_dir)
        _save_config()

        image_count = len(_list_images())
        return jsonify({"status": "ok", "image_count": image_count, "output_dir": str(output_dir)})

    @app.route("/api/list-dir", methods=["POST"])
    def api_list_dir():
        """List directories at a given path for the built-in file browser."""
        data = request.get_json()
        path = data.get("path", "").strip()

        if not path:
            # Return system roots
            if sys.platform == "win32":
                import string
                drives = []
                for letter in string.ascii_uppercase:
                    dp = f"{letter}:\\"
                    if Path(dp).exists():
                        drives.append(dp)
                return jsonify({"path": "", "dirs": drives, "is_root": True})
            else:
                # On Linux/WSL, show /mnt/ drives + home
                dirs = []
                mnt = Path("/mnt")
                if mnt.is_dir():
                    for d in sorted(mnt.iterdir()):
                        # Mapped-but-disconnected drives raise OSError on access
                        # (e.g. ENODEV under WSL) — skip anything unreadable.
                        try:
                            if d.is_dir() and any(d.iterdir()):
                                dirs.append(str(d))
                        except OSError:
                            continue
                home = Path.home()
                if home.is_dir():
                    dirs.append(str(home))
                return jsonify({"path": "/", "dirs": dirs, "is_root": True})

        p = Path(path)
        if not p.is_dir():
            return jsonify({"error": f"Not a directory: {path}"}), 400

        dirs = []
        try:
            for item in sorted(p.iterdir()):
                if item.is_dir() and not item.name.startswith("."):
                    dirs.append(str(item))
        except PermissionError:
            pass

        parent = str(p.parent) if str(p.parent) != str(p) else ""
        return jsonify({"path": str(p), "dirs": dirs, "parent": parent, "is_root": False})

    @app.route("/api/current-config", methods=["GET"])
    def api_current_config():
        """Return the active session config, if any, so the setup page can pre-fill."""
        s = _session()
        output_dir = str(_default_output_dir())
        if _is_configured():
            return jsonify({
                "found": True,
                "config": {
                    "input_dir": s["input_dir"],
                    "labels": s["labels"],
                },
                "output_dir": output_dir,
            })
        return jsonify({"found": False, "output_dir": output_dir})

    @app.route("/label")
    def label_page():
        if not _is_configured():
            return redirect(url_for("setup_page"))
        s = _session()
        return render_template(
            "label.html",
            labels=s["labels"],
            colors=s["colors"],
            input_dir=s["input_dir"],
            output_dir=s["output_dir"],
        )

    @app.route("/api/images")
    @_requires_setup
    def api_images():
        images = _list_images()
        progress = _load_progress()
        return jsonify({
            "images": images,
            "total": len(images),
            "completed": progress.get("completed", []),
            "skipped": progress.get("skipped", []),
            "deleted": progress.get("deleted", []),
        })

    @app.route("/api/image/<path:filename>")
    @_requires_setup
    def api_image(filename: str):
        if not (_input_path() / filename).is_file():
            abort(404)
        return send_from_directory(str(_input_path()), filename)

    @app.route("/api/annotations/<path:filename>", methods=["GET"])
    @_requires_setup
    def api_get_annotations(filename: str):
        annotations = _load_annotations(filename)
        return jsonify({"filename": filename, "annotations": annotations})

    @app.route("/api/annotations/<path:filename>", methods=["POST"])
    @_requires_setup
    def api_save_annotations(filename: str):
        data = request.get_json()
        annotations = data.get("annotations", [])
        for ann in annotations:
            if "id" not in ann:
                ann["id"] = str(uuid.uuid4())[:8]
        _save_annotations(filename, annotations)
        return jsonify({"status": "saved", "count": len(annotations)})

    @app.route("/api/annotations/<path:filename>/<box_id>", methods=["DELETE"])
    @_requires_setup
    def api_delete_annotation(filename: str, box_id: str):
        annotations = _load_annotations(filename)
        annotations = [a for a in annotations if a.get("id") != box_id]
        _save_annotations(filename, annotations)
        return jsonify({"status": "deleted", "count": len(annotations)})

    @app.route("/api/delete-image/<path:filename>", methods=["POST"])
    @_requires_setup
    def api_delete_image(filename: str):
        """Move an image to the deleted folder (not permanent delete)."""
        # Strip any directory component so a crafted path can't move files
        # from outside the input folder.
        filename = Path(filename).name
        if not filename:
            return jsonify({"error": "File not found"}), 404

        src = _input_path() / filename
        if not src.is_file():
            return jsonify({"error": "File not found"}), 404

        dest = _deleted_dir() / filename
        src.rename(dest)

        # Remove any annotations
        ann_path = _annotation_path(filename)
        if ann_path.exists():
            ann_path.unlink()
        lbl_path = _label_path(filename)
        if lbl_path.exists():
            lbl_path.unlink()

        # Track in progress
        progress = _load_progress()
        for key in ("completed", "skipped"):
            if filename in progress.get(key, []):
                progress[key].remove(filename)
        progress.setdefault("deleted", []).append(filename)
        _save_progress(progress)

        return jsonify({"status": "deleted", "filename": filename})

    @app.route("/api/progress", methods=["GET"])
    @_requires_setup
    def api_get_progress():
        images = _list_images()
        progress = _load_progress()
        return jsonify({
            "total": len(images),
            "completed": len(progress.get("completed", [])),
            "skipped": len(progress.get("skipped", [])),
            "deleted": len(progress.get("deleted", [])),
            "remaining": len(images)
            - len(progress.get("completed", []))
            - len(progress.get("skipped", [])),
        })

    @app.route("/api/progress/<path:filename>", methods=["POST"])
    @_requires_setup
    def api_update_progress(filename: str):
        data = request.get_json()
        status = data.get("status")
        progress = _load_progress()
        for key in ("completed", "skipped"):
            if filename in progress.get(key, []):
                progress[key].remove(filename)
        if status in ("completed", "skipped"):
            progress.setdefault(status, []).append(filename)
        _save_progress(progress)
        return jsonify({"status": "updated"})

    @app.route("/api/export", methods=["POST"])
    @_requires_setup
    def api_export():
        """Re-export all annotations to YOLO format, points, and counts."""
        images = _list_images()
        exported = 0
        per_image_counts: list[tuple[str, dict[int, dict[str, int]]]] = []
        for img_name in images:
            annotations = _load_annotations(img_name)
            if annotations:
                _export_yolo(img_name, annotations)
                _export_points(img_name, annotations)
                per_image_counts.append((img_name, _count_annotations(annotations)))
                exported += 1

        s = _session()
        labels = s["labels"]

        # Write classes.txt
        classes_path = _output_path() / "classes.txt"
        classes_path.write_text(
            "\n".join(labels[i] for i in sorted(labels)) + "\n"
        )
        # Write dataset.yaml for YOLO training
        yaml_path = _output_path() / "dataset.yaml"
        yaml_path.write_text(
            f"path: {_output_path()}\n"
            f"train: {_input_path()}\n"
            f"val: {_input_path()}\n\n"
            f"names:\n"
            + "".join(f"  {i}: {name}\n" for i, name in sorted(labels.items()))
        )

        # Per-image tally so counting work is usable without parsing labels.
        # Points, boxes and masks are broken out because a point is a count
        # while the other two are training annotations that happen to imply one.
        totals = {i: 0 for i in labels}
        point_totals = {i: 0 for i in labels}
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(["image", "class_id", "class_name", "points", "boxes", "polygons", "total"])
        for img_name, tally in per_image_counts:
            for class_id in sorted(tally):
                c = tally[class_id]
                total = c["point"] + c["box"] + c["polygon"]
                writer.writerow([
                    img_name, class_id, labels.get(class_id, f"class_{class_id}"),
                    c["point"], c["box"], c["polygon"], total,
                ])
                if class_id in totals:
                    totals[class_id] += total
                    point_totals[class_id] += c["point"]
        (_output_path() / "counts.csv").write_text(buf.getvalue())

        return jsonify({
            "status": "exported",
            "count": exported,
            "totals": {labels[i]: totals[i] for i in sorted(totals)},
            "point_totals": {labels[i]: point_totals[i] for i in sorted(point_totals)},
        })

    return app


def main():
    """Entry point — launch the labeling tool."""
    import logging

    port = 5555
    log_file = _app_dir() / "fishlabeler.log"
    logging.basicConfig(
        filename=str(log_file),
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger = logging.getLogger("fishlabeler")

    try:
        app = create_app()
    except Exception:
        logger.exception("Failed to create app")
        raise

    logger.info("Templates: %s", app.template_folder)
    logger.info("Static: %s", app.static_folder)
    logger.info("App dir: %s", _app_dir())
    logger.info("Bundle dir: %s", _bundle_dir())

    Timer(1.5, lambda: webbrowser.open(f"http://localhost:{port}")).start()

    print(f"Fish Labeling Tool running at http://localhost:{port}")
    print("Press Ctrl+C to stop.")

    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    main()
