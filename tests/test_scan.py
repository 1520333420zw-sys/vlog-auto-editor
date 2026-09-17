from vlog_editor.scan import probe_file


def test_probe_shape(monkeypatch, tmp_path):
    payload = {"format": {"duration": "2.5", "tags": {"creation_time": "2024-01-01"}}, "streams": [{"codec_type": "video", "width": 1920, "height": 1080, "r_frame_rate": "30/1", "codec_name": "h264", "tags": {}}, {"codec_type": "audio"}]}
    monkeypatch.setattr("vlog_editor.scan.run_json_command", lambda _: payload)
    monkeypatch.setattr("vlog_editor.scan.require_tool", lambda _: "ffprobe")
    item = probe_file(tmp_path / "clip.MOV")
    assert item["duration"] == 2.5 and item["fps"] == 30 and item["audio"] is True
