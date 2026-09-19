import json

from vlog_editor.review import clip_id, display_id, orientation, thumbnail_timestamps, build_contact_sheet_command, build_thumbnail_command, build_review_package


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
    thumb = build_thumbnail_command(__import__("pathlib").Path("x y/旅行.MOV"), __import__("pathlib").Path("out.jpg"), 7, "C001 07.00", 320)
    sheet = build_contact_sheet_command(__import__("pathlib").Path("list.txt"), __import__("pathlib").Path("sheet.jpg"), 3, 2)
    assert "C001 07.00" in thumb[thumb.index("-vf") + 1]
    assert "tile=3x2" in sheet[sheet.index("-vf") + 1]


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
