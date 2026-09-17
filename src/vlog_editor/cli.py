from __future__ import annotations

import argparse
from pathlib import Path

from .proxy import generate_proxies
from .render import render
from .scan import scan
from .subtitles import write_subtitles


def main() -> int:
    parser = argparse.ArgumentParser(prog="vlog-editor")
    parser.add_argument("--workspace", type=Path, default=Path("workspace"))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor"); sub.add_parser("init")
    scan_parser = sub.add_parser("scan"); scan_parser.add_argument("--workspace", type=Path, default=Path("workspace"), dest="scan_workspace")
    proxy_parser = sub.add_parser("proxy"); proxy_parser.add_argument("--force", action="store_true"); proxy_parser.add_argument("--dry-run", action="store_true")
    render_parser = sub.add_parser("render"); render_parser.add_argument("--project", type=Path, required=True); render_parser.add_argument("--dry-run", action="store_true")
    subtitle_parser = sub.add_parser("subtitles"); subtitle_parser.add_argument("--input", type=Path, required=True); subtitle_parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(); workspace = args.workspace
    if args.command == "doctor":
        from .common import require_tool
        for tool in ("python", "ffmpeg", "ffprobe"): print(f"{tool}: {require_tool(tool)}")
    elif args.command == "init":
        for name in ("raw", "proxy", "manifests", "project", "subtitles", "output", "transcripts"): (workspace / name).mkdir(parents=True, exist_ok=True)
    elif args.command == "scan": scan(args.scan_workspace / "raw", args.scan_workspace / "manifests")
    elif args.command == "proxy": generate_proxies(workspace / "raw", workspace / "proxy", args.force, args.dry_run)
    elif args.command == "render": render(args.project, workspace, args.dry_run)
    elif args.command == "subtitles": write_subtitles(args.input, args.output_dir or workspace / "subtitles")
    return 0
