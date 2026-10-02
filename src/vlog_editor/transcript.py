from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def validate_transcript(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        raise ValueError("transcript must contain an entries array")
    for index, entry in enumerate(data["entries"], 1):
        if not isinstance(entry, dict) or not isinstance(entry.get("text"), str):
            raise ValueError(f"transcript entry {index} must contain text")
        start, end = entry.get("start"), entry.get("end")
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)) or start < 0 or start >= end:
            raise ValueError(f"transcript entry {index} has invalid timestamps")
    return data


def import_transcript(input_path: Path, output_path: Path, dry_run: bool = False) -> dict[str, Any]:
    data = validate_transcript(json.loads(input_path.read_text(encoding="utf-8")))
    if not dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return data


def subtitle_source(transcript_path: Path, output: Path, dry_run: bool = False) -> Path:
    data = validate_transcript(json.loads(transcript_path.read_text(encoding="utf-8")))
    entries = [{"start": item["start"], "end": item["end"], "zh": item["text"], "en": item.get("translation", "")} for item in data["entries"]]
    if not dry_run:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output

