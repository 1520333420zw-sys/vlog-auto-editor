from __future__ import annotations

import argparse
import json
from pathlib import Path

from .plan import write_generated_plan
from .analyze import analyze_manifest
from .autoedit import plan_from_autoedit, write_autoedit
from .finish import validate_finish_config
from .proxy import generate_proxies
from .render import render
from .review import build_review_package
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
    plan_parser = sub.add_parser("plan"); plan_parser.add_argument("--input", type=Path); plan_parser.add_argument("--output", type=Path); plan_parser.add_argument("--dry-run", action="store_true")
    review_parser = sub.add_parser("review"); review_parser.add_argument("--force", action="store_true"); review_parser.add_argument("--dry-run", action="store_true"); review_parser.add_argument("--thumbnail-count", type=int, default=6); review_parser.add_argument("--sheet-columns", type=int, default=3)
    subtitle_parser = sub.add_parser("subtitles"); subtitle_parser.add_argument("--input", type=Path, required=True); subtitle_parser.add_argument("--output-dir", type=Path)
    analyze_parser = sub.add_parser("analyze"); analyze_parser.add_argument("--input", type=Path); analyze_parser.add_argument("--output", type=Path); analyze_parser.add_argument("--dry-run", action="store_true")
    transcribe_parser = sub.add_parser("transcribe"); transcribe_parser.add_argument("--output", type=Path); transcribe_parser.add_argument("--backend"); transcribe_parser.add_argument("--dry-run", action="store_true")
    autoedit_parser = sub.add_parser("autoedit"); autoedit_parser.add_argument("--review", type=Path); autoedit_parser.add_argument("--analysis", type=Path); autoedit_parser.add_argument("--output", type=Path); autoedit_parser.add_argument("--target-duration", type=float); autoedit_parser.add_argument("--dry-run", action="store_true")
    build_parser = sub.add_parser("build"); build_parser.add_argument("--force", action="store_true"); build_parser.add_argument("--dry-run", action="store_true"); build_parser.add_argument("--target-duration", type=float); build_parser.add_argument("--transcribe", action="store_true"); build_parser.add_argument("--subtitles", action="store_true"); build_parser.add_argument("--config", type=Path)
    args = parser.parse_args(); workspace = args.workspace
    if args.command == "doctor":
        from .common import require_tool
        for tool in ("python", "ffmpeg", "ffprobe"): print(f"{tool}: {require_tool(tool)}")
    elif args.command == "init":
        for name in ("raw", "proxy", "manifests", "project", "subtitles", "output", "transcripts"): (workspace / name).mkdir(parents=True, exist_ok=True)
    elif args.command == "scan": scan(args.scan_workspace / "raw", args.scan_workspace / "manifests")
    elif args.command == "proxy": generate_proxies(workspace / "raw", workspace / "proxy", args.force, args.dry_run)
    elif args.command == "plan":
        input_path = args.input or workspace / "review" / "review_manifest.json"
        output_path = args.output or workspace / "project" / "rough_cut.generated.json"
        plan = write_generated_plan(input_path, output_path, workspace, args.dry_run)
        if args.dry_run:
            print(json.dumps(plan, ensure_ascii=False, indent=2))
        else:
            print(f"Wrote {output_path}")
    elif args.command == "render": render(args.project, workspace, args.dry_run)
    elif args.command == "review": build_review_package(workspace, args.force, args.dry_run, args.thumbnail_count, args.sheet_columns)
    elif args.command == "subtitles": write_subtitles(args.input, args.output_dir or workspace / "subtitles")
    elif args.command == "analyze":
        artifact = analyze_manifest(args.input or workspace / "manifests" / "media_manifest.json", workspace, args.output or workspace / "analysis" / "media_analysis.json", args.dry_run)
        if args.dry_run: print(json.dumps(artifact, ensure_ascii=False, indent=2))
    elif args.command == "transcribe":
        from .transcript import transcribe
        transcribe(args.output or workspace / "transcript" / "transcript.json", args.backend, args.dry_run)
    elif args.command == "autoedit":
        artifact = write_autoedit(args.review or workspace / "review" / "review_manifest.json", args.output or workspace / "project" / "autoedit.json", args.analysis or workspace / "analysis" / "media_analysis.json", args.target_duration, args.dry_run)
        if args.dry_run: print(json.dumps(artifact, ensure_ascii=False, indent=2))
    elif args.command == "build":
        config_path = args.config or workspace / "project" / "vlog_config.json"
        config = validate_finish_config(json.loads(config_path.read_text(encoding="utf-8"))) if config_path.exists() else {}
        transcribe_enabled = args.transcribe or config.get("auto_transcribe", False)
        subtitles_enabled = args.subtitles or config.get("burn_subtitles", False)
        manifest_path = workspace / "manifests" / "media_manifest.json"
        review_path = workspace / "review" / "review_manifest.json"
        if args.dry_run:
            if not manifest_path.exists() or not review_path.exists():
                raise FileNotFoundError("build --dry-run requires existing manifests/review artifacts and will not create them")
            print("[dry-run] using existing scan and review artifacts")
        else:
            print("[1/5] scan")
            scan(workspace / "raw", workspace / "manifests")
            print("[2/5] review package")
            build_review_package(workspace, args.force, False)
        print("[3/5] analyze")
        analyze_manifest(workspace / "manifests" / "media_manifest.json", workspace, workspace / "analysis" / "media_analysis.json", args.dry_run)
        print("[4/5] automatic decisions")
        artifact = write_autoedit(review_path, workspace / "project" / "autoedit.json", workspace / "analysis" / "media_analysis.json", args.target_duration, args.dry_run)
        plan = plan_from_autoedit(artifact)
        plan["audio_normalization"] = config.get("audio_normalization", False)
        if args.dry_run:
            print(json.dumps(plan, ensure_ascii=False, indent=2))
        else:
            plan_path = workspace / "project" / "rough_cut.generated.json"
            plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print("[5/5] render")
            render(plan_path, workspace, False)
        transcript_path = workspace / "transcript" / "transcript.json"
        if transcribe_enabled:
            print("[optional] transcribe")
            from .transcript import transcribe
            transcribe(transcript_path, config.get("transcription_backend"), args.dry_run)
        else:
            print("[optional] transcribe skipped (not configured)")
        if subtitles_enabled:
            if not transcript_path.exists():
                raise FileNotFoundError("Subtitle generation was requested, but no transcript.json exists")
            if args.dry_run:
                print("[optional] subtitles would be generated from transcript.json")
            else:
                from .transcript import subtitle_source
                subtitle_input = subtitle_source(transcript_path)
                write_subtitles(subtitle_input, workspace / "subtitles")
        else:
            print("[optional] subtitles skipped (not configured)")
    return 0
