from vlog_editor.common import parse_fps, parse_time


def test_parse_time_variants():
    assert parse_time("01:02:03.500") == 3723.5
    assert parse_time("02:03.5") == 123.5
    assert parse_time(4) == 4


def test_parse_fps():
    assert parse_fps("30000/1001") > 29.9
    assert parse_fps("0/0") is None
