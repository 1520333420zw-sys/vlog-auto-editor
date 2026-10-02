from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any

from .common import parse_time


DEFAULT_OUTPUT = "workspace/output/VLOG_01_V1.mp4"
DEFAULT_WIDTH = 1920
DEFAULT_HEIGHT = 1080
DEFAULT_FPS = 30
FALLBACK_RANGE_SECONDS = 4.0


def _format_seconds(value: float) -> float | int:
    rounded = round(value, 3)
    return int(rounded) if rounded.is_integer() else rounded


def _clip_label(clip: dict[str, Any], index: int) -> str:
    return str(clip.get("display_id") or clip.get("clip_id") or f"clip {index + 1}")


def _safe_raw_source(relative_path: str, workspace: Path) -> str:
    path = Path(relative_path)
    if path.is_absolute() or path.drive:
        raise ValueError(f"Review source path must be relative to workspace/raw: {relative_path!r}")
    raw_root = (workspace / "raw").resolve()
    candidate = (raw_root / path).resolve()
    if candidate != raw_root and raw_root in candidate.parents:
        return PurePosixPath("workspace/raw").joinpath(PurePosixPath(relative_path.replace("\\", "/"))).as_posix()
    raise ValueError(f"Review source path escapes workspace/raw: {relative_path!r}")


def _selected_ranges(clip: dict[str, Any], index: int) -> list[tuple[float, float]]:
    label = _clip_label(clip, index)
    duration = clip.get("duration_seconds")
    if not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration <= 0:
        raise ValueError(f"{label} must have a positive duration_seconds value")
    editorial = clip.get("editorial") or {}
    ranges = editorial.get("selected_ranges") or []
    if not isinstance(ranges, list):
        raise ValueError(f"{label} editorial.selected_ranges must be an array")
    if ranges:
        return [_validate_range(item, duration, label, range_index) for range_index, item in enumerate(ranges)]
    if editorial.get("keep") is True:
        return [(0.0, min(float(duration), FALLBACK_RANGE_SECONDS))]
    return []


def _validate_range(item: Any, duration: float, label: str, range_index: int) -> tuple[float, float]:
    if not isinstance(item, dict):
        raise ValueError(f"{label} range {range_index + 1} must be an object with in/out values")
    start_value = item.get("in", item.get("start"))
    end_value = item.get("out", item.get("end"))
    try:
        start = parse_time(start_value)
        end = parse_time(end_value)
    except ValueError as exc:
        if "negative" in str(exc).lower():
            raise ValueError(f"{label} range {range_index + 1} uses negative timestamps") from exc
        raise ValueError(f"{label} range {range_index + 1} has malformed timestamps") from exc
    if start < 0:
        raise ValueError(f"{label} range {range_index + 1} starts before 0")
    if start >= end:
        raise ValueError(f"{label} range {range_index + 1} must have in before out")
    if end > duration:
        raise ValueError(f"{label} range {range_index + 1} ends after source duration")
    return start, end


def build_plan(review_manifest: dict[str, Any], workspace: Path) -> dict[str, Any]:
    clips = review_manifest.get("clips")
    if not isinstance(clips, list):
        raise ValueError("review_manifest.json must contain a clips array")
    planned: list[dict[str, Any]] = []
    for clip_index, clip in enumerate(clips):
        source = clip.get("source", {})
        relative_path = source.get("relative_path") if isinstance(source, dict) else None
        if not isinstance(relative_path, str) or not relative_path:
            raise ValueError(f"{_clip_label(clip, clip_index)} is missing source.relative_path")
        ranges = _selected_ranges(clip, clip_index)
        if not ranges:
            continue
        safe_source = _safe_raw_source(relative_path, workspace)
        editorial = clip.get("editorial") or {}
        note = editorial.get("notes") or ""
        for start, end in ranges:
            segment = {
                "source": safe_source,
                "in": _format_seconds(start),
                "out": _format_seconds(end),
                "audio": "source",
                "note": note,
                "display_id": clip.get("display_id"),
                "clip_id": clip.get("clip_id"),
            }
            planned.append({key: value for key, value in segment.items() if value not in (None, "")})
    if not planned:
        raise ValueError("No clips were selected for the rough-cut plan")
    return {
        "output": DEFAULT_OUTPUT,
        "video": {"width": DEFAULT_WIDTH, "height": DEFAULT_HEIGHT, "fps": DEFAULT_FPS},
        "clips": planned,
    }


def load_review_manifest(input_path: Path) -> dict[str, Any]:
    return json.loads(input_path.read_text(encoding="utf-8"))


def write_generated_plan(input_path: Path, output_path: Path, workspace: Path, dry_run: bool = False) -> dict[str, Any]:
    plan = build_plan(load_review_manifest(input_path), workspace)
    if not dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return plan
