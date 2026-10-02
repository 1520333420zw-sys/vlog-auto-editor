from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from .common import parse_time, require_tool, resolve_workspace_path, run_json_command
from .audio import normalization_filter


def validate_plan(plan: dict) -> None:
    clips = plan.get("clips")
    if not isinstance(clips, list) or not clips:
        raise ValueError("rough_cut.json must contain a non-empty clips array")
    for index, clip in enumerate(clips):
        for key in ("source", "in", "out"):
            if key not in clip: raise ValueError(f"clip {index} is missing {key!r}")
        if parse_time(clip["out"]) <= parse_time(clip["in"]): raise ValueError(f"clip {index} out must be after in")


def audio_filter(clip: dict) -> str:
    if "audio" in clip:
        audio = clip["audio"]
        if audio == "source":
            return "anull"
        if audio == "mute":
            return "volume=0"
        if isinstance(audio, (int, float)) and not isinstance(audio, bool):
            return f"volume={float(audio):g}dB"
        raise ValueError("audio must be 'source', 'mute', or a numeric gain in dB")
    gain = clip.get("audio_gain_db", 0)
    return f"volume={gain}dB" if gain else "anull"


def build_filter(index: int, clip: dict, width: int, height: int, fps: int, output_index: int | None = None, normalize_audio: bool = False) -> str:
    label_index = index if output_index is None else output_index
    audio = audio_filter(clip)
    if normalize_audio:
        audio = f"{audio},{normalization_filter()}"
    return f"[{index}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps={fps},format=yuv420p[v{label_index}];[{index}:a]{audio}[a{label_index}]"


def render(project: Path, workspace: Path, dry_run: bool = False) -> list[str]:
    plan = json.loads(project.read_text(encoding="utf-8")); validate_plan(plan)
    require_tool("ffmpeg")
    settings = plan.get("video", {}); width = settings.get("width", 1920); height = settings.get("height", 1080); fps = settings.get("fps", 30)
    normalize_audio = plan.get("audio_normalization", False)
    if not isinstance(normalize_audio, bool):
        raise ValueError("audio_normalization must be boolean")
    output = resolve_workspace_path(plan.get("output", "workspace/output/VLOG_01_V1.mp4"), workspace)
    output.parent.mkdir(parents=True, exist_ok=True)
    command = ["ffmpeg", "-y"]
    filters = []
    input_index = 0
    for i, clip in enumerate(plan["clips"]):
        video_index = input_index
        source = resolve_workspace_path(clip["source"], workspace)
        command += ["-ss", str(parse_time(clip["in"])), "-to", str(parse_time(clip["out"])), "-i", str(source)]
        streams = run_json_command([require_tool("ffprobe"), "-v", "error", "-show_streams", "-of", "json", str(source)]).get("streams", [])
        has_audio = any(stream.get("codec_type") == "audio" for stream in streams)
        audio_index = input_index
        if not has_audio:
            command += ["-f", "lavfi", "-t", str(parse_time(clip["out"]) - parse_time(clip["in"])), "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
            audio_index = input_index + 1
            input_index += 1
        filters.append(build_filter(video_index, clip, width, height, fps, i, normalize_audio).replace(f"[{video_index}:a]", f"[{audio_index}:a]"))
        input_index += 1
    concat_inputs = "".join(f"[v{i}][a{i}]" for i in range(len(filters)))
    filters.append(f"{concat_inputs}concat=n={len(filters)}:v=1:a=1[vout][aout]")
    command += ["-filter_complex", ";".join(filters), "-map", "[vout]", "-map", "[aout]", "-c:v", "libx264", "-c:a", "aac", "-r", str(fps), "-movflags", "+faststart", str(output)]
    if not dry_run:
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode: raise RuntimeError(result.stderr.strip() or "ffmpeg render failed")
    return command
