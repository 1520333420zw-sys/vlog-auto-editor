import json
import os
import shutil
import subprocess

import pytest

from vlog_editor.review import clip_id, display_id, orientation, thumbnail_timestamps, format_timestamp, build_contact_sheet_command, build_thumbnail_command, build_review_package, _asset_path
import vlog_editor.review as review_module


def test_clip_id_is_stable_across_mtime_changes():
    assert clip_id("day\\旅行 01\\IMG 0001.MOV", 42) == clip_id("day/旅行 01/IMG 0001.MOV", 42)
    assert clip_id("clip.MOV", 42) == clip_id("clip.MOV", 42)
    assert clip_id("clip.MOV", 42) != clip_id("clip.MOV", 43)


def test_display_ids_and_orientation():
    assert [display_id(i) for i in range(1, 4)] == ["C001", "C002", "C003"]
    assert orientation(1920, 1080, 0) == "landscape"
    assert orientation(1920, 1080, 90) == "portrait"
    assert orientation(1080, 1920, 90) == "landscape"


def test_thumbnail_timestamps_and_labeled_commands():
    assert thumbnail_timestamps(14, 3) == [0.0, 6.75, 13.5]
    assert thumbnail_timestamps(2, 3, 2) == [0.0, 0.75, 1.5]
    assert [format_timestamp(value) for value in (0, 7, 84, 3600)] == ["00:00", "00:07", "01:24", "01:00:00"]
    thumb = build_thumbnail_command(__import__("pathlib").Path("x y/旅行.MOV"), __import__("pathlib").Path("out.jpg"), 7, "C001 · 00:07", 320)
    sheet = build_contact_sheet_command([__import__("pathlib").Path("a.jpg"), __import__("pathlib").Path("b.jpg"), __import__("pathlib").Path("c.jpg")], __import__("pathlib").Path("sheet.jpg"), 2)
    assert "C001 · 00\\:07" in thumb[thumb.index("-vf") + 1]
    assert thumb[thumb.index("-pix_fmt") + 1] == "yuvj420p"
    assert "tile=2x2" in sheet[sheet.index("-filter_complex") + 1]
    assert sheet.count("-i") == 3


def test_thumbnail_filter_uses_discovered_font_with_windows_safe_path(monkeypatch, tmp_path):
    font = tmp_path / "Windows Fonts" / "Arial.ttf"
    font.parent.mkdir()
    font.write_bytes(b"font")
    monkeypatch.setattr(review_module, "_find_font_file", lambda: font)
    command = build_thumbnail_command(__import__("pathlib").Path("C:/media/clip.MOV"), __import__("pathlib").Path("C:/review/frame.jpg"), 0, "C001 · 00:00", 320)
    filter_text = command[command.index("-vf") + 1]
    assert "fontfile='" in filter_text
    assert "Windows Fonts/Arial.ttf" in filter_text
    assert "C:/" not in filter_text or "C\\:/" in filter_text


def test_review_manifest_is_portable_and_preserves_editorial_fields(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    raw = workspace / "raw" / "day 01"; raw.mkdir(parents=True)
    source = raw / "旅行.MOV"; source.write_bytes(b"media")
    manifest_dir = workspace / "manifests"; manifest_dir.mkdir()
    manifest_dir.joinpath("media_manifest.json").write_text(json.dumps([{"path": str(source), "filename": source.name, "duration": 8, "width": 1920, "height": 1080, "rotation": 0, "fps": 30, "codec": "hevc", "audio": True, "creation_time": None}]), encoding="utf-8")
    monkeypatch.setattr("vlog_editor.review.require_tool", lambda _: "ffmpeg")
    monkeypatch.setattr("vlog_editor.review._run", lambda command, dry_run: None)
    result = build_review_package(workspace)
    result["clips"][0]["editorial"]["notes"] = "keep opening"
    workspace.joinpath("review/review_manifest.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    rebuilt = build_review_package(workspace)
    clip = rebuilt["clips"][0]
    assert clip["editorial"]["notes"] == "keep opening"
    serialized = json.dumps(rebuilt, ensure_ascii=False)
    assert str(workspace) not in serialized
    assert "day 01/旅行.MOV" in serialized


def test_dry_run_does_not_write_review_assets(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"; raw = workspace / "raw"; raw.mkdir(parents=True)
    source = raw / "clip.MOV"; source.write_bytes(b"media")
    workspace.joinpath("manifests").mkdir()
    workspace.joinpath("manifests/media_manifest.json").write_text(json.dumps([{"path": str(source), "filename": "clip.MOV", "duration": 1, "width": 1, "height": 1, "rotation": None, "audio": False}]), encoding="utf-8")
    monkeypatch.setattr("vlog_editor.review.require_tool", lambda _: "ffmpeg")
    result = build_review_package(workspace, dry_run=True)
    assert result["commands"]
    assert not (workspace / "review").exists()


def test_force_rebuilds_unchanged_assets_and_incremental_build_reuses_them(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"; raw = workspace / "raw"; raw.mkdir(parents=True)
    source = raw / "clip.MOV"; source.write_bytes(b"media")
    workspace.joinpath("manifests").mkdir()
    workspace.joinpath("manifests/media_manifest.json").write_text(json.dumps([{"path": str(source), "filename": "clip.MOV", "duration": 1, "width": 1, "height": 1, "rotation": None, "audio": False}]), encoding="utf-8")
    monkeypatch.setattr("vlog_editor.review.require_tool", lambda _: "ffmpeg")
    monkeypatch.setattr("vlog_editor.review._run", lambda command, dry_run: None)
    first = build_review_package(workspace)
    review = workspace / "review"
    for clip in first["clips"]:
        for thumbnail in clip["thumbnails"]:
            (review / thumbnail["relative_path"]).parent.mkdir(parents=True, exist_ok=True)
            (review / thumbnail["relative_path"]).write_bytes(b"thumb")
        (review / clip["contact_sheet"]["relative_path"]).parent.mkdir(parents=True, exist_ok=True)
        (review / clip["contact_sheet"]["relative_path"]).write_bytes(b"sheet")
    incremental = build_review_package(workspace, dry_run=True)
    forced = build_review_package(workspace, force=True, dry_run=True)
    assert incremental["commands"] == []
    assert forced["commands"]


def test_mtime_change_invalidates_cache_without_changing_clip_id(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"; raw = workspace / "raw"; raw.mkdir(parents=True)
    source = raw / "clip.MOV"; source.write_bytes(b"media")
    workspace.joinpath("manifests").mkdir()
    workspace.joinpath("manifests/media_manifest.json").write_text(json.dumps([{"path": str(source), "filename": "clip.MOV", "duration": 1, "width": 1, "height": 1, "rotation": None, "audio": False}]), encoding="utf-8")
    monkeypatch.setattr("vlog_editor.review.require_tool", lambda _: "ffmpeg")
    monkeypatch.setattr("vlog_editor.review._run", lambda command, dry_run: None)
    first = build_review_package(workspace)
    os.utime(source, ns=(source.stat().st_atime_ns, source.stat().st_mtime_ns + 2_000_000_000))
    second = build_review_package(workspace, dry_run=True)
    assert first["clips"][0]["clip_id"] == second["clips"][0]["clip_id"]
    assert second["commands"]


def test_review_asset_traversal_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        _asset_path(tmp_path / "workspace" / "review", "../raw/original.MOV")


def test_original_footage_is_only_an_ffmpeg_input(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"; raw = workspace / "raw"; raw.mkdir(parents=True)
    source = raw / "original.MOV"; source.write_bytes(b"media")
    workspace.joinpath("manifests").mkdir()
    workspace.joinpath("manifests/media_manifest.json").write_text(json.dumps([{"path": str(source), "filename": source.name, "duration": 1, "width": 1, "height": 1, "rotation": None, "audio": False}]), encoding="utf-8")
    commands = []
    monkeypatch.setattr("vlog_editor.review.require_tool", lambda _: "ffmpeg")
    monkeypatch.setattr("vlog_editor.review._run", lambda command, dry_run: commands.append(command))
    build_review_package(workspace)
    source_text = str(source)
    assert all(command[-1] != source_text for command in commands)
    assert all(str(workspace / "review") in command[-1] for command in commands)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is unavailable")
def test_real_ffmpeg_review_package_smoke(tmp_path):
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        pytest.skip("ffprobe is unavailable")
    workspace = tmp_path / "workspace"; raw = workspace / "raw"; raw.mkdir(parents=True)
    source = raw / "synthetic.MOV"
    subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=red:s=320x180:d=2:r=2", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source)], check=True, capture_output=True)
    workspace.joinpath("manifests").mkdir()
    workspace.joinpath("manifests/media_manifest.json").write_text(json.dumps([{"path": str(source), "filename": source.name, "duration": 2, "width": 320, "height": 180, "rotation": 0, "fps": 2, "codec": "h264", "audio": False, "creation_time": None}]), encoding="utf-8")
    result = build_review_package(workspace, thumbnail_count=3, sheet_columns=2)
    thumbnails = [workspace / "review" / item["relative_path"] for item in result["clips"][0]["thumbnails"]]
    sheet = workspace / "review" / result["clips"][0]["contact_sheet"]["relative_path"]
    assert all(path.exists() and path.stat().st_size > 0 for path in thumbnails)
    assert sheet.exists() and sheet.stat().st_size > 0
    probe = subprocess.run([ffprobe, "-v", "error", "-show_entries", "stream=width,height,nb_frames", "-of", "json", str(sheet)], check=True, capture_output=True, text=True)
    stream = json.loads(probe.stdout)["streams"][0]
    assert stream["width"] == 648
    assert stream["height"] == 368
