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
```

## Phase 1

1. Scan media with ffprobe.
2. Build a machine-readable footage manifest.
3. Generate optional proxies.
4. Accept a human/AI-authored edit plan.
5. Render a deterministic rough cut with FFmpeg.
6. Generate/import bilingual subtitle tracks.
7. Export a 1080p review file.

The system is intentionally semi-automatic: editorial judgment remains with ChatGPT/user; automation handles repetitive media operations.