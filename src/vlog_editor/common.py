from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


MEDIA_EXTENSIONS = {".mov", ".mp4", ".m4v"}


def parse_time(value: Any) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        result = float(value)
    elif isinstance(value, str):
        parts = value.strip().split(":")
        try:
            if len(parts) == 1:
                result = float(parts[0])
            elif len(parts) == 2:
                result = float(parts[0]) * 60 + float(parts[1])
            elif len(parts) == 3:
                result = float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
            else:
                raise ValueError
        except ValueError as exc:
            raise ValueError(f"Invalid time value: {value!r}") from exc
    else:
        raise ValueError(f"Invalid time value: {value!r}")
    if result < 0:
        raise ValueError("Time values cannot be negative")
    return result


def parse_fps(value: str | None) -> float | None:
    if not value or value in {"0/0", "N/A"}:
        return None
    try:
        numerator, denominator = value.split("/", 1)
        return float(numerator) / float(denominator)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError(f"Invalid frame rate: {value!r}") from exc


def require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"{name} was not found on PATH. Install FFmpeg and reopen the terminal.")
    return path


def run_json_command(args: list[str]) -> dict[str, Any]:
    completed = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"Command failed ({completed.returncode}): {' '.join(args)}\n{detail}")
    return json.loads(completed.stdout)


def resolve_workspace_path(value: str | Path, workspace: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    if path.parts and path.parts[0].lower() == workspace.name.lower():
        return workspace.parent.joinpath(*path.parts)
    return workspace.joinpath(path)
