from __future__ import annotations

from typing import Any


def validate_finish_config(config: dict[str, Any]) -> dict[str, Any]:
    allowed = {"generate_subtitles", "burn_subtitles", "audio_normalization", "transcript_path", "bgm_path", "bgm_gain_db", "lut_path"}
    unknown = set(config) - allowed
    if unknown:
        raise ValueError(f"unknown finish configuration fields: {', '.join(sorted(unknown))}")
    for key in ("generate_subtitles", "burn_subtitles", "audio_normalization"):
        if key in config and not isinstance(config[key], bool):
            raise ValueError(f"{key} must be boolean")
    for key in ("transcript_path", "bgm_path", "lut_path"):
        if key in config and not isinstance(config[key], str):
            raise ValueError(f"{key} must be a string")
    if "bgm_gain_db" in config and (not isinstance(config["bgm_gain_db"], (int, float)) or isinstance(config["bgm_gain_db"], bool) or not -60 <= config["bgm_gain_db"] <= 0):
        raise ValueError("bgm_gain_db must be between -60 and 0")
    return config
