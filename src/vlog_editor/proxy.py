from __future__ import annotations

import subprocess
from pathlib import Path

from .common import MEDIA_EXTENSIONS, require_tool, run_json_command


def generate_proxies(raw: Path, output: Path, force: bool = False, dry_run: bool = False) -> list[list[str]]:
    require_tool("ffmpeg")
    commands = []
    for source in sorted(p for p in raw.rglob("*") if p.is_file() and p.suffix.lower() in MEDIA_EXTENSIONS):
        target = output / source.relative_to(raw).with_suffix(".mp4")
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and not force and target.stat().st_mtime >= source.stat().st_mtime:
            continue
        probe = run_json_command([require_tool("ffprobe"), "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=codec_type", "-of", "json", str(source)])
        command = ["ffmpeg", "-y", "-i", str(source), "-vf", "scale='min(1280,iw)':'min(1280,ih)':force_original_aspect_ratio=decrease,fps=30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "28"]
        if probe.get("streams"):
            command += ["-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(target)]
        commands.append(command)
        if not dry_run:
            completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
            if completed.returncode:
                raise RuntimeError(completed.stderr.strip() or "ffmpeg proxy generation failed")
    return commands
