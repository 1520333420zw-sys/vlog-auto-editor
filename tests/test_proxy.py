from vlog_editor.proxy import generate_proxies


def test_proxy_video_only_command_has_output_and_no_audio(monkeypatch, tmp_path):
    raw = tmp_path / "raw"; raw.mkdir(); source = raw / "clip.MOV"; source.write_bytes(b"source")
    monkeypatch.setattr("vlog_editor.proxy.require_tool", lambda name: name)
    monkeypatch.setattr("vlog_editor.proxy.run_json_command", lambda _: {"streams": []})
    commands = generate_proxies(raw, tmp_path / "proxy", dry_run=True)
    command = commands[0]
    assert "-an" in command
    assert str(tmp_path / "proxy" / "clip.mp4") == command[-1]


def test_proxy_audio_command_has_audio_encoding(monkeypatch, tmp_path):
    raw = tmp_path / "raw"; raw.mkdir(); source = raw / "clip.MOV"; source.write_bytes(b"source")
    monkeypatch.setattr("vlog_editor.proxy.require_tool", lambda name: name)
    monkeypatch.setattr("vlog_editor.proxy.run_json_command", lambda _: {"streams": [{"codec_type": "audio"}]})
    command = generate_proxies(raw, tmp_path / "proxy", dry_run=True)[0]
    assert command[-1].endswith("clip.mp4")
    assert command[command.index("-c:a") + 1] == "aac"
