from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .common import require_tool, run_json_command
from .review import normalize_relative_path


def analyze_manifest(manifest_path: Path, workspace: Path, output_path: Path, dry_run: bool = False) -> dict[str, Any]:
    """Create portable, deterministic metadata from the scanned media manifest."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, list):
        raise ValueError("media_manifest.json must contain an array")
    require_tool("ffprobe")
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
        results.append({
            "source": {"relative_path": relative},
            "duration_seconds": float(item.get("duration", 0)),
            "width": video.get("width", item.get("width")),
            "height": video.get("height", item.get("height")),
            "fps": item.get("fps"),
            "rotation": item.get("rotation"),
            "orientation": "portrait" if (video.get("height", 0) or 0) > (video.get("width", 0) or 0) else "landscape",
            "has_audio": audio is not None,
            "signals": {"black_sections": [], "static_sections": [], "audio_activity": "present" if audio else "none", "luminance": "not_measured"},
        })
    artifact = {"schema_version": 1, "source_manifest": manifest_path.name, "clips": results}
    if not dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return artifact
