"""Tests for the Fish Labeling Tool Flask application.

Exercises every route to identify 500 errors and verify correct behavior.
"""

import json
from pathlib import Path

import pytest


# ── Home / landing page ──

class TestHomePage:
    def test_home_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_home_contains_title(self, client):
        resp = client.get("/")
        assert b"Fish Labeling Tool" in resp.data


# ── Setup page ──

class TestSetupPage:
    def test_setup_page_returns_200(self, client):
        resp = client.get("/setup")
        assert resp.status_code == 200

    def test_setup_page_with_prefill(self, client):
        resp = client.get("/setup?input=/some/path")
        assert resp.status_code == 200

    def test_setup_page_renders_template(self, client):
        resp = client.get("/setup")
        assert b"Label Imagery" in resp.data


# ── Prepare page ──

class TestPreparePage:
    def test_prepare_page_returns_200(self, client):
        resp = client.get("/prepare")
        assert resp.status_code == 200

    def test_prepare_page_renders_template(self, client):
        resp = client.get("/prepare")
        assert b"Prepare Dataset" in resp.data


# ── API: setup ──

class TestApiSetup:
    def test_setup_valid(self, client, tmp_dirs):
        resp = client.post("/api/setup", json={
            "input_dir": str(tmp_dirs["input"]),
            "labels": ["king", "red"],
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["image_count"] == 3

    def test_setup_missing_input_dir(self, client):
        resp = client.post("/api/setup", json={
            "input_dir": "",
            "labels": ["king"],
        })
        assert resp.status_code == 400

    def test_setup_nonexistent_dir(self, client):
        resp = client.post("/api/setup", json={
            "input_dir": "/nonexistent/path/abc123",
            "labels": ["king"],
        })
        assert resp.status_code == 400

    def test_setup_no_labels(self, client, tmp_dirs):
        resp = client.post("/api/setup", json={
            "input_dir": str(tmp_dirs["input"]),
            "labels": [],
        })
        assert resp.status_code == 400

    def test_setup_empty_labels(self, client, tmp_dirs):
        resp = client.post("/api/setup", json={
            "input_dir": str(tmp_dirs["input"]),
            "labels": ["", "  "],
        })
        assert resp.status_code == 400


# ── API: current-config ──

class TestApiCurrentConfig:
    def test_no_config_initially(self, client):
        resp = client.get("/api/current-config")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["found"] is False

    def test_config_after_setup(self, configured_client):
        resp = configured_client.get("/api/current-config")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["found"] is True
        assert "king" in data["config"]["labels"].values()


# ── Label page ──

class TestLabelPage:
    def test_label_redirects_without_setup(self, client):
        resp = client.get("/label")
        assert resp.status_code == 302

    def test_label_page_after_setup(self, configured_client):
        resp = configured_client.get("/label")
        assert resp.status_code == 200


# ── API: images ──

class TestApiImages:
    def test_list_images(self, configured_client):
        resp = configured_client.get("/api/images")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 3
        assert "frame_001.png" in data["images"]

    def test_serve_image(self, configured_client):
        resp = configured_client.get("/api/image/frame_001.png")
        assert resp.status_code == 200
        assert resp.content_type.startswith("image/")

    def test_serve_missing_image(self, configured_client):
        resp = configured_client.get("/api/image/nonexistent.png")
        assert resp.status_code == 404


# ── API: annotations ──

class TestApiAnnotations:
    def test_get_empty_annotations(self, configured_client):
        resp = configured_client.get("/api/annotations/frame_001.png")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["annotations"] == []

    def test_save_and_get_box_annotation(self, configured_client):
        annotation = {
            "class_id": 0,
            "x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4,
            "type": "box",
        }
        resp = configured_client.post("/api/annotations/frame_001.png", json={
            "annotations": [annotation],
        })
        assert resp.status_code == 200
        assert resp.get_json()["count"] == 1

        resp = configured_client.get("/api/annotations/frame_001.png")
        data = resp.get_json()
        assert len(data["annotations"]) == 1
        assert data["annotations"][0]["class_id"] == 0
        assert "id" in data["annotations"][0]

    def test_save_polygon_annotation(self, configured_client):
        annotation = {
            "class_id": 1,
            "type": "polygon",
            "points": [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]],
        }
        resp = configured_client.post("/api/annotations/frame_002.png", json={
            "annotations": [annotation],
        })
        assert resp.status_code == 200

    def test_delete_annotation(self, configured_client):
        annotation = {"class_id": 0, "x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4, "id": "test123"}
        configured_client.post("/api/annotations/frame_001.png", json={
            "annotations": [annotation],
        })

        resp = configured_client.delete("/api/annotations/frame_001.png/test123")
        assert resp.status_code == 200
        assert resp.get_json()["count"] == 0


# ── API: delete image ──

class TestApiDeleteImage:
    def test_delete_image(self, configured_client):
        resp = configured_client.post("/api/delete-image/frame_003.png")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "deleted"

    def test_delete_nonexistent_image(self, configured_client):
        resp = configured_client.post("/api/delete-image/nope.png")
        assert resp.status_code == 404


# ── API: progress tracking ──

class TestApiProgress:
    def test_get_progress(self, configured_client):
        resp = configured_client.get("/api/progress")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 3

    def test_update_progress(self, configured_client):
        resp = configured_client.post("/api/progress/frame_001.png", json={
            "status": "completed",
        })
        assert resp.status_code == 200

        resp = configured_client.get("/api/progress")
        data = resp.get_json()
        assert data["completed"] == 1


# ── API: export ──

class TestApiExport:
    def test_export_empty(self, configured_client):
        resp = configured_client.post("/api/export")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "exported"

    def test_export_writes_classes_txt(self, configured_client, tmp_dirs):
        configured_client.post("/api/export")
        # Output dir is the default (app_dir / labeling_output)
        # Check that classes.txt was written in the output dir
        resp = configured_client.get("/api/current-config")
        output_dir = Path(resp.get_json()["output_dir"])
        classes = output_dir / "classes.txt"
        assert classes.exists()
        content = classes.read_text()
        assert "king" in content

    def test_export_with_annotations(self, configured_client, tmp_dirs):
        configured_client.post("/api/annotations/frame_001.png", json={
            "annotations": [{"class_id": 0, "x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4, "type": "box"}],
        })
        resp = configured_client.post("/api/export")
        data = resp.get_json()
        assert data["count"] == 1


# ── API: list-dir ──

class TestApiListDir:
    def test_list_dir_root(self, client):
        resp = client.post("/api/list-dir", json={"path": ""})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["is_root"] is True

    def test_list_dir_valid_path(self, client, tmp_dirs):
        resp = client.post("/api/list-dir", json={"path": str(tmp_dirs["root"])})
        assert resp.status_code == 200
        data = resp.get_json()
        assert not data["is_root"]

    def test_list_dir_invalid_path(self, client):
        resp = client.post("/api/list-dir", json={"path": "/nonexistent/xyz"})
        assert resp.status_code == 400


# ── API: prepare status ──

class TestApiPrepareStatus:
    def test_prepare_status_idle(self, client):
        resp = client.get("/api/prepare/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "idle"


# ── YOLO export format ──

class TestYoloExport:
    def test_box_annotation_creates_label_file(self, configured_client, tmp_dirs):
        configured_client.post("/api/annotations/frame_001.png", json={
            "annotations": [{
                "class_id": 0, "x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4, "type": "box",
            }],
        })
        resp = configured_client.get("/api/current-config")
        output_dir = Path(resp.get_json()["output_dir"])
        label_file = output_dir / "labels" / "frame_001.txt"
        assert label_file.exists()
        line = label_file.read_text().strip()
        assert line.startswith("0 ")
        parts = line.split()
        assert len(parts) == 5

    def test_polygon_annotation_creates_seg_label(self, configured_client, tmp_dirs):
        configured_client.post("/api/annotations/frame_001.png", json={
            "annotations": [{
                "class_id": 1,
                "type": "polygon",
                "points": [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]],
            }],
        })
        resp = configured_client.get("/api/current-config")
        output_dir = Path(resp.get_json()["output_dir"])
        label_file = output_dir / "labels" / "frame_001.txt"
        assert label_file.exists()
        line = label_file.read_text().strip()
        assert line.startswith("1 ")
        parts = line.split()
        assert len(parts) == 7  # class + 3 x,y pairs


# ── Session restore ──

class TestSessionRestore:
    def test_last_session_saved_on_setup(self, configured_client, tmp_dirs):
        session_file = tmp_dirs["root"] / "last_session.json"
        assert session_file.exists()
        data = json.loads(session_file.read_text())
        assert "input_dir" in data
        assert "labels" in data


# ── Point annotations ──

class TestPointAnnotations:
    def _output_dir(self, client):
        return Path(client.get("/api/current-config").get_json()["output_dir"])

    def test_point_round_trips(self, configured_client):
        resp = configured_client.post("/api/annotations/frame_001.png", json={
            "annotations": [{"class_id": 0, "type": "point", "x": 0.25, "y": 0.75}],
        })
        assert resp.status_code == 200

        data = configured_client.get("/api/annotations/frame_001.png").get_json()
        assert len(data["annotations"]) == 1
        assert data["annotations"][0]["type"] == "point"

    def test_point_writes_points_file(self, configured_client):
        configured_client.post("/api/annotations/frame_001.png", json={
            "annotations": [
                {"class_id": 0, "type": "point", "x": 0.25, "y": 0.75},
                {"class_id": 2, "type": "point", "x": 0.5, "y": 0.5},
            ],
        })
        pts = self._output_dir(configured_client) / "points" / "frame_001.txt"
        lines = pts.read_text().strip().split("\n")
        assert len(lines) == 2
        assert lines[0].split() == ["0", "0.250000", "0.750000"]

    def test_points_excluded_from_yolo_labels(self, configured_client):
        """A point has no width or height — emitting it as a box would
        write a zero-area detection and corrupt training."""
        configured_client.post("/api/annotations/frame_001.png", json={
            "annotations": [
                {"class_id": 0, "type": "point", "x": 0.25, "y": 0.75},
                {"class_id": 1, "x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2, "type": "box"},
            ],
        })
        label_file = self._output_dir(configured_client) / "labels" / "frame_001.txt"
        lines = [l for l in label_file.read_text().strip().split("\n") if l]
        assert len(lines) == 1
        assert lines[0].startswith("1 ")

    def test_point_coordinates_are_clamped(self, configured_client):
        configured_client.post("/api/annotations/frame_001.png", json={
            "annotations": [{"class_id": 0, "type": "point", "x": -0.4, "y": 1.6}],
        })
        pts = self._output_dir(configured_client) / "points" / "frame_001.txt"
        _, x, y = pts.read_text().strip().split()
        assert float(x) == 0.0
        assert float(y) == 1.0

    def test_export_writes_counts_csv(self, configured_client):
        configured_client.post("/api/annotations/frame_001.png", json={
            "annotations": [
                {"class_id": 0, "type": "point", "x": 0.2, "y": 0.2},
                {"class_id": 0, "type": "point", "x": 0.3, "y": 0.3},
                {"class_id": 1, "x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2, "type": "box"},
            ],
        })
        resp = configured_client.post("/api/export")
        data = resp.get_json()
        assert data["point_totals"]["king"] == 2
        assert data["totals"]["red"] == 1

        csv_text = (self._output_dir(configured_client) / "counts.csv").read_text()
        rows = [r.split(",") for r in csv_text.strip().split("\n")]
        assert rows[0][0] == "image"
        king_row = next(r for r in rows[1:] if r[2] == "king")
        assert king_row[3] == "2"   # points
        assert king_row[6] == "2"   # total

    def test_counts_csv_quotes_names_with_commas(self, configured_client, tmp_dirs):
        awkward = tmp_dirs["input"] / "frame,004.png"
        awkward.write_bytes((tmp_dirs["input"] / "frame_001.png").read_bytes())

        configured_client.post("/api/annotations/frame,004.png", json={
            "annotations": [{"class_id": 0, "type": "point", "x": 0.2, "y": 0.2}],
        })
        configured_client.post("/api/export")

        csv_text = (self._output_dir(configured_client) / "counts.csv").read_text()
        assert '"frame,004.png"' in csv_text


# ── Unconfigured access ──
#
# These routes all read the session dict. Before the _requires_setup guard
# they raised a bare KeyError and returned a 500 traceback to the browser.

class TestUnconfiguredAccess:
    @pytest.mark.parametrize("method,route", [
        ("get", "/api/images"),
        ("get", "/api/image/frame_001.png"),
        ("get", "/api/annotations/frame_001.png"),
        ("post", "/api/annotations/frame_001.png"),
        ("delete", "/api/annotations/frame_001.png/abc"),
        ("post", "/api/delete-image/frame_001.png"),
        ("get", "/api/progress"),
        ("post", "/api/progress/frame_001.png"),
        ("post", "/api/export"),
    ])
    def test_returns_409_not_500(self, client, method, route):
        resp = getattr(client, method)(route, json={})
        assert resp.status_code == 409
        assert resp.get_json()["needs_setup"] is True


# ── Path traversal ──

class TestPathTraversal:
    def test_delete_image_cannot_escape_input_dir(self, configured_client, tmp_dirs):
        outside = tmp_dirs["root"] / "secret.png"
        outside.write_bytes(b"do not move me")

        resp = configured_client.post("/api/delete-image/..%2Fsecret.png")
        assert resp.status_code == 404
        assert outside.exists()


# ── Coordinate clamping ──

class TestCoordinateClamping:
    def _label_lines(self, client, name="frame_001"):
        output_dir = Path(client.get("/api/current-config").get_json()["output_dir"])
        return (output_dir / "labels" / f"{name}.txt").read_text().strip().split("\n")

    def test_box_beyond_edges_is_clamped(self, configured_client):
        configured_client.post("/api/annotations/frame_001.png", json={
            "annotations": [{
                "class_id": 0, "x": -0.2, "y": -0.1, "w": 1.5, "h": 1.4, "type": "box",
            }],
        })
        cls, cx, cy, w, h = self._label_lines(configured_client)[0].split()
        for v in (cx, cy, w, h):
            assert 0.0 <= float(v) <= 1.0
        # x spans -0.2..1.3 -> clamps to 0..1, so center 0.5 and width 1.0
        assert float(cx) == pytest.approx(0.5)
        assert float(w) == pytest.approx(1.0)

    def test_polygon_points_are_clamped(self, configured_client):
        configured_client.post("/api/annotations/frame_001.png", json={
            "annotations": [{
                "class_id": 1,
                "type": "polygon",
                "points": [[-0.5, 0.2], [1.8, 0.4], [0.5, -0.3]],
            }],
        })
        coords = [float(v) for v in self._label_lines(configured_client)[0].split()[1:]]
        assert all(0.0 <= v <= 1.0 for v in coords)

    def test_fully_offscreen_box_is_dropped(self, configured_client):
        configured_client.post("/api/annotations/frame_001.png", json={
            "annotations": [{
                "class_id": 0, "x": 1.2, "y": 1.2, "w": 0.3, "h": 0.3, "type": "box",
            }],
        })
        output_dir = Path(configured_client.get("/api/current-config").get_json()["output_dir"])
        assert (output_dir / "labels" / "frame_001.txt").read_text() == ""
