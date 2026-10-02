import json
import sys

import pytest

from vlog_editor.cli import main
from vlog_editor.plan import build_plan, write_generated_plan


def clip(display_id, relative_path="day/clip.MOV", duration=10, keep=None, selected_ranges=None):
    editorial = {"selected_ranges": selected_ranges or []}
    if keep is not None:
        editorial["keep"] = keep
    return {
        "clip_id": f"clip_{display_id}",
        "display_id": display_id,
        "source": {"relative_path": relative_path},
        "duration_seconds": duration,
        "editorial": editorial,
    }


def manifest(clips):
    return {"schema_version": 1, "clips": clips}


def test_keep_true_without_selected_ranges_uses_conservative_fallback(tmp_path):
    plan = build_plan(manifest([clip("C001", duration=10, keep=True)]), tmp_path / "workspace")
    segment = plan["clips"][0]
    assert segment["in"] == 0
    assert segment["out"] == 4
    assert segment["audio"] == "source"


def test_keep_true_short_clip_fallback_respects_duration(tmp_path):
    plan = build_plan(manifest([clip("C001", duration=2.5, keep=True)]), tmp_path / "workspace")
    assert plan["clips"][0]["out"] == 2.5


def test_selected_ranges_take_precedence_with_keep_true(tmp_path):
    plan = build_plan(manifest([clip("C001", keep=True, selected_ranges=[{"in": 2, "out": 3}])]), tmp_path / "workspace")
    assert [(item["in"], item["out"]) for item in plan["clips"]] == [(2, 3)]


def test_selected_ranges_are_used_when_keep_false(tmp_path):
    plan = build_plan(manifest([clip("C001", keep=False, selected_ranges=[{"in": 1, "out": 2}])]), tmp_path / "workspace")
    assert len(plan["clips"]) == 1


def test_rejected_and_unselected_clips_are_excluded(tmp_path):
    with pytest.raises(ValueError, match="No clips"):
        build_plan(manifest([clip("C001", keep=False), clip("C002")]), tmp_path / "workspace")


def test_multiple_ranges_and_ordering_across_clips(tmp_path):
    clips = [
        clip("C001", selected_ranges=[{"in": 3, "out": 4}, {"in": 5, "out": 6}]),
        clip("C002", selected_ranges=[{"start": "00:00:01", "end": "00:00:02"}]),
    ]
    plan = build_plan(manifest(clips), tmp_path / "workspace")
    assert [item["display_id"] for item in plan["clips"]] == ["C001", "C001", "C002"]
    assert [(item["in"], item["out"]) for item in plan["clips"]] == [(3, 4), (5, 6), (1, 2)]


@pytest.mark.parametrize(
    "selected_ranges, message",
    [
        ([{"in": "bad", "out": 1}], "malformed"),
        ([{"in": -1, "out": 1}], "negative"),
        ([{"in": 1, "out": 1}], "in before out"),
        ([{"in": 2, "out": 1}], "in before out"),
        ([{"in": 1, "out": 99}], "after source duration"),
    ],
)
def test_invalid_ranges_are_rejected(tmp_path, selected_ranges, message):
    with pytest.raises(ValueError, match=message):
        build_plan(manifest([clip("C001", selected_ranges=selected_ranges)]), tmp_path / "workspace")


@pytest.mark.parametrize("relative_path", ["../outside.MOV", "day/../../outside.MOV", "C:/outside.MOV", "C:outside.MOV"])
def test_source_path_must_stay_inside_workspace_raw(tmp_path, relative_path):
    with pytest.raises(ValueError, match="workspace/raw"):
        build_plan(manifest([clip("C001", relative_path=relative_path, keep=True)]), tmp_path / "workspace")


def test_deterministic_output(tmp_path):
    review = manifest([clip("C001", keep=True)])
    first = build_plan(review, tmp_path / "workspace")
    second = build_plan(review, tmp_path / "workspace")
    assert json.dumps(first, ensure_ascii=False, indent=2) == json.dumps(second, ensure_ascii=False, indent=2)


def test_dry_run_does_not_write(tmp_path):
    workspace = tmp_path / "workspace"
    input_path = workspace / "review" / "review_manifest.json"
    output_path = workspace / "project" / "rough_cut.generated.json"
    input_path.parent.mkdir(parents=True)
    input_path.write_text(json.dumps(manifest([clip("C001", keep=True)])), encoding="utf-8")
    plan = write_generated_plan(input_path, output_path, workspace, dry_run=True)
    assert plan["clips"]
    assert not output_path.exists()


def test_cli_plan_dry_run_wiring(monkeypatch, tmp_path, capsys):
    workspace = tmp_path / "workspace"
    input_path = workspace / "review" / "review_manifest.json"
    input_path.parent.mkdir(parents=True)
    input_path.write_text(json.dumps(manifest([clip("C001", keep=True)])), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["vlog-editor", "--workspace", str(workspace), "plan", "--dry-run"])
    assert main() == 0
    output = capsys.readouterr().out
    assert "rough_cut.generated" not in output
    assert '"clips"' in output
