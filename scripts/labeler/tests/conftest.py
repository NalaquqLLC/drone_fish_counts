import json
import shutil
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app


@pytest.fixture()
def tmp_dirs(tmp_path):
    """Create temporary input and output directories with sample images."""
    input_dir = tmp_path / "images"
    input_dir.mkdir()

    # Create minimal valid PNG files (1x1 pixel)
    png_header = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
        b"\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx"
        b"\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    for name in ["frame_001.png", "frame_002.png", "frame_003.png"]:
        (input_dir / name).write_bytes(png_header)

    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "annotations").mkdir()
    (output_dir / "labels").mkdir()
    (output_dir / "deleted").mkdir()

    return {"input": input_dir, "output": output_dir, "root": tmp_path}


@pytest.fixture()
def app(tmp_dirs, monkeypatch):
    """Create a test app with a clean session (no last_session.json interference)."""
    # Ensure _app_dir returns our temp directory so last_session.json
    # doesn't bleed in from the real filesystem.
    import app as app_module
    monkeypatch.setattr(app_module, "_app_dir", lambda: tmp_dirs["root"])

    application = create_app()
    application.config["TESTING"] = True
    return application


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def configured_client(client, tmp_dirs):
    """A test client with a session already configured (setup complete)."""
    resp = client.post("/api/setup", json={
        "input_dir": str(tmp_dirs["input"]),
        "labels": ["king", "red", "silver"],
    })
    assert resp.status_code == 200
    return client
