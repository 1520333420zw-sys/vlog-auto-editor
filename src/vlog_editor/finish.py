from __future__ import annotations

from typing import Any


def validate_finish_config(config: dict[str, Any]) -> dict[str, Any]:
    allowed = {"burn_subtitles", "audio_normalization", "auto_transcribe", "transcription_backend"}
    unknown = set(config) - allowed
    if unknown:
        raise ValueError(f"unknown finish configuration fields: {', '.join(sorted(unknown))}")
    for key in ("burn_subtitles", "audio_normalization", "auto_transcribe"):
        if key in config and not isinstance(config[key], bool):
            raise ValueError(f"{key} must be boolean")
    if "transcription_backend" in config and not isinstance(config["transcription_backend"], str):
        raise ValueError("transcription_backend must be a string")
    return config
