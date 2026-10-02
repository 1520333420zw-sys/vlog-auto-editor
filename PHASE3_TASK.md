# Codex Task — Phase 3: Review-to-Rough-Cut Planning Pipeline

## Scope

Connect the Phase 2 review package to the Phase 1 render pipeline by converting human editorial decisions in `workspace/review/review_manifest.json` into a deterministic, renderable rough-cut plan at `workspace/project/rough_cut.generated.json`.

Phase 3 is a planning bridge. It does not make automatic creative decisions beyond conservative, documented defaults.

## Non-goals

- Speech-to-text.
- Automatic highlight detection.
- Automatic semantic clip selection.
- Background music.
- Transitions.
- Color grading.
- Publishing.
- Jianying/CapCut project generation.
- External AI APIs.
- New heavyweight dependencies.

## Input contract

The planner reads the Phase 2 review manifest. The review manifest is treated as the authority for which raw-media paths are represented at planning time; the planner validates the manifest shape and raw-tree boundary, but it does not rediscover sources independently.

Each entry in `clips` must be an object. Each clip is expected to include:

- `display_id` and/or `clip_id` for actionable errors and audit fields.
- `source`, as an object.
- `source.relative_path`, as a non-empty relative path under `workspace/raw/`.
- `duration_seconds`.
- `editorial.keep`.
- `editorial.selected_ranges`.
- optional `editorial.notes`.

Selected ranges may use either `in`/`out` or `start`/`end` values. Time values follow the existing rough-cut parser and may be seconds or `HH:MM:SS.sss` strings.

## Selection rules

A clip is eligible when:

- `editorial.keep == true`, or
- `editorial.selected_ranges` contains at least one valid range.

Explicit `selected_ranges` always take precedence. If ranges exist, the planner creates one rough-cut segment for each range and preserves the authored range order.

If `keep == true` and no ranges exist, the fallback range is `0` to `min(duration_seconds, 4.0)`. This avoids silently selecting an arbitrarily long full clip while keeping a short, inspectable placeholder for human refinement.

Rejected or unreviewed clips without selected ranges are excluded.

## Ordering rules

The planner preserves review-manifest clip order. Within each clip, it preserves selected range order. Phase 3 does not add automatic chronology, semantic sorting, or quality ranking.

## Range rules

Each explicit selected range must satisfy:

```text
0 <= in < out <= duration_seconds
```

The planner rejects negative, zero-length, reversed, malformed, non-numeric, and over-duration ranges. Errors identify the relevant display ID or clip ID and range number.

## Output contract

The generated plan is compatible with the existing renderer:

- `output`
- `video.width`
- `video.height`
- `video.fps`
- `clips[].source`
- `clips[].in`
- `clips[].out`
- `clips[].audio`

Generated segments use `audio: "source"` by default to preserve source sound. They may also include audit fields that the renderer ignores safely:

- `note`
- `display_id`
- `clip_id`

## Safety rules

Generated sources must resolve inside `workspace/raw/` and originate from `source.relative_path` in the review manifest. The planner rejects malformed clip/source records, empty source paths, absolute paths, drive-qualified paths, and path traversal. It never modifies, moves, renames, or deletes source media.

`--dry-run` validates input and constructs the exact logical plan without writing the output file.

## Acceptance criteria

- `python -m vlog_editor plan` reads `workspace/review/review_manifest.json`.
- By default it writes `workspace/project/rough_cut.generated.json`.
- `--input`, `--output`, and `--dry-run` are supported.
- Eligible clips and selected ranges are converted deterministically.
- Invalid ranges fail clearly.
- Source paths are constrained to `workspace/raw/`.
- Generated plans render with the existing `render` command.
- Existing Phase 1 rough-cut files using `audio_gain_db` remain compatible.
- Tests cover selection, fallback, ordering, validation, source safety, determinism, dry-run, CLI wiring, render compatibility, and backward compatibility.
