from __future__ import annotations

from .render import audio_filter


def normalization_filter() -> str:
    """Conservative deterministic loudness normalization for future filter composition."""
    return "loudnorm=I=-16:TP=-1.5:LRA=11:linear=true"
