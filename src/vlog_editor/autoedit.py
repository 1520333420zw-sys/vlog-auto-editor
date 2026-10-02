from __future__ import annotations

import json
import math
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any

from .common import parse_time


def build_autoedit(review: dict[str, Any], analysis: dict[str, Any] | None = None, target_duration: float | None = None) -> dict[str, Any]:
    if not isinstance(review.get("clips"), list):
        raise ValueError("review manifest must contain a clips array")
    analysis_by_source = {item.get("source", {}).get("relative_path"): item for item in (analysis or {}).get("clips", [])}
    decisions = []
    total = 0.0
    used_groups: set[str] = set()
    last_orientation: str | None = None
    for index, clip in enumerate(review["clips"]):
        if not isinstance(clip, dict) or not isinstance(clip.get("source"), dict):
            raise ValueError(f"review clip {index + 1} is malformed")
        source = clip["source"].get("relative_path")
        if not isinstance(source, str) or not source or Path(source).is_absolute() or Path(source).drive:
            raise ValueError(f"clip {index + 1} source must be a relative raw-media path")
        normalized_source = source.replace("\\", "/")
        if any(part in {"", ".", ".."} for part in PurePosixPath(normalized_source).parts) and ".." in PurePosixPath(normalized_source).parts:
            raise ValueError(f"clip {index + 1} source path must stay inside workspace/raw")
        duration = clip.get("duration_seconds")
        if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(float(duration)) or duration <= 0:
            raise ValueError(f"clip {index + 1} duration_seconds must be a positive number")
        editorial = clip.get("editorial") or {}
        ranges = editorial.get("selected_ranges") or []
        rejected = editorial.get("keep") is False
        signals = analysis_by_source.get(source, {})
        visual = signals.get("visual", {})
        duplicate_group = visual.get("duplicate_group")
        orientation = signals.get("orientation")
        chosen = []
        if ranges:
            for range_index, item in enumerate(ranges, 1):
                if not isinstance(item, dict):
                    raise ValueError(f"clip {index + 1} range {range_index} is malformed")
                start = parse_time(item.get("in", item.get("start"))); end = parse_time(item.get("out", item.get("end")))
                if start >= end or end > float(duration):
                    raise ValueError(f"clip {index + 1} range {range_index} is invalid")
                chosen.append((start, end, "human selected range"))
        elif editorial.get("keep") is True:
            end = min(float(duration), 4.0)
            chosen = [(0.0, end, "human keep with conservative fallback")]
        elif not rejected and float(duration) >= 1.5:
            if duplicate_group and duplicate_group in used_groups:
                continue
            if orientation == "portrait" and last_orientation == "portrait":
                continue
            segment_length = min(float(duration), 4.0)
            start = 0.0 if duration <= 4.0 else min(max(float(duration) * 0.35, 0.0), float(duration) - segment_length)
            reason = "automatic interior usable window; no human decision"
            if signals.get("signals", {}).get("audio_activity") == "none":
                reason += "; video-only source"
            if duplicate_group:
                reason += f"; representative of {duplicate_group}"
            if orientation:
                reason += f"; {orientation} framing"
            chosen = [(round(start, 3), round(start + segment_length, 3), reason)]
        for start, end, reason in chosen:
            if target_duration is not None and total >= target_duration and reason.startswith("automatic"):
                continue
            source_of_decision = "human" if reason.startswith("human") else "automatic"
            decisions.append({"clip_id": clip.get("clip_id"), "display_id": clip.get("display_id"), "source": source, "suggested_in": start, "suggested_out": end, "score": 1.0 if source_of_decision == "human" else 0.5, "reasons": [reason], "source_of_decision": source_of_decision, "orientation": orientation, "duplicate_group": duplicate_group, "representative_source": visual.get("representative_source")})
            total += end - start
            if duplicate_group:
                used_groups.add(duplicate_group)
            last_orientation = orientation or last_orientation
    if not decisions:
        raise ValueError("No clips were selected for automatic rough cut")
    return {"schema_version": 1, "target_duration_seconds": target_duration, "decisions": decisions, "total_duration_seconds": round(total, 3)}


def write_autoedit(review_path: Path, output_path: Path, analysis_path: Path | None = None, target_duration: float | None = None, dry_run: bool = False, analysis_data: dict[str, Any] | None = None) -> dict[str, Any]:
    review = json.loads(review_path.read_text(encoding="utf-8"))
    analysis = analysis_data if analysis_data is not None else (json.loads(analysis_path.read_text(encoding="utf-8")) if analysis_path and analysis_path.exists() else None)
    artifact = build_autoedit(review, analysis, target_duration)
    if not dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return artifact


def plan_from_autoedit(artifact: dict[str, Any]) -> dict[str, Any]:
    clips = []
    for decision in artifact.get("decisions", []):
        clips.append({"source": "workspace/raw/" + decision["source"], "in": decision["suggested_in"], "out": decision["suggested_out"], "audio": "source", "note": "; ".join(decision.get("reasons", [])), "display_id": decision.get("display_id"), "clip_id": decision.get("clip_id")})
    if not clips:
        raise ValueError("Automatic decisions contain no renderable clips")
    return {"output": "workspace/output/VLOG_01_V1.mp4", "video": {"width": 1920, "height": 1080, "fps": 30}, "clips": clips}
