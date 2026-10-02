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


def test_build_filter_can_label_output_by_timeline_segment():
    result = build_filter(2, {"audio": "source"}, 1920, 1080, 30, output_index=1)
    assert "[2:v]" in result
    assert "[v1]" in result
    assert "[2:a]anull[a1]" in result


def test_audio_filter_supports_documented_and_legacy_audio_contracts():
    assert audio_filter({"audio": "source"}) == "anull"
    assert audio_filter({"audio": "mute"}) == "volume=0"
    assert audio_filter({"audio": -2}) == "volume=-2dB"
    assert audio_filter({"audio_gain_db": -3}) == "volume=-3dB"


def test_render_audio_normalization_is_strict_opt_in(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"; source = workspace / "raw" / "clip.MOV"; source.parent.mkdir(parents=True); source.write_bytes(b"source")
    project = workspace / "project.json"
    project.write_text(json.dumps({"audio_normalization": True, "clips": [{"source": "raw/clip.MOV", "in": 0, "out": 1}]}), encoding="utf-8")
    monkeypatch.setattr(render_module, "require_tool", lambda name: name)
    monkeypatch.setattr(render_module, "run_json_command", lambda _: {"streams": [{"codec_type": "audio"}]})
    monkeypatch.setattr(render_module.subprocess, "run", lambda *args, **kwargs: type("Result", (), {"returncode": 0, "stderr": ""})())
    command = render_module.render(project, workspace, dry_run=False)
    assert "loudnorm=I=-16:TP=-1.5:LRA=11:linear=true" in command[command.index("-filter_complex") + 1]


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


@pytest.mark.parametrize("audio, expected_filter", [("source", "[1:a]anull[a0]"), ("mute", "[1:a]volume=0[a0]")])
def test_render_phase3_audio_contract_handles_video_only_sources(monkeypatch, tmp_path, audio, expected_filter):
    workspace = tmp_path / "workspace"; source = workspace / "raw" / "clip.MOV"; source.parent.mkdir(parents=True); source.write_bytes(b"source")
    project = workspace / "project.json"
    project.write_text(json.dumps({"clips": [{"source": "raw/clip.MOV", "in": 0, "out": 1, "audio": audio}]}), encoding="utf-8")
    monkeypatch.setattr(render_module, "require_tool", lambda name: name)
    monkeypatch.setattr(render_module, "run_json_command", lambda _: {"streams": []})
    monkeypatch.setattr(render_module.subprocess, "run", lambda *args, **kwargs: type("Result", (), {"returncode": 0, "stderr": ""})())
    command = render_module.render(project, workspace, dry_run=False)
    filter_complex = command[command.index("-filter_complex") + 1]
    assert "anullsrc=channel_layout=stereo:sample_rate=48000" in command
    assert expected_filter in filter_complex
    assert "[v0][a0]concat" in filter_complex


def test_render_video_only_first_clip_keeps_timeline_labels_for_following_clip(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"; raw = workspace / "raw"; raw.mkdir(parents=True)
    (raw / "a.MOV").write_bytes(b"a"); (raw / "b.MOV").write_bytes(b"b")
    project = workspace / "project.json"
    project.write_text(json.dumps({"clips": [{"source": "raw/a.MOV", "in": 0, "out": 1, "audio": "source"}, {"source": "raw/b.MOV", "in": 0, "out": 1, "audio": "source"}]}), encoding="utf-8")
    monkeypatch.setattr(render_module, "require_tool", lambda name: name)
    monkeypatch.setattr(render_module, "run_json_command", lambda command: {"streams": [] if "a.MOV" in command[-1] else [{"codec_type": "audio"}]})
    monkeypatch.setattr(render_module.subprocess, "run", lambda *args, **kwargs: type("Result", (), {"returncode": 0, "stderr": ""})())
    command = render_module.render(project, workspace, dry_run=False)
    filter_complex = command[command.index("-filter_complex") + 1]
    assert "[0:v]" in filter_complex
    assert "[2:v]" in filter_complex
    assert "[v0][a0][v1][a1]concat" in filter_complex
