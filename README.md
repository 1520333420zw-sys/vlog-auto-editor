# Vlog Auto Editor

Semi-automated editing pipeline for horizontal study/life vlogs.

## Goal

Turn iPhone source footage into a reviewable V1 rough cut while keeping the creator in control of final aesthetic decisions.

Pipeline:

`iPhone footage -> scan -> manifest -> review -> human editorial decisions -> generated rough-cut plan -> rough cut -> bilingual subtitles -> V1 export -> Jianying/CapCut fine cut`

## Creative brief

- Format: 16:9 horizontal
- Output target: 1920x1080
- Subject: working full-time while preparing for the postgraduate entrance exam
- Tone: observational, calm, intimate, conversational
- Subtitles: Chinese primary + natural English secondary; should read like chatting with a friend, not formal narration
- Editing: restrained cuts and transitions; preserve useful room tone and everyday sound
- Avoid: rigid check-in style, motivational slogans, excessive transitions, over-editing

## Privacy

Raw video, proxy video, rendered outputs, personal footage, and local transcription data must not be committed to GitHub.

## Planned local workspace

```text
workspace/
  raw/          # original iPhone footage (local only)
  proxy/        # lightweight proxies (local only)
  manifests/    # generated metadata
  project/      # edit plans / timelines
  subtitles/    # bilingual subtitle files
  output/       # rendered V1 exports (local only)
  review/       # thumbnails, contact sheets, and review catalog (local only)
```

## Phase 1

1. Scan media with ffprobe.
2. Build a machine-readable footage manifest.
3. Generate optional proxies.
4. Accept a human/AI-authored edit plan.
5. Render a deterministic rough cut with FFmpeg.
6. Generate/import bilingual subtitle tracks.
7. Export a 1080p review file.

## Windows quick start

Install Python 3.11+ and FFmpeg (both `ffmpeg` and `ffprobe` must be on `PATH`). From PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m vlog_editor doctor
python -m vlog_editor init
Copy-Item examples\rough_cut.example.json workspace\project\rough_cut.json
Copy-Item examples\subtitles.example.json workspace\project\subtitles.json
python -m vlog_editor scan
python -m vlog_editor proxy
python -m vlog_editor review
python -m vlog_editor plan --dry-run
python -m vlog_editor plan
python -m vlog_editor render --project workspace\project\rough_cut.generated.json
python -m vlog_editor subtitles --input workspace\project\subtitles.json
```

Edit the sample JSON files to reference your own local clips and human-authored bilingual text. The renderer makes hard cuts on a 1920x1080/30fps canvas and preserves source audio where available. Subtitle generation never translates or invents text. A generated `.srt` and `.ass` can be reviewed in Jianying/CapCut; a burned-in review render is intentionally left to the editor in Phase 1.

## Review-to-plan workflow

After `scan` and `review`, inspect `workspace/review/review_manifest.json` and make human editorial decisions in each clip's `editorial` fields:

- Set `keep` to `true` to include a clip.
- Add `selected_ranges` to choose exact source ranges.
- Leave rejected or unreviewed clips without selected ranges to exclude them.

Generate a renderable plan:

```powershell
python -m vlog_editor plan --dry-run
python -m vlog_editor plan
python -m vlog_editor render --project workspace\project\rough_cut.generated.json
```

The planner reads `workspace/review/review_manifest.json` by default and writes `workspace/project/rough_cut.generated.json` by default. You can override paths:

```powershell
python -m vlog_editor plan --input workspace\review\review_manifest.json --output workspace\project\rough_cut.generated.json
```

Explicit `selected_ranges` always win over `keep`. Each range creates one segment and must satisfy `0 <= in < out <= duration_seconds`. Ranges may use `in`/`out` or `start`/`end`, with seconds or timestamp strings.

If `keep` is `true` and no ranges are supplied, the planner uses a conservative fallback range from `0` to `min(duration_seconds, 4.0)` seconds. This creates a short placeholder instead of silently selecting a long full clip.

Generated segments use `audio: "source"` to preserve source sound. Older hand-written plans that use `audio_gain_db` remain supported by the renderer.

The review manifest is the authority for which raw-media paths are represented at planning time. The planner requires each clip record to be an object, `source` to be an object, and `source.relative_path` to be a non-empty relative path. It rejects absolute paths, drive-qualified paths, and traversal outside `workspace/raw/`. It does not modify, move, rename, or delete source media.

Run tests with `python -m pytest`.

Known limitations: iPhone HDR/HEVC handling depends on the installed FFmpeg build and may require later color-management work; rotation metadata is collected and FFmpeg is asked to honor it, but unusual vendor metadata should be checked visually. Real media is required for an end-to-end render smoke test.

The system is intentionally semi-automatic: editorial judgment remains with ChatGPT/user; automation handles repetitive media operations.

## Automatic workflow

The coherent local pipeline can be run with:

```powershell
python -m vlog_editor build
```

It scans raw footage, creates or refreshes the review package, writes portable media analysis, creates an auditable automatic decision report, writes a deterministic rough-cut plan, and renders the V1 file. `--dry-run` reads existing manifest/review inputs and constructs the analysis/decision/plan output without writing any workspace artifact. Use `--force` to refresh review assets, and `--target-duration 300` for a best-effort target. Explicit review ranges and `keep: false` decisions remain authoritative; automatic fallback only fills undecided usable clips.

Additional commands are available independently:

```powershell
python -m vlog_editor analyze
python -m vlog_editor autoedit --target-duration 300
python -m vlog_editor transcribe
```

`analyze` writes `workspace/analysis/media_analysis.json` with deterministic probe metadata and explicitly marked unsupported signals. `autoedit` writes `workspace/project/autoedit.json`, including reasons, source identifiers, scores that are heuristic (not AI probabilities), and decision provenance. Optional stages are explicit: use `python -m vlog_editor build --transcribe` or `--subtitles`, or configure `auto_transcribe`, `burn_subtitles`, `transcription_backend`, and `audio_normalization` in `workspace/project/vlog_config.json`. Transcription reports a clear actionable error when the selected local backend is unavailable; leaving it unconfigured skips it. Subtitle files are generated only from an existing transcript and never translated automatically. Audio normalization is also strict opt-in. Generated reports, subtitle exports, and renders stay local and must not be committed.

The automatic milestone does not add music, semantic claims, aggressive silence cutting, transitions, color grading, or HDR-to-SDR conversion. Mixed dimensions and orientations continue through the renderer's 1920x1080 letterbox/pillarbox normalization and 30fps output. HDR/HEVC behavior remains dependent on the installed FFmpeg build and should be visually checked.
