import pytest
from vlog_editor.render import validate_plan


def test_validate_plan_rejects_reverse_range():
    with pytest.raises(ValueError):
        validate_plan({"clips": [{"source": "raw/a.MOV", "in": 2, "out": 1}]})


def test_validate_plan_accepts_sample():
    validate_plan({"clips": [{"source": "raw/a.MOV", "in": "00:00:01", "out": "00:00:02"}]})
