import pytest
import json
import shutil
import subprocess
from vlog_editor.render import _portrait_video_filter, audio_filter, build_filter, validate_plan
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


def test_portrait_filter_uses_numeric_fps_without_placeholder():
    result = _portrait_video_filter(0, 0, 1920, 1080, 30)
    assert "fps=30" in result
    assert "{fps}" not in result


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


def test_render_portrait_bgm_lut_and_burned_subtitle_options(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"; source = workspace / "raw" / "portrait.MOV"; source.parent.mkdir(parents=True); source.write_bytes(b"source")
    bgm = tmp_path / "music.mp3"; bgm.write_bytes(b"music")
    lut = tmp_path / "look.cube"; lut.write_text("LUT_3D_SIZE 2\n", encoding="utf-8")
    subtitle = tmp_path / "captions.srt"; subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\nhello\n", encoding="utf-8")
    project = workspace / "project.json"
    project.write_text(json.dumps({"bgm": {"path": str(bgm), "gain_db": -18}, "lut": str(lut), "subtitle_file": str(subtitle), "clips": [{"source": "raw/portrait.MOV", "in": 0, "out": 1}]}), encoding="utf-8")
    monkeypatch.setattr(render_module, "require_tool", lambda name: name)
    monkeypatch.setattr(render_module, "run_json_command", lambda _: {"streams": [{"codec_type": "video", "width": 1080, "height": 1920, "tags": {"rotate": "0"}}, {"codec_type": "audio"}]})
    monkeypatch.setattr(render_module.subprocess, "run", lambda *args, **kwargs: type("Result", (), {"returncode": 0, "stderr": ""})())
    command = render_module.render(project, workspace, dry_run=False)
    graph = command[command.index("-filter_complex") + 1]
    assert "gblur=sigma=18" in graph
    assert "lut3d" in graph
    assert "subtitles=filename" in graph
    assert "amix=inputs=2" in graph


@pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="FFmpeg is unavailable")
def test_real_ffmpeg_portrait_bgm_render(tmp_path):
    workspace = tmp_path / "workspace"; raw = workspace / "raw"; raw.mkdir(parents=True)
    source = raw / "portrait.mp4"; bgm = tmp_path / "bgm.wav"
    ffmpeg = shutil.which("ffmpeg"); ffprobe = shutil.which("ffprobe")
    subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=blue:s=100x200:d=1:r=10", "-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(source)], check=True, capture_output=True)
    subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=220:duration=1", str(bgm)], check=True, capture_output=True)
    project = workspace / "project.json"
    project.write_text(json.dumps({"output": "workspace/output/portrait-bgm.mp4", "clips": [{"source": "raw/portrait.mp4", "in": 0, "out": 1}], "bgm": {"path": str(bgm), "gain_db": -20}}), encoding="utf-8")
    render_module.render(project, workspace)
    output = workspace / "output" / "portrait-bgm.mp4"
    probe = subprocess.run([ffprobe, "-v", "error", "-show_streams", "-of", "json", str(output)], check=True, capture_output=True, text=True)
    streams = json.loads(probe.stdout)["streams"]
    video = next(stream for stream in streams if stream["codec_type"] == "video")
    assert (video["width"], video["height"]) == (1920, 1080)
    assert any(stream["codec_type"] == "audio" for stream in streams)


@pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="FFmpeg is unavailable")
def test_real_ffmpeg_rotation_metadata_is_explicitly_applied(tmp_path):
    workspace = tmp_path / "workspace"; raw = workspace / "raw"; raw.mkdir(parents=True)
    base = raw / "base.mp4"; source = raw / "rotated.mp4"
    ffmpeg = shutil.which("ffmpeg"); ffprobe = shutil.which("ffprobe")
    subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=green:s=200x100:d=1:r=10", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(base)], check=True, capture_output=True)
    subprocess.run([ffmpeg, "-y", "-display_rotation", "90", "-i", str(base), "-c", "copy", str(source)], check=True, capture_output=True)
    project = workspace / "project.json"
    project.write_text(json.dumps({"output": "workspace/output/rotated.mp4", "clips": [{"source": "raw/rotated.mp4", "in": 0, "out": 1}]}), encoding="utf-8")
    command = render_module.render(project, workspace)
    graph = command[command.index("-filter_complex") + 1]
    assert "transpose=1" in graph
    output = workspace / "output" / "rotated.mp4"
    probe = subprocess.run([ffprobe, "-v", "error", "-show_streams", "-of", "json", str(output)], check=True, capture_output=True, text=True)
    video = next(stream for stream in json.loads(probe.stdout)["streams"] if stream["codec_type"] == "video")
    assert (video["width"], video["height"]) == (1920, 1080)


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
