# Automatic local vlog pipeline

The automatic milestone adds deterministic media analysis, optional local transcription handling, auditable candidate decisions, opt-in audio normalization, and a `build` orchestrator around the existing scan, proxy, review, plan, subtitle, and render commands.

Human `selected_ranges` and explicit `keep: false` decisions remain authoritative. Automatic decisions are stored in `workspace/project/autoedit.json`; they never silently overwrite the review manifest. Analysis is metadata-only and records unsupported signals explicitly. Transcription and subtitle generation are opt-in via build flags or `workspace/project/vlog_config.json`; neither is invoked when unconfigured. `build --dry-run` only reads existing inputs and writes nothing.

Generated artifacts remain under `workspace/` and raw media is never changed. The pipeline is intentionally conservative: hard cuts, short fallback ranges, source audio, no music, no semantic or AI claims, and no HDR-to-SDR conversion.
