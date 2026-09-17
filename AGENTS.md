# Codex implementation brief

## Product role

You are implementing repetitive media-engineering tasks for a semi-automated vlog editing workflow. Do not make irreversible aesthetic decisions. The user and ChatGPT remain the editors/directors.

## Phase 1 deliverable

Build a Windows-friendly Python CLI around FFmpeg/ffprobe that can:

1. `doctor` — verify Python, ffmpeg and ffprobe availability and print actionable setup errors.
2. `init` — create the local `workspace/` directory tree without touching existing media.
3. `scan` — recursively inspect `workspace/raw/` and write a JSON manifest containing filename, relative path, duration, width, height, fps, codec, audio presence, creation metadata when available, and rotation/orientation metadata.
4. `proxy` — generate lightweight 1080p-or-lower H.264 proxies while preserving aspect ratio and orientation. Never overwrite originals.
5. `render` — read `workspace/project/edit_plan.json`, trim specified source ranges, normalize them to a 1920x1080 16:9 delivery canvas, concatenate them, preserve source audio where possible, and export `workspace/output/VLOG_01_V1.mp4`.
6. `subtitles` — accept an explicitly supplied bilingual subtitle data file and create SRT plus an optional burned-in review render. Do not invent translations inside the CLI.

## Edit-plan contract

Create and document a JSON schema/example. Each clip should minimally support:

- `source`: path relative to `workspace/raw/`
- `in`: seconds
- `out`: seconds
- `audio`: `source`, `mute`, or numeric gain in dB
- optional `note`

The plan should include project settings such as output filename, 1920x1080, fps policy, and optional subtitle file.

## Creative constraints

- Horizontal 16:9 vlog.
- Calm observational pacing.
- No automatic flashy transitions.
- Hard cuts are the default.
- Preserve useful environmental sound.
- Never auto-add music.
- Never auto-delete original footage.
- Never commit raw footage, proxies, transcripts, subtitle exports containing personal speech, or rendered videos.

## Engineering requirements

- Python 3.11+.
- Prefer Python standard library; keep dependencies minimal.
- FFmpeg/ffprobe invoked through `subprocess` with argument arrays, never shell-concatenated commands.
- Paths must work on Windows and tolerate spaces/non-ASCII filenames.
- Fail safely and provide clear error messages.
- Add dry-run support where destructive/expensive work could occur.
- Add unit tests for parsing, validation, timeline duration calculations, and command construction where practical.
- Add a sample edit plan that references dummy filenames only.
- Update README with exact Windows setup and first-run commands.

## Acceptance criteria

A fresh Windows user who has Python and FFmpeg installed should be able to clone the repository, place iPhone videos under `workspace/raw/`, run scan, inspect the manifest, supply/edit an edit plan, and render a deterministic V1 rough cut without modifying original media.

Before declaring Phase 1 complete, run tests and report what was tested plus any limitations, especially iPhone HDR/HEVC/color-management limitations.