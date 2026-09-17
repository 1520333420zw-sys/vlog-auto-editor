import json
from vlog_editor.subtitles import srt_time, write_subtitles


def test_srt_format():
    assert srt_time(62.25) == "00:01:02,250"


def test_writes_srt_and_ass(tmp_path):
    source = tmp_path / "subtitles.json"
    source.write_text(json.dumps([{"start": 0, "end": 1.5, "zh": "你好", "en": "Hello"}], ensure_ascii=False), encoding="utf-8")
    srt, ass = write_subtitles(source, tmp_path / "out")
    assert "你好\nHello" in srt.read_text(encoding="utf-8")
    assert "Dialogue:" in ass.read_text(encoding="utf-8")
