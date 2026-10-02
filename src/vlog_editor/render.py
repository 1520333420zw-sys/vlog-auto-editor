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


def _escape_filter_path(path: str | Path) -> str:
    return str(path).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def _portrait_video_filter(index: int, label: int, width: int, height: int, lut: str | None = None) -> str:
    lut_filter = f",lut3d=file='{_escape_filter_path(lut)}'" if lut else ""
    return f"[{index}:v]split=2[bg{label}][fg{label}];[bg{label}]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},gblur=sigma=18[bgfit{label}];[fg{label}]scale={width}:{height}:force_original_aspect_ratio=decrease[fgfit{label}];[bgfit{label}][fgfit{label}]overlay=(W-w)/2:(H-h)/2{lut_filter},fps={{fps}},format=yuv420p[v{label}]"


def _landscape_video_filter(index: int, label: int, width: int, height: int, fps: int, lut: str | None = None) -> str:
    lut_filter = f",lut3d=file='{_escape_filter_path(lut)}'" if lut else ""
    return f"[{index}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2{lut_filter},fps={fps},format=yuv420p[v{label}]"


def build_filter(index: int, clip: dict, width: int, height: int, fps: int, output_index: int | None = None, normalize_audio: bool = False, portrait: bool = False, lut: str | None = None) -> str:
    label_index = index if output_index is None else output_index
    audio = audio_filter(clip)
    if normalize_audio:
        audio = f"{audio},{normalization_filter()}"
    video = _portrait_video_filter(index, label_index, width, height, lut).replace("fps={fps}", f"fps={fps}") if portrait else _landscape_video_filter(index, label_index, width, height, fps, lut)
    return f"{video};[{index}:a]{audio}[a{label_index}]"


def _is_portrait(stream: dict) -> bool:
    width, height = stream.get("width"), stream.get("height")
    rotation = 0
    tags = stream.get("tags", {})
    side_data = stream.get("side_data_list", [])
    raw_rotation = tags.get("rotate") or (side_data[0].get("rotation") if side_data else 0)
    try:
        rotation = int(raw_rotation or 0) % 360
    except (TypeError, ValueError):
        pass
    if rotation in {90, 270}:
        width, height = height, width
    return bool(width and height and height > width)


def build_bgm_filter(input_index: int, duration: float, gain_db: float) -> str:
    fade = min(0.5, duration / 2.0)
    end = max(0.0, duration - fade)
    return f"[{input_index}:a]atrim=duration={duration:.3f},asetpts=N/SR/TB,volume={gain_db:g}dB,afade=t=in:st=0:d={fade:.3f},afade=t=out:st={end:.3f}:d={fade:.3f}[bgm];[aout][bgm]amix=inputs=2:duration=first:dropout_transition=2,alimiter=limit=0.95[aoutmix]"


def render(project: Path, workspace: Path, dry_run: bool = False) -> list[str]:
    plan = json.loads(project.read_text(encoding="utf-8")); validate_plan(plan)
    require_tool("ffmpeg")
    settings = plan.get("video", {}); width = settings.get("width", 1920); height = settings.get("height", 1080); fps = settings.get("fps", 30)
    normalize_audio = plan.get("audio_normalization", False)
    if not isinstance(normalize_audio, bool):
        raise ValueError("audio_normalization must be boolean")
    output = resolve_workspace_path(plan.get("output", "workspace/output/VLOG_01_V1.mp4"), workspace)
    lut = plan.get("lut")
    if lut:
        lut_path = Path(lut)
        if not lut_path.is_absolute():
            lut_path = resolve_workspace_path(lut_path, workspace)
        if lut_path.suffix.lower() != ".cube" or not lut_path.is_file():
            raise ValueError("lut must reference an existing local .cube file")
        lut = str(lut_path)
    bgm = plan.get("bgm")
    bgm_path = None
    bgm_gain = -18.0
    if bgm:
        if isinstance(bgm, dict):
            bgm_path = Path(bgm.get("path", "")); bgm_gain = bgm.get("gain_db", -18.0)
        else:
            bgm_path = Path(bgm)
        if not bgm_path.is_absolute():
            bgm_path = resolve_workspace_path(bgm_path, workspace)
        if not bgm_path.is_file() or not isinstance(bgm_gain, (int, float)) or isinstance(bgm_gain, bool) or bgm_gain > 0 or bgm_gain < -60:
            raise ValueError("bgm must reference an existing local audio file with gain between -60 and 0 dB")
    subtitle_file = plan.get("subtitle_file")
    if subtitle_file:
        subtitle_path = Path(subtitle_file)
        if not subtitle_path.is_absolute():
            subtitle_path = resolve_workspace_path(subtitle_path, workspace)
        if not subtitle_path.is_file():
            raise ValueError("subtitle_file must reference an existing subtitle file")
        subtitle_file = str(subtitle_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    command = ["ffmpeg", "-y"]
    filters = []
    input_index = 0
    for i, clip in enumerate(plan["clips"]):
        video_index = input_index
        source = resolve_workspace_path(clip["source"], workspace)
        command += ["-ss", str(parse_time(clip["in"])), "-to", str(parse_time(clip["out"])), "-i", str(source)]
        streams = run_json_command([require_tool("ffprobe"), "-v", "error", "-show_streams", "-of", "json", str(source)]).get("streams", [])
        video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), {})
        has_audio = any(stream.get("codec_type") == "audio" for stream in streams)
        audio_index = input_index
        if not has_audio:
            command += ["-f", "lavfi", "-t", str(parse_time(clip["out"]) - parse_time(clip["in"])), "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
            audio_index = input_index + 1
            input_index += 1
        filters.append(build_filter(video_index, clip, width, height, fps, i, normalize_audio, _is_portrait(video_stream), lut).replace(f"[{video_index}:a]", f"[{audio_index}:a]"))
        input_index += 1
    concat_inputs = "".join(f"[v{i}][a{i}]" for i in range(len(filters)))
    clip_count = len(filters)
    filters.append(f"{concat_inputs}concat=n={clip_count}:v=1:a=1[vout][aout]")
    video_label = "vout"
    if subtitle_file:
        filters.append(f"[vout]subtitles=filename='{_escape_filter_path(subtitle_file)}'[vsub]")
        video_label = "vsub"
    audio_label = "aout"
    duration = sum(parse_time(clip["out"]) - parse_time(clip["in"]) for clip in plan["clips"])
    if bgm_path:
        bgm_index = input_index
        command += ["-stream_loop", "-1", "-i", str(bgm_path)]
        filters.append(build_bgm_filter(bgm_index, duration, float(bgm_gain)))
        audio_label = "aoutmix"
    command += ["-filter_complex", ";".join(filters), "-map", f"[{video_label}]", "-map", f"[{audio_label}]", "-c:v", "libx264", "-c:a", "aac", "-r", str(fps), "-movflags", "+faststart", str(output)]
    if not dry_run:
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode: raise RuntimeError(result.stderr.strip() or "ffmpeg render failed")
    return command
