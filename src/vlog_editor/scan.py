from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

from .common import MEDIA_EXTENSIONS, parse_fps, require_tool, run_json_command


def probe_file(path: Path) -> dict:
    data = run_json_command([require_tool("ffprobe"), "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)])
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    tags = {**data.get("format", {}).get("tags", {}), **video.get("tags", {})}
    rotation = video.get("tags", {}).get("rotate") or video.get("side_data_list", [{}])[0].get("rotation")
    return {"path": str(path), "filename": path.name, "duration": float(data.get("format", {}).get("duration", 0)),
            "width": video.get("width"), "height": video.get("height"), "fps": parse_fps(video.get("r_frame_rate")),
            "codec": video.get("codec_name"), "audio": audio is not None, "creation_time": tags.get("creation_time"),
            "rotation": int(rotation) if rotation is not None else None}


def scan(raw: Path, manifests: Path) -> list[dict]:
    require_tool("ffprobe")
    items = [probe_file(p) for p in raw.rglob("*") if p.is_file() and p.suffix.lower() in MEDIA_EXTENSIONS]
    items.sort(key=lambda item: (item["creation_time"] or "9999", item["filename"].lower()))
    manifests.mkdir(parents=True, exist_ok=True)
    (manifests / "media_manifest.json").write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    fields = ["path", "filename", "duration", "width", "height", "fps", "codec", "audio", "creation_time", "rotation"]
    with (manifests / "media_manifest.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader(); writer.writerows(items)
    return items
