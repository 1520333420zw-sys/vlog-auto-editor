from __future__ import annotations

from typing import Any


def validate_finish_config(config: dict[str, Any]) -> dict[str, Any]:
    allowed = {"burn_subtitles", "audio_normalization", "fade_in_seconds", "fade_out_seconds"}
    unknown = set(config) - allowed
    if unknown:
        raise ValueError(f"unknown finish configuration fields: {', '.join(sorted(unknown))}")
    for key in ("fade_in_seconds", "fade_out_seconds"):
        if key in config and (not isinstance(config[key], (int, float)) or config[key] < 0):
            raise ValueError(f"{key} must be non-negative")
    return config
