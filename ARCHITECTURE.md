# UltraSplitter Architecture

## Product contract

UltraSplitter produces usable subject assets from layouts that are not safe to split with equal rows and columns. The system preserves source pixels whenever possible and makes generated reconstruction an explicit, approved, and auditable escalation.

The core package is provider-neutral. A multimodal host such as Codex or Claude Code supplies semantic grouping, user interaction, image generation, and visual comparison. Python performs coordinates, masks, files, validation, provenance, and state transitions.

## Processing model

<img src="docs/assets/architecture.svg" alt="UltraSplitter agent-native processing architecture" width="100%">

### Scan

Panel candidates come from continuous divider/frame evidence. Object candidates come from background estimation, a simple foreground mask, and connected components. All coordinates refer to oriented source pixels; previews are for judgment only.

### Plan

The host treats deterministic candidates as planning evidence rather than the final inventory. It inspects the source and previews, inventories intended subjects and layout zones, then chooses a candidate set and groups stable region IDs into semantic items. Mixed layout systems, complex foreground/background overlap, multi-subject candidates, or materially ambiguous counts require scope alignment with the user before apply. If candidate IDs cannot express the confirmed scope, the host changes one justified scan assumption or exits explicitly instead of guessing coordinates.

Every clipped, contaminated, touching, or ambiguous candidate requires a `visual_assessment`. The host classifies it as `deliver`, `clean`, `repair`, or `ignore` and records visible completeness, whether the primary content remains recognizable, missing critical parts, identity confidence, and a visible-fraction estimate. The host should semantically reject text, captions, and watermarks, but recognition does not create a pixel mask: inseparable text/subject regions still require a source-pixel cleaning route, a better candidate set, or an unsupported result.

Generated repair requires all three gates: at least `0.65` of the subject is visibly retained, the primary content remains recognizable, and identity confidence is above `low`. A recognizable majority cannot be silently ignored; it is offered for approval-gated repair. Explicit user rejection may be recorded with `user_declined_repair: true`. Severely incomplete or identity-ambiguous fragments belong in `exclude_regions` plus structured `exclusions`; they are not output items and never become repair requests. Visible area alone is insufficient: missing identity-defining structure outweighs a large remaining pixel area.

### Route

The router does not equate bbox intersection with subject overlap:

- `source_crop`: complete source pixels and no relevant conflict.
- `source_composite`: distinct connected components have intersecting rectangular extents; only the selected component pixels are retained and centered on a clean canvas.
- `generated_reconstruction`: the host explicitly classifies a minor or moderately incomplete, identity-grounded subject as repairable.

Simple masks can remove foreign foreground; they cannot recover pixels hidden behind another object. Any operation that invents missing pixels must use the generated route.

An edge-contact flag without semantic assessment is not enough to authorize repair. It returns `needs_user_decision` with zero generation calls. A high-confidence assessment may also establish that a subject merely touches the canvas while remaining complete.

## Triage and delivery separation

The manifest separates four artifact roles:

- `delivery.images` contains only title-free production assets;
- `delivery.transparent_candidates` contains unapproved alpha variants and the legacy `alpha_images` field aliases those paths;
- `delivery.transparent_images` contains only alpha variants that passed automatic checks and an explicit independent visual verdict;
- `review/contact-sheet.png` is the named, automatically arranged delivery preview, not an alternate production asset;
- `review/triage-sheet.png` labels every retained candidate as `deliver`, `repair`, or `triage`, and shows structured exclusions as `ignore`;
- `delivery.pending_repair_images` and `delivery.ignored_images` remain review evidence and never masquerade as finished assets.

Contact sheets are review presentation artifacts, not alternate asset files. They use a compact near-square card grid, a uniform canvas, label-safe cells, and longest-edge subject normalization so mixed aspect ratios remain readable. Uniform-background trimming is applied only when corner and border evidence agree; otherwise the full image is preserved. The renderer never rewrites `delivery.images`. Layout metadata is recorded under `delivery.contact_sheet_layout` and `delivery.triage_sheet_layout`.

All routes converge on a primary delivery review gate. The host compares the confirmed inventory with the contact sheet and every individual delivery image. A failed candidate choice or plan returns to scan/plan with one named change; generated repair returns through ingest and the same review gate. Primary success requires both resolved manifest state and a visual `pass`. Repeated attempts are bounded by the failed cause rather than allowed to loop indefinitely.

Transparent candidates use a separate, optional gate after the primary asset passes. Before review, the runtime may add transparent-only canvas padding to reach the safe margin without resampling or changing subject pixels. The renderer presents every candidate on white, black, and checkerboard sheets. Automatic checks require a real alpha channel, transparent background, non-empty foreground, and at least `0.08` safe margin; interior transparency is surfaced for visual review because holes may be either legitimate geometry or erased light material. A transparent `pass` promotes paths into `delivery.transparent_images`. `retryable` or `reject` keeps them out without invalidating an already accepted primary asset.

Before a repair packet is prepared, simple-mask isolation removes unrelated disconnected foreground from each repair reference. The original expanded dispute region remains available as `context.png`; the clean subject montage is `source.png`.

## Conflict groups and repair packets

Generation candidates become nodes in a spatial conflict graph. Expanded source boxes create edges and connected components form repair groups. Isolated candidates with the same reason are batch-packed so the system does not make one generation call per subject. Groups are capped at six subjects. Spatially sparse groups use a reference montage instead of an unreadable ultra-wide crop. Every group defines an exact row-major order and near-square layout with a target of at least 512 pixels per cell.

`repair prepare` emits, per group:

- a clean, isolated source montage;
- an expanded original context crop;
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

The manifest contains the source hash, scan and plan, output items, structured exclusions, route evidence, conflict groups, approval scope, repair attempts, evaluations, warnings, and delivery paths. It reports `deliverable_count`, `repair_candidate_count`, and `ignored_count`. Each retained item records exactly one origin:

- `source_crop`;
- `source_composite`;
- `generated_reconstruction` with group and attempt metadata.

Generated pixels are always marked `completion_is_inferred: true`. They are never described as extracted or restored source truth.

## States and failure policy

Public states are `success`, `needs_review`, `awaiting_user_approval`, `needs_user_decision`, `retry_exhausted`, `unsupported`, and `failed`.

Exit code `0` means success, `2` means a valid artifact exists but human or agent attention remains, `10` means invalid input or contract, and `20` means an unexpected processing failure. Partial artifacts are retained for diagnosis.

## Security and compatibility

The package contains no provider credentials and makes no network calls. Input bytes are hashed between scan and apply. Existing outputs are not overwritten unless explicitly requested. v0.1.0 reads and writes schema v3 only; schema v2 callers must migrate or keep using the earlier standalone script.
