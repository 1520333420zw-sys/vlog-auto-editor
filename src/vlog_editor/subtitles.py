from __future__ import annotations

import json
from pathlib import Path

from .common import parse_time


def srt_time(seconds: float) -> str:
    millis = round(seconds * 1000); hours, millis = divmod(millis, 3600000); minutes, millis = divmod(millis, 60000); secs, millis = divmod(millis, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def ass_time(seconds: float) -> str:
    hours, remainder = divmod(seconds, 3600); minutes, remainder = divmod(remainder, 60)
    return f"{int(hours)}:{int(minutes):02}:{remainder:05.2f}"


def write_subtitles(input_path: Path, output_dir: Path) -> tuple[Path, Path]:
    entries = json.loads(input_path.read_text(encoding="utf-8")); output_dir.mkdir(parents=True, exist_ok=True)
    srt = output_dir / f"{input_path.stem}.srt"; ass = output_dir / f"{input_path.stem}.ass"
    srt_lines = []
    ass_lines = ["[Script Info]", "ScriptType: v4.00+", "[V4+ Styles]", "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Alignment, MarginL, MarginR, MarginV, Encoding", "Style: Default,Arial,42,&H00FFFFFF,&H00FFFFFF,&H80000000,&H80000000,0,0,2,80,80,70,1", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    for i, entry in enumerate(entries, 1):
        start, end = parse_time(entry["start"]), parse_time(entry["end"])
        zh, en = entry.get("zh", ""), entry.get("en", "")
        srt_lines += [str(i), f"{srt_time(start)} --> {srt_time(end)}", f"{zh}\n{en}", ""]
        ass_lines += [f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Default,,0,0,0,,{zh}\\N{{\\fs32}}{en}"]
    srt.write_text("\n".join(srt_lines), encoding="utf-8"); ass.write_text("\n".join(ass_lines), encoding="utf-8")
    return srt, ass
