import json
from pathlib import Path

import pytest

from vlog_editor.autoedit import build_autoedit, plan_from_autoedit
from vlog_editor.finish import validate_finish_config
from vlog_editor.transcript import validate_transcript


def review(*, keep=None, ranges=None):
    return {"clips": [{"clip_id": "c1", "display_id": "C001", "source": {"relative_path": "a clip.mp4"}, "duration_seconds": 8, "editorial": {"keep": keep, "selected_ranges": ranges or []}}]}


def test_human_range_wins_and_is_auditable():
    artifact = build_autoedit(review(keep=False, ranges=[{"in": 1, "out": 3}]))
    assert artifact["decisions"][0]["source_of_decision"] == "human"
    assert artifact["decisions"][0]["suggested_in"] == 1


def test_reject_wins_over_automatic_fallback():
    with pytest.raises(ValueError, match="No clips"):
        build_autoedit(review(keep=False))


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
    assert validate_finish_config({"audio_normalization": True})["audio_normalization"] is True
    with pytest.raises(ValueError):
        validate_finish_config({"magic": True})
