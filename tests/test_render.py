import pytest
import json
from vlog_editor.render import audio_filter, build_filter, validate_plan
from vlog_editor import render as render_module


def test_validate_plan_rejects_reverse_range():
    with pytest.raises(ValueError):
        validate_plan({"clips": [{"source": "raw/a.MOV", "in": 2, "out": 1}]})


def test_validate_plan_accepts_sample():
    validate_plan({"clips": [{"source": "raw/a.MOV", "in": "00:00:01", "out": "00:00:02"}]})


def test_build_filter_keeps_video_and_audio_indices_separate():
    result = build_filter(0, {"audio_gain_db": 0}, 1920, 1080, 30).replace("[0:a]", "[1:a]")
    assert "[0:v]" in result
    assert "[1:a]anull[a0]" in result


def test_audio_filter_supports_documented_and_legacy_audio_contracts():
    assert audio_filter({"audio": "source"}) == "anull"
    assert audio_filter({"audio": "mute"}) == "volume=0"
    assert audio_filter({"audio": -2}) == "volume=-2dB"
    assert audio_filter({"audio_gain_db": -3}) == "volume=-3dB"


@pytest.mark.parametrize("streams, expected_audio_input", [([], "anullsrc=channel_layout=stereo:sample_rate=48000"), ([{"codec_type": "audio"}], None)])
def test_render_command_handles_audio_and_video_only(monkeypatch, tmp_path, streams, expected_audio_input):
    workspace = tmp_path / "workspace"; source = workspace / "raw" / "clip.MOV"; source.parent.mkdir(parents=True); source.write_bytes(b"source")
    project = workspace / "project.json"
    project.write_text(json.dumps({"clips": [{"source": "raw/clip.MOV", "in": 0, "out": 1}]}), encoding="utf-8")
    monkeypatch.setattr(render_module, "require_tool", lambda name: name)
    monkeypatch.setattr(render_module, "run_json_command", lambda _: {"streams": streams})
    monkeypatch.setattr(render_module.subprocess, "run", lambda *args, **kwargs: type("Result", (), {"returncode": 0, "stderr": ""})())
    command = render_module.render(project, workspace, dry_run=False)
    assert (expected_audio_input in command) if expected_audio_input else "anullsrc" not in command
    filter_complex = command[command.index("-filter_complex") + 1]
    assert "[0:v]" in filter_complex


def test_render_accepts_phase3_generated_audio_schema(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"; source = workspace / "raw" / "clip.MOV"; source.parent.mkdir(parents=True); source.write_bytes(b"source")
    project = workspace / "project.json"
    project.write_text(json.dumps({"clips": [{"source": "workspace/raw/clip.MOV", "in": 0, "out": 1, "audio": "source"}]}), encoding="utf-8")
    monkeypatch.setattr(render_module, "require_tool", lambda name: name)
    monkeypatch.setattr(render_module, "run_json_command", lambda _: {"streams": [{"codec_type": "audio"}]})
    monkeypatch.setattr(render_module.subprocess, "run", lambda *args, **kwargs: type("Result", (), {"returncode": 0, "stderr": ""})())
    command = render_module.render(project, workspace, dry_run=False)
    assert "anull" in command[command.index("-filter_complex") + 1]
