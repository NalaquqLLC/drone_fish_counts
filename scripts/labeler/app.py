"""
Standalone salmon labeling tool for YOLO training data.

Provides a web UI with:
- Setup screen for selecting input/output directories and defining labels
- Image review with delete capability (remove photos without fish)
- Bounding box annotation with user-defined labels
- YOLO-format export
"""

import json
import os
import sys
import uuid
import webbrowser
from pathlib import Path
from threading import Timer

from flask import Flask, abort, jsonify, redirect, render_template, request, send_from_directory, url_for

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


def create_app():
    """Create the Flask labeling application."""
    app = Flask(__name__)
    app.config["SESSION"] = {}  # runtime state: input_dir, output_dir, labels, colors

    def _session():
        return app.config["SESSION"]

    def _is_configured():
        s = _session()
        return bool(s.get("input_dir") and s.get("output_dir") and s.get("labels"))

    def _last_session_path() -> Path:
        """Fixed location to remember the last-used session across restarts."""
        return _app_dir() / "last_session.json"

    def _save_last_session() -> None:
        s = _session()
        _last_session_path().write_text(json.dumps({
            "input_dir": s["input_dir"],
            "output_dir": s["output_dir"],
            "labels": s["labels"],
        }, indent=2))

    def _restore_last_session() -> bool:
        """Try to restore the previous session. Returns True if successful."""
        p = _last_session_path()
        if not p.exists():
            return False
        try:
            cfg = json.loads(p.read_text())
            input_dir = cfg.get("input_dir", "")
            output_dir = cfg.get("output_dir", "")
            labels_raw = cfg.get("labels", {})
            if not input_dir or not Path(input_dir).is_dir() or not labels_raw:
                return False
            labels = {int(k): v for k, v in labels_raw.items()}
            colors = {i: PALETTE[i % len(PALETTE)] for i in range(len(labels))}
            s = _session()
            s["input_dir"] = input_dir
            s["output_dir"] = output_dir
            s["labels"] = labels
            s["colors"] = colors
            # Ensure output dirs exist
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            (Path(output_dir) / "annotations").mkdir(exist_ok=True)
            (Path(output_dir) / "labels").mkdir(exist_ok=True)
            (Path(output_dir) / "deleted").mkdir(exist_ok=True)
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
            "output_dir": s["output_dir"],
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

    def _load_annotations(filename: str) -> list[dict]:
        p = _annotation_path(filename)
        if p.exists():
            return json.loads(p.read_text())
        return []

    def _save_annotations(filename: str, annotations: list[dict]) -> None:
        _annotation_path(filename).write_text(json.dumps(annotations, indent=2))
        _export_yolo(filename, annotations)

    def _export_yolo(filename: str, annotations: list[dict]) -> None:
        """Write YOLO-format label file from annotations."""
        lines = []
        for ann in annotations:
            cls = ann["class_id"]
            x = ann["x"] + ann["w"] / 2
            y = ann["y"] + ann["h"] / 2
            lines.append(f"{cls} {x:.6f} {y:.6f} {ann['w']:.6f} {ann['h']:.6f}")
        _label_path(filename).write_text("\n".join(lines) + "\n" if lines else "")

    # ─── Routes ───

    @app.route("/")
    def index():
        if _is_configured():
            return redirect(url_for("label_page"))
        return redirect(url_for("setup_page"))

    @app.route("/setup")
    def setup_page():
        return render_template("setup.html")

    @app.route("/api/setup", methods=["POST"])
    def api_setup():
        data = request.get_json()
        input_dir = data.get("input_dir", "").strip()
        output_dir = data.get("output_dir", "").strip()
        labels = data.get("labels", [])

        if not input_dir or not Path(input_dir).is_dir():
            return jsonify({"error": f"Input directory not found: {input_dir}"}), 400
        if not output_dir:
            return jsonify({"error": "Output directory is required"}), 400
        if not labels:
            return jsonify({"error": "At least one label is required"}), 400

        # Clean labels
        labels = [l.strip() for l in labels if l.strip()]
        if not labels:
            return jsonify({"error": "At least one non-empty label is required"}), 400

        # Assign colors
        colors = {i: PALETTE[i % len(PALETTE)] for i in range(len(labels))}

        # Set session
        s = _session()
        s["input_dir"] = str(Path(input_dir).resolve())
        s["output_dir"] = str(Path(output_dir).resolve())
        s["labels"] = {i: name for i, name in enumerate(labels)}
        s["colors"] = colors

        # Create output dirs
        _output_path().mkdir(parents=True, exist_ok=True)
        _annotations_dir().mkdir(exist_ok=True)
        _labels_dir().mkdir(exist_ok=True)
        _deleted_dir().mkdir(exist_ok=True)

        _save_config()

        image_count = len(_list_images())
        return jsonify({"status": "ok", "image_count": image_count})

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
                        if d.is_dir() and any(d.iterdir()):
                            dirs.append(str(d))
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

    @app.route("/api/restore", methods=["GET"])
    def api_restore():
        """Check if a previous config exists in a given output dir."""
        output_dir = request.args.get("output_dir", "").strip()
        if not output_dir:
            return jsonify({"found": False})
        config_path = Path(output_dir) / "labeler_config.json"
        if config_path.exists():
            config = json.loads(config_path.read_text())
            return jsonify({"found": True, "config": config})
        return jsonify({"found": False})

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
    def api_image(filename: str):
        if not (_input_path() / filename).is_file():
            abort(404)
        return send_from_directory(str(_input_path()), filename)

    @app.route("/api/annotations/<path:filename>", methods=["GET"])
    def api_get_annotations(filename: str):
        annotations = _load_annotations(filename)
        return jsonify({"filename": filename, "annotations": annotations})

    @app.route("/api/annotations/<path:filename>", methods=["POST"])
    def api_save_annotations(filename: str):
        data = request.get_json()
        annotations = data.get("annotations", [])
        for ann in annotations:
            if "id" not in ann:
                ann["id"] = str(uuid.uuid4())[:8]
        _save_annotations(filename, annotations)
        return jsonify({"status": "saved", "count": len(annotations)})

    @app.route("/api/annotations/<path:filename>/<box_id>", methods=["DELETE"])
    def api_delete_annotation(filename: str, box_id: str):
        annotations = _load_annotations(filename)
        annotations = [a for a in annotations if a.get("id") != box_id]
        _save_annotations(filename, annotations)
        return jsonify({"status": "deleted", "count": len(annotations)})

    @app.route("/api/delete-image/<path:filename>", methods=["POST"])
    def api_delete_image(filename: str):
        """Move an image to the deleted folder (not permanent delete)."""
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
    def api_export():
        """Re-export all annotations to YOLO format."""
        images = _list_images()
        exported = 0
        for img_name in images:
            annotations = _load_annotations(img_name)
            if annotations:
                _export_yolo(img_name, annotations)
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
        return jsonify({"status": "exported", "count": exported})

    return app


def main():
    """Entry point — launch the labeling tool."""
    port = 5000
    app = create_app()

    Timer(1.5, lambda: webbrowser.open(f"http://localhost:{port}")).start()

    print(f"Fish Labeling Tool running at http://localhost:{port}")
    print("Press Ctrl+C to stop.")

    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    main()
