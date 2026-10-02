from __future__ import annotations

from typing import Any


def validate_finish_config(config: dict[str, Any]) -> dict[str, Any]:
    allowed = {"generate_subtitles", "audio_normalization", "transcript_path"}
    unknown = set(config) - allowed
    if unknown:
        raise ValueError(f"unknown finish configuration fields: {', '.join(sorted(unknown))}")
    for key in ("generate_subtitles", "audio_normalization"):
        if key in config and not isinstance(config[key], bool):
            raise ValueError(f"{key} must be boolean")
    if "transcript_path" in config and not isinstance(config["transcript_path"], str):
        raise ValueError("transcript_path must be a string")
    return config
