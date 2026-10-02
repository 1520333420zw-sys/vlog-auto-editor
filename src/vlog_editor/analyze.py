from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from .common import require_tool, run_json_command
from .review import normalize_relative_path


def _average_hash(frame: bytes) -> str:
    if not frame:
        return ""
    mean = sum(frame) / len(frame)
    bits = "".join("1" if value >= mean else "0" for value in frame)
    return f"{int(bits, 2):064x}"


def representative_frame_hash(source: Path, timestamp: float) -> str:
    command = [require_tool("ffmpeg"), "-v", "error", "-ss", f"{timestamp:.3f}", "-i", str(source), "-frames:v", "1", "-vf", "scale=16:16,format=gray", "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1"]
    result = subprocess.run(command, capture_output=True)
    if result.returncode:
        return ""
    return _average_hash(result.stdout)


def _hamming_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return 1.0 - ((int(left, 16) ^ int(right, 16)).bit_count() / 64.0)


def _duplicate_groups(results: list[dict[str, Any]]) -> None:
    groups: list[dict[str, Any]] = []
    for item in results:
        fingerprint = item["visual"]["representative_hash"]
        match = next((group for group in groups if fingerprint and group["hash"] and _hamming_similarity(fingerprint, group["hash"]) >= 0.92), None)
        if match:
            match["members"].append(item)
        else:
            group = {"id": f"duplicate_{len(groups) + 1:03d}", "hash": fingerprint, "members": [item]}
            groups.append(group)
    for group in groups:
        representative = max(
            enumerate(group["members"]),
            key=lambda pair: (
                bool(pair[1].get("has_audio")),
                float(pair[1].get("duration_seconds", 0)),
                pair[1].get("orientation") == "landscape",
                -pair[0],
            ),
        )[1]
        representative_hash = representative["visual"]["representative_hash"]
        representative_source = representative["source"]["relative_path"]
        for item in group["members"]:
            fingerprint = item["visual"]["representative_hash"]
            item["visual"]["duplicate_group"] = group["id"]
            item["visual"]["representative_source"] = representative_source
            item["visual"]["representative_reason"] = "audio presence, usable duration, landscape suitability, then stable manifest order"
            item["visual"]["similarity_to_representative"] = round(_hamming_similarity(fingerprint, representative_hash), 4) if fingerprint and representative_hash else 0.0


def analyze_manifest(manifest_path: Path, workspace: Path, output_path: Path, dry_run: bool = False) -> dict[str, Any]:
    """Create portable, deterministic metadata from the scanned media manifest."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, list):
        raise ValueError("media_manifest.json must contain an array")
    require_tool("ffprobe")
    require_tool("ffmpeg")
    results = []
    for index, item in enumerate(manifest, 1):
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise ValueError(f"manifest item {index} must contain a path")
        source = Path(item["path"])
        streams = run_json_command([require_tool("ffprobe"), "-v", "error", "-show_streams", "-show_format", "-of", "json", str(source)])
        video = next((s for s in streams.get("streams", []) if s.get("codec_type") == "video"), {})
        audio = next((s for s in streams.get("streams", []) if s.get("codec_type") == "audio"), None)
        try:
            relative = normalize_relative_path(source.resolve().relative_to((workspace / "raw").resolve()))
        except ValueError as exc:
            raise ValueError(f"manifest source escapes workspace/raw: {source}") from exc
        duration = float(item.get("duration", 0))
        sample_time = min(max(duration / 2.0, 0.0), max(duration - 0.1, 0.0))
        frame_hash = representative_frame_hash(source, sample_time)
        rotation = int(item.get("rotation") or 0) % 360
        display_width = video.get("height", item.get("height")) if rotation in {90, 270} else video.get("width", item.get("width"))
        display_height = video.get("width", item.get("width")) if rotation in {90, 270} else video.get("height", item.get("height"))
        results.append({
            "source": {"relative_path": relative},
            "duration_seconds": duration,
            "width": video.get("width", item.get("width")),
            "height": video.get("height", item.get("height")),
            "fps": item.get("fps"),
            "rotation": rotation,
            "display_width": display_width,
            "display_height": display_height,
            "orientation": "portrait" if (display_height or 0) > (display_width or 0) else "landscape",
            "has_audio": audio is not None,
            "signals": {"black_sections": [], "static_sections": [], "audio_activity": "present" if audio else "none", "luminance": "not_measured"},
            "visual": {"representative_timestamp": round(sample_time, 3), "representative_hash": frame_hash},
        })
    _duplicate_groups(results)
    artifact = {"schema_version": 1, "source_manifest": manifest_path.name, "clips": results}
    if not dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return artifact
