# Vlog Auto Editor

Semi-automated editing pipeline for horizontal study/life vlogs.

## Goal

Turn iPhone source footage into a reviewable V1 rough cut while keeping the creator in control of final aesthetic decisions.

Pipeline:

`iPhone footage -> scan -> manifest -> edit plan -> rough cut -> bilingual subtitles -> V1 export -> Jianying/CapCut fine cut`

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
python -m vlog_editor render --project workspace\project\rough_cut.json
python -m vlog_editor subtitles --input workspace\project\subtitles.json
```

Edit the sample JSON files to reference your own local clips and human-authored bilingual text. The renderer makes hard cuts on a 1920x1080/30fps canvas and preserves source audio where available. Subtitle generation never translates or invents text. A generated `.srt` and `.ass` can be reviewed in Jianying/CapCut; a burned-in review render is intentionally left to the editor in Phase 1.

Run tests with `python -m pytest`.

Known limitations: iPhone HDR/HEVC handling depends on the installed FFmpeg build and may require later color-management work; rotation metadata is collected and FFmpeg is asked to honor it, but unusual vendor metadata should be checked visually. Real media is required for an end-to-end render smoke test.

The system is intentionally semi-automatic: editorial judgment remains with ChatGPT/user; automation handles repetitive media operations.
