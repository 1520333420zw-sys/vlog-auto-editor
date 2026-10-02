import json
from pathlib import Path

import pytest
import sys

from vlog_editor.autoedit import build_autoedit, plan_from_autoedit
from vlog_editor.finish import validate_finish_config
from vlog_editor.transcript import import_transcript, validate_transcript


def review(*, keep=None, ranges=None):
    return {"clips": [{"clip_id": "c1", "display_id": "C001", "source": {"relative_path": "a clip.mp4"}, "duration_seconds": 8, "editorial": {"keep": keep, "selected_ranges": ranges or []}}]}


def test_human_range_wins_and_is_auditable():
    artifact = build_autoedit(review(keep=False, ranges=[{"in": 1, "out": 3}]))
    assert artifact["decisions"][0]["source_of_decision"] == "human"
    assert artifact["decisions"][0]["suggested_in"] == 1


def test_reject_wins_over_automatic_fallback():
    with pytest.raises(ValueError, match="No clips"):
        build_autoedit(review(keep=False))


def test_autoedit_rejects_unsafe_source_path():
    bad = review()
    bad["clips"][0]["source"]["relative_path"] = "../outside.mp4"
    with pytest.raises(ValueError, match="workspace/raw"):
        build_autoedit(bad)


def test_automatic_fallback_is_deterministic_and_converts_to_plan():
    artifact = build_autoedit(review(), {"clips": [{"source": {"relative_path": "a clip.mp4"}, "signals": {"audio_activity": "none"}}]})
    assert artifact == build_autoedit(review(), {"clips": [{"source": {"relative_path": "a clip.mp4"}, "signals": {"audio_activity": "none"}}]})
    assert plan_from_autoedit(artifact)["clips"][0]["audio"] == "source"


def test_target_duration_does_not_truncate_human_material():
    artifact = build_autoedit(review(keep=True, ranges=[{"in": 0, "out": 8}]), target_duration=2)
    assert artifact["total_duration_seconds"] == 8


def test_transcript_schema_rejects_bad_timestamps():
    with pytest.raises(ValueError):
        validate_transcript({"entries": [{"start": 2, "end": 1, "text": "bad"}]})


def test_finish_config_is_strict():
    assert validate_finish_config({"audio_normalization": True, "generate_subtitles": True})["generate_subtitles"] is True
    with pytest.raises(ValueError):
        validate_finish_config({"burn_subtitles": True})
    with pytest.raises(ValueError):
        validate_finish_config({"magic": True})


def test_existing_transcript_can_be_imported_and_validated(tmp_path):
    source = tmp_path / "local.json"
    destination = tmp_path / "workspace" / "transcript" / "transcript.json"
    source.write_text(json.dumps({"entries": [{"start": 0, "end": 1, "text": "hello"}]}), encoding="utf-8")
    imported = import_transcript(source, destination)
    assert imported["entries"][0]["text"] == "hello"
    assert destination.exists()


@pytest.mark.parametrize("duration", [True, 0, -1, "bad"])
def test_autoedit_rejects_invalid_durations(duration):
    bad = review(keep=True)
    bad["clips"][0]["duration_seconds"] = duration
    with pytest.raises(ValueError, match="duration_seconds"):
        build_autoedit(bad)


def test_build_dry_run_does_not_write_workspace(monkeypatch, tmp_path):
    from vlog_editor import cli

    workspace = tmp_path / "workspace"
    (workspace / "manifests").mkdir(parents=True)
    (workspace / "review").mkdir(parents=True)
    (workspace / "manifests" / "media_manifest.json").write_text("[]", encoding="utf-8")
    (workspace / "review" / "review_manifest.json").write_text("{}", encoding="utf-8")
    before = {path.relative_to(workspace): path.read_bytes() for path in workspace.rglob("*") if path.is_file()}
    monkeypatch.setattr(cli, "analyze_manifest", lambda *args, **kwargs: {})
    monkeypatch.setattr(cli, "write_autoedit", lambda *args, **kwargs: {"decisions": [{"source": "clip.mp4", "suggested_in": 0, "suggested_out": 1, "reasons": []}]})
    monkeypatch.setattr(sys, "argv", ["vlog-editor", "--workspace", str(workspace), "build", "--dry-run"])
    assert cli.main() == 0
    after = {path.relative_to(workspace): path.read_bytes() for path in workspace.rglob("*") if path.is_file()}
    assert after == before


def test_build_dry_run_uses_fresh_analysis_over_stale_file(monkeypatch, tmp_path, capsys):
    from vlog_editor import cli

    workspace = tmp_path / "workspace"
    (workspace / "manifests").mkdir(parents=True)
    (workspace / "review").mkdir(parents=True)
    (workspace / "analysis").mkdir(parents=True)
    (workspace / "manifests" / "media_manifest.json").write_text("[]", encoding="utf-8")
    review_data = review()
    (workspace / "review" / "review_manifest.json").write_text(json.dumps(review_data), encoding="utf-8")
    stale = {"clips": [{"source": {"relative_path": "a clip.mp4"}, "signals": {"audio_activity": "present"}}]}
    (workspace / "analysis" / "media_analysis.json").write_text(json.dumps(stale), encoding="utf-8")
    before = {path.relative_to(workspace): path.read_bytes() for path in workspace.rglob("*") if path.is_file()}
    fresh = {"clips": [{"source": {"relative_path": "a clip.mp4"}, "signals": {"audio_activity": "none"}}]}
    monkeypatch.setattr(cli, "analyze_manifest", lambda *args, **kwargs: fresh)
    monkeypatch.setattr(sys, "argv", ["vlog-editor", "--workspace", str(workspace), "build", "--dry-run"])
    assert cli.main() == 0
    output = capsys.readouterr().out
    assert "video-only source" in output
    after = {path.relative_to(workspace): path.read_bytes() for path in workspace.rglob("*") if path.is_file()}
    assert after == before
