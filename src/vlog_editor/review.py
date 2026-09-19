from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

from .common import require_tool


SCHEMA_VERSION = 1
DEFAULT_THUMBNAIL_COUNT = 6
DEFAULT_THUMBNAIL_WIDTH = 320
DEFAULT_SHEET_COLUMNS = 3


def normalize_relative_path(value: str | Path) -> str:
    return PurePosixPath(str(value).replace("\\", "/")).as_posix().lstrip("./")


def clip_id(relative_path: str | Path, file_size: int) -> str:
    identity = f"{normalize_relative_path(relative_path).casefold()}\0{file_size}".encode("utf-8")
    return f"clip_{hashlib.sha256(identity).hexdigest()[:12]}"


def display_id(index: int) -> str:
    return f"C{index:03d}"


def orientation(width: int | None, height: int | None, rotation: int | None) -> str | None:
    if not width or not height:
        return None
    rotated = abs((rotation or 0) % 180) == 90
    return "portrait" if (height > width) ^ rotated else "landscape"


def thumbnail_timestamps(duration: float, count: int = DEFAULT_THUMBNAIL_COUNT) -> list[float]:
    if count < 1:
        raise ValueError("thumbnail count must be at least 1")
    if duration <= 0 or count == 1:
        return [0.0]
    end = max(0.0, duration - min(0.5, duration / 10))
    return [round(end * index / (count - 1), 3) for index in range(count)]


def _source_relative(path: str, raw: Path) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(raw.resolve()).as_posix()
    except ValueError:
        normalized = normalize_relative_path(path)
        marker = normalize_relative_path(raw.name) + "/"
        if marker in normalized:
            return normalized.split(marker, 1)[1]
        raise ValueError(f"Manifest path is outside raw workspace: {path}")


def _asset_path(review_root: Path, relative: str) -> Path:
    root = review_root.resolve()
    path = (review_root / relative).resolve()
    if path != root and root not in path.parents:
        raise ValueError(f"Review asset escapes workspace/review: {relative}")
    return path


def _label_filter(label: str, width: int) -> str:
    escaped = label.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    return f"scale={width}:-2:force_original_aspect_ratio=decrease,pad={width}:ih:(ow-iw)/2:0:color=black,drawtext=text='{escaped}':x=8:y=8:fontsize=20:fontcolor=white:box=1:boxcolor=black@0.65"


def build_thumbnail_command(source: Path, output: Path, timestamp: float, label: str, width: int) -> list[str]:
    return ["ffmpeg", "-y", "-ss", str(timestamp), "-i", str(source), "-frames:v", "1", "-vf", _label_filter(label, width), str(output)]


def build_contact_sheet_command(thumbnail_list: Path, output: Path, columns: int, rows: int) -> list[str]:
    return ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(thumbnail_list), "-vf", f"tile={columns}x{rows}:padding=4:margin=4", "-frames:v", "1", str(output)]


def _run(command: list[str], dry_run: bool) -> None:
    if dry_run:
        return
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "FFmpeg review asset generation failed")


def _editorial(previous: dict[str, Any] | None) -> dict[str, Any]:
    fields = {"notes": "", "tags": [], "rating": None, "keep": None, "selected_ranges": [], "reviewed": False}
    if previous:
        fields.update(previous.get("editorial", {}))
    return fields


def build_review_package(workspace: Path, force: bool = False, dry_run: bool = False, thumbnail_count: int = DEFAULT_THUMBNAIL_COUNT, sheet_columns: int = DEFAULT_SHEET_COLUMNS) -> dict[str, Any]:
    require_tool("ffmpeg")
    raw = workspace / "raw"
    review_root = workspace / "review"
    manifest_path = workspace / "manifests" / "media_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError("Run 'vlog-editor scan' before building the review package")
    previous_path = review_root / "review_manifest.json"
    previous = json.loads(previous_path.read_text(encoding="utf-8")) if previous_path.exists() else {}
    previous_by_id = {item["clip_id"]: item for item in previous.get("clips", [])}
    scanned = json.loads(manifest_path.read_text(encoding="utf-8"))
    ordered = sorted(scanned, key=lambda item: (item.get("creation_time") or "9999", item.get("filename", "").casefold(), item.get("path", "").casefold()))
    clips: list[dict[str, Any]] = []
    commands: list[list[str]] = []
    for index, item in enumerate(ordered, 1):
        relative = _source_relative(item["path"], raw)
        source = raw / Path(relative)
        file_size = source.stat().st_size
        identity = clip_id(relative, file_size)
        short_id = display_id(index)
        timestamps = thumbnail_timestamps(float(item.get("duration", 0)), thumbnail_count)
        thumbnail_refs = [f"thumbnails/{identity}-{number:03d}.jpg" for number in range(len(timestamps))]
        sheet_ref = f"contact_sheets/{short_id}-{identity}.jpg"
        proxy_ref = str((Path("proxy") / Path(relative).with_suffix(".mp4")).as_posix())
        clip = {
            "clip_id": identity,
            "display_id": short_id,
            "source": {"relative_path": relative},
            "duration_seconds": item.get("duration", 0),
            "width": item.get("width"),
            "height": item.get("height"),
            "orientation": orientation(item.get("width"), item.get("height"), item.get("rotation")),
            "rotation": item.get("rotation"),
            "fps": item.get("fps"),
            "codec": item.get("codec"),
            "has_audio": item.get("audio", False),
            "creation_time": item.get("creation_time"),
            "mtime_ns": source.stat().st_mtime_ns,
            "file_size": file_size,
            "proxy": {"relative_path": proxy_ref},
            "thumbnails": [{"index": number, "timestamp_seconds": timestamp, "relative_path": ref} for number, (timestamp, ref) in enumerate(zip(timestamps, thumbnail_refs))],
            "contact_sheet": {"relative_path": sheet_ref},
            "editorial": _editorial(previous_by_id.get(identity)),
        }
        clips.append(clip)
        changed = force or previous_by_id.get(identity, {}).get("mtime_ns") != clip["mtime_ns"]
        for thumb, timestamp in zip(thumbnail_refs, timestamps):
            output = _asset_path(review_root, thumb)
            if changed or not output.exists():
                commands.append(build_thumbnail_command(source, output, timestamp, f"{short_id} {timestamp:05.2f}", DEFAULT_THUMBNAIL_WIDTH))
        sheet_output = _asset_path(review_root, sheet_ref)
        if changed or not sheet_output.exists():
            list_path = review_root / f".{identity}.concat.txt"
            commands.append(build_contact_sheet_command(list_path, sheet_output, sheet_columns, math.ceil(len(timestamps) / sheet_columns)))
    if dry_run:
        return {"clips": clips, "commands": commands}
    (review_root / "thumbnails").mkdir(parents=True, exist_ok=True)
    (review_root / "contact_sheets").mkdir(parents=True, exist_ok=True)
    for clip in clips:
        changed = force or previous_by_id.get(clip["clip_id"], {}).get("mtime_ns") != clip["mtime_ns"]
        for thumbnail in clip["thumbnails"]:
            output = _asset_path(review_root, thumbnail["relative_path"])
            source = raw / Path(clip["source"]["relative_path"])
            if changed or not output.exists():
                _run(build_thumbnail_command(source, output, thumbnail["timestamp_seconds"], f"{clip['display_id']} {thumbnail['timestamp_seconds']:05.2f}", DEFAULT_THUMBNAIL_WIDTH), False)
        sheet = clip["contact_sheet"]["relative_path"]
        sheet_output = _asset_path(review_root, sheet)
        if not changed and sheet_output.exists():
            continue
        list_path = review_root / f".{clip['clip_id']}.concat.txt"
        lines = [f"file '{_asset_path(review_root, thumbnail['relative_path']).as_posix()}'" for thumbnail in clip["thumbnails"]]
        list_path.write_text("\n".join(lines), encoding="utf-8")
        try:
            _run(build_contact_sheet_command(list_path, sheet_output, sheet_columns, math.ceil(len(clip["thumbnails"]) / sheet_columns)), False)
        finally:
            list_path.unlink(missing_ok=True)
    portable = {"schema_version": SCHEMA_VERSION, "settings": {"thumbnail_width": DEFAULT_THUMBNAIL_WIDTH, "thumbnail_count": thumbnail_count, "contact_sheet_columns": sheet_columns}, "clips": clips}
    review_root.joinpath("review_manifest.json").write_text(json.dumps(portable, ensure_ascii=False, indent=2), encoding="utf-8")
    return portable
