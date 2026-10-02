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


def transcribe(output_path: Path, backend: str | None = None, dry_run: bool = False) -> dict[str, Any]:
    if backend:
        raise RuntimeError(f"Transcription backend {backend!r} is not installed; install and configure it explicitly")
    raise RuntimeError("No local transcription backend is configured. Transcription is optional; continue without it or supply a supported backend.")

