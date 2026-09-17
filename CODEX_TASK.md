# Codex Task — Phase 1: Local Vlog Rough-Cut Pipeline

## Goal
Build a Windows-friendly, local-first Python + FFmpeg pipeline that prepares iPhone vlog footage for a human-directed rough cut. Never upload raw media to GitHub.

## Creative contract
- 16:9 horizontal master, 1920x1080, 30 fps.
- Calm observational study/work vlog.
- Preserve useful ambience; avoid aggressive transitions.
- Bilingual subtitles: conversational Chinese primary line, natural English secondary line.
- Final aesthetic polish happens in Jianying/CapCut; this tool produces a clean V1 rough cut.

## Required Phase 1 deliverables
1. `src/vlog_editor/scan.py`
   - Recursively scan `workspace/raw/` for MOV/MP4/M4V.
   - Call `ffprobe` and collect: path, filename, duration, width, height, fps, codec, audio presence, creation time when available, rotation/orientation when available.
   - Write UTF-8 `workspace/manifests/media_manifest.json` and `.csv`.
   - Sort deterministically by creation time then filename.
   - Fail clearly when FFmpeg/ffprobe is missing.

2. `src/vlog_editor/proxy.py`
   - Optional proxy generation into `workspace/proxy/`.
   - Preserve aspect ratio and orientation.
   - Target review proxies: H.264, max 1280px long edge, 30 fps, AAC audio when present.
   - Skip up-to-date proxies unless `--force` is supplied.

3. `src/vlog_editor/render.py`
   - Read a human-authored `workspace/project/rough_cut.json`.
   - Timeline entries contain `source`, `in`, `out`, optional `audio_gain_db`.
   - Normalize each selected clip to 1920x1080/30fps without stretching; letterbox/pillarbox only when required.
   - Concatenate clips and export H.264/AAC MP4 to `workspace/output/VLOG_01_V1.mp4`.
   - Preserve source ambience by default.
   - No automatic transitions in Phase 1.

4. `src/vlog_editor/subtitles.py`
   - Read `workspace/project/subtitles.json` with start/end/zh/en.
   - Export bilingual UTF-8 SRT and ASS.
   - ASS should visually distinguish Chinese primary and English secondary lines but remain restrained and readable.
   - Do not invent or machine-translate subtitle text; text is human/assistant-authored input.

5. CLI
   - `python -m vlog_editor scan`
   - `python -m vlog_editor proxy`
   - `python -m vlog_editor render --project workspace/project/rough_cut.json`
   - `python -m vlog_editor subtitles --input workspace/project/subtitles.json`
   - Provide useful `--help` and actionable errors.

6. Project setup
   - `pyproject.toml`, package layout, Windows setup instructions, sample JSON templates under `examples/`, and lightweight tests that do not require real personal video.
   - Keep dependencies minimal; standard library preferred for orchestration.

## Safety/privacy requirements
- Never commit files under `workspace/raw`, `workspace/proxy`, `workspace/output`, or generated subtitle/transcript files.
- Do not add cloud upload, telemetry, face recognition, or automatic publishing.
- Do not delete or modify original footage.
- Shell commands must quote Windows paths safely.

## Acceptance criteria
- A user can copy iPhone clips into `workspace/raw/`, run scan, inspect the manifest, author/select a rough-cut JSON, render V1, and export bilingual subtitle files.
- Unit tests cover time parsing, fps parsing, manifest ordering, timeline validation, and subtitle formatting.
- README documents exact Windows commands and the workflow from iPhone footage to Jianying/CapCut.

## Not in Phase 1
Automatic clip selection, speech-to-text, BGM selection, color grading, beat cuts, transitions, social-media publishing, or direct Jianying project generation.
