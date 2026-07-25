"""Tests for video_utils helpers that don't need real media files."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import video_utils
from video_utils import convert_raw_batch, list_raw_images, list_videos, raw_support_available


class TestListing:
    def test_lists_raw_extensions_case_insensitively(self, tmp_path):
        for name in ["a.dng", "b.CR2", "c.NEF", "skip.png", "skip.mp4"]:
            (tmp_path / name).touch()
        found = {p.name for p in list_raw_images(tmp_path)}
        assert found == {"a.dng", "b.CR2", "c.NEF"}

    def test_lists_videos_case_insensitively(self, tmp_path):
        for name in ["a.mp4", "b.MOV", "c.dng", "d.png"]:
            (tmp_path / name).touch()
        found = {p.name for p in list_videos(tmp_path)}
        assert found == {"a.mp4", "b.MOV"}


class TestRawSupportAvailable:
    def test_reports_false_when_rawpy_missing(self, monkeypatch):
        # A None entry in sys.modules makes `import rawpy` raise ImportError.
        monkeypatch.setitem(sys.modules, "rawpy", None)
        assert raw_support_available() is False


class TestConvertRawBatchResilience:
    def test_empty_dir_returns_zero(self, tmp_path):
        out = tmp_path / "out"
        result = convert_raw_batch(tmp_path, out)
        assert result["raw_count"] == 0
        assert result["failed"] == []

    def test_unreadable_file_is_skipped_not_fatal(self, tmp_path, monkeypatch):
        """One corrupt card image must not abort a long conversion run."""
        src = tmp_path / "in"
        src.mkdir()
        for name in ["good_1.dng", "bad.dng", "good_2.dng"]:
            (src / name).write_bytes(b"raw bytes")
        out = tmp_path / "out"

        def fake_convert(raw_path, output_dir, quality=95):
            if raw_path.name == "bad.dng":
                raise OSError("Input/output error")
            dest = output_dir / f"{raw_path.stem}.jpg"
            dest.write_bytes(b"jpg")
            return dest

        monkeypatch.setattr(video_utils, "convert_raw_image", fake_convert)

        result = convert_raw_batch(src, out)
        assert result["raw_count"] == 2
        assert [n for n, _ in result["failed"]] == ["bad.dng"]
        assert "Input/output error" in result["failed"][0][1]
        assert {p.name for p in out.glob("*.jpg")} == {"good_1.jpg", "good_2.jpg"}

    def test_progress_reports_skipped_count(self, tmp_path, monkeypatch):
        src = tmp_path / "in"
        src.mkdir()
        (src / "bad.dng").write_bytes(b"raw")

        monkeypatch.setattr(
            video_utils, "convert_raw_image",
            lambda *a, **k: (_ for _ in ()).throw(OSError("boom")),
        )

        messages = []
        convert_raw_batch(src, tmp_path / "out", progress_callback=lambda s: messages.append(s["message"]))
        assert "could not be read" in messages[-1]

    def test_all_failing_still_returns_cleanly(self, tmp_path, monkeypatch):
        src = tmp_path / "in"
        src.mkdir()
        for name in ["a.dng", "b.dng"]:
            (src / name).write_bytes(b"raw")

        monkeypatch.setattr(
            video_utils, "convert_raw_image",
            lambda *a, **k: (_ for _ in ()).throw(OSError("boom")),
        )

        result = convert_raw_batch(src, tmp_path / "out")
        assert result["raw_count"] == 0
        assert len(result["failed"]) == 2


class TestFlattenOutput:
    def test_moves_pngs_up_and_dedupes(self, tmp_path):
        (tmp_path / "clip_a").mkdir()
        (tmp_path / "clip_b").mkdir()
        (tmp_path / "clip_a" / "frame_0001.png").write_bytes(b"a")
        (tmp_path / "clip_b" / "frame_0001.png").write_bytes(b"b")

        moved = video_utils.flatten_output(tmp_path)
        assert moved == 2
        names = sorted(p.name for p in tmp_path.glob("*.png"))
        assert names == ["frame_0001.png", "frame_0001_1.png"]
        assert not (tmp_path / "clip_a").exists()
