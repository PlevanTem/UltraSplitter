# UltraSplitter Architecture

## Product contract

UltraSplitter produces usable subject assets from layouts that are not safe to split with equal rows and columns. The system preserves source pixels whenever possible and makes generated reconstruction an explicit, approved, and auditable escalation.

The core package is provider-neutral. A multimodal host such as Codex or Claude Code supplies semantic grouping, user interaction, image generation, and visual comparison. Python performs coordinates, masks, files, validation, provenance, and state transitions.

## Processing model

```text
SCAN → PLAN → APPLY → ROUTE
                        ├─ source_crop ───────────────┐
                        ├─ source_composite ──────────┤
                        └─ generated_reconstruction  │
                                   ↓                 │
                         awaiting_user_approval      │
                                   ↓                 │
                         PREPARE → GENERATE → INGEST │
                                               ↓     │
                                            EVALUATE ┘
                                               ↓
                                  success / bounded exit
```

### Scan

Panel candidates come from continuous divider/frame evidence. Object candidates come from background estimation, a simple foreground mask, and connected components. All coordinates refer to oriented source pixels; previews are for judgment only.

### Plan

The host chooses a candidate set and groups stable region IDs into semantic items. It may add `visual_assessment` when visible evidence shows clipping, occlusion, touching subjects, or multiple semantic subjects inside one connected component.

### Route

The router does not equate bbox intersection with subject overlap:

- `source_crop`: complete source pixels and no relevant conflict.
- `source_composite`: distinct connected components have intersecting rectangular extents; only the selected component pixels are retained and centered on a clean canvas.
- `generated_reconstruction`: the source is clipped or the visual assessment reports missing, occluded, touching, or merged subjects.

Simple masks can remove foreign foreground; they cannot recover pixels hidden behind another object. Any operation that invents missing pixels must use the generated route.

## Conflict groups and repair packets

Generation candidates become nodes in a spatial conflict graph. Expanded source boxes create edges and connected components form repair groups. Isolated candidates with the same reason are batch-packed so the system does not make one generation call per subject. Groups are capped at six subjects. Spatially sparse groups use a reference montage instead of an unreadable ultra-wide crop. Every group defines an exact row-major order and near-square layout with a target of at least 512 pixels per cell.

`repair prepare` emits, per group:

- an expanded source crop;
- a target-ID preview;
- exact target count, order, and layout;
- a constrained reconstruction prompt;
- a request JSON and prompt hash.

Preparation never invokes a model. The manifest moves to `awaiting_user_approval`. `repair ingest` rejects a grid unless that exact group is recorded as approved.

## Evaluation and bounded loop

Deterministic grid checks cover dimensions, expected occupied cells, uniform background, edge contact, minimum margin, and obvious duplicate cells. A multimodal host then compares every reconstructed subject with the visible source anchors: identity, pose, silhouette, color, material, ornament, and absence of redesign.

Visual verdicts are:

- `pass`: all deterministic and identity checks pass;
- `retryable`: prompt-correctable layout or detail failure;
- `identity_uncertain`: user judgment is required.

Each conflict group permits at most two ingested attempts. A second failed attempt ends in `retry_exhausted`; the system retains both attempts and never loops indefinitely.

## Schema v3 and provenance

The manifest contains the source hash, scan and plan, output items, route evidence, conflict groups, approval scope, repair attempts, evaluations, warnings, and delivery paths. Each item records exactly one origin:

- `source_crop`;
- `source_composite`;
- `generated_reconstruction` with group and attempt metadata.

Generated pixels are always marked `completion_is_inferred: true`. They are never described as extracted or restored source truth.

## States and failure policy

Public states are `success`, `needs_review`, `awaiting_user_approval`, `needs_user_decision`, `retry_exhausted`, `unsupported`, and `failed`.

Exit code `0` means success, `2` means a valid artifact exists but human or agent attention remains, `10` means invalid input or contract, and `20` means an unexpected processing failure. Partial artifacts are retained for diagnosis.

## Security and compatibility

The package contains no provider credentials and makes no network calls. Input bytes are hashed between scan and apply. Existing outputs are not overwritten unless explicitly requested. v0.1.0 reads and writes schema v3 only; schema v2 callers must migrate or keep using the earlier standalone script.
