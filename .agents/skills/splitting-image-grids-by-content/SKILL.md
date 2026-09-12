---
name: splitting-image-grids-by-content
description: Split framed image grids and simple-background object collages into user-accessible assets, preserving source pixels when possible and preparing approval-gated repair grids when clipping, occlusion, or touching subjects require generated reconstruction.
---

# Split Images by Content

Use the host model for semantic judgment and UltraSplitter for exact source-pixel operations. Do not estimate final crop coordinates from a resized model view.

## CLI runtime

Prefer an existing `ultrasplit` command. In an UltraSplitter checkout, use the repository-local wrapper at `.agents/skills/splitting-image-grids-by-content/scripts/ultrasplit.py`. If this Skill was installed independently and the runtime is missing, install it into the active Python environment with `python -m pip install git+https://github.com/PlevanTem/UltraSplitter.git`, using the host's normal permission flow for package installation, then continue the requested split. Do not replace an existing installed version silently.

This section only explains how to launch the deterministic CLI. It does not replace the host model's semantic planning or declare the Python package dependencies.

## Decision flow

```text
scan -> inspect source + candidate previews -> inventory intended assets
  |- scope is materially ambiguous -> align the proposed asset scope with the user
  |- candidate IDs cannot express the scope -> rescan with one justified change or stop unsupported
  `- scope and candidates are sufficient -> write plan -> apply
                                                    |
                                                    v
                         inspect contact sheet + every delivery image
                           |- pass all success conditions -> deliver
                           |- candidate/plan failure -> revise -> apply and review again
                           `- missing source pixels -> approval-gated repair -> ingest -> review again
```

## Workflow

1. Infer `panels` for framed grids/turnarounds and `objects` for separated subjects on a simple background, then run `ultrasplit scan`. Treat deterministic regions as evidence for planning, not as the final asset inventory.
2. Inspect the full-resolution source and every numbered candidate preview. Inventory the intended subjects or views, their names and order, distinct layout zones, foreground/background semantic overlap, decorative text, captions, watermarks, occlusion, and shared ownership before writing a plan.
3. Align the proposed asset scope with the user before `apply` when the image mixes layout systems, contains complex foreground/background overlap, places multiple semantic subjects in one candidate, or leaves the intended count or ownership materially ambiguous. Show the proposed asset list and exclusions. Do not add this confirmation step for a simple, unambiguous sheet.
4. If the available candidate IDs cannot express the confirmed scope, do not guess crop coordinates or force a lossy plan. Rescan with one justified change to mode, layout hint, tolerance, or scale. If the same coverage failure remains after two concrete revisions, stop with `unsupported` or `needs_user_decision` and name the missing detection capability.
5. Read [references/plan-schema.md](references/plan-schema.md), then write a semantic plan using exact candidate and region IDs. For every clipped, contaminated, touching, or ambiguous candidate, add `visual_assessment` and choose `deliver`, `clean`, or `repair`. Exclude non-subject text and severe or identity-ambiguous fragments. Recognizable clipped content at or above the repair threshold must be offered for repair instead of silently ignored.
6. Run `ultrasplit apply`. Inspect the source, `review/triage-sheet.png`, the named and automatically arranged `review/contact-sheet.png`, and every file in `delivery.images`. Preview labels and cards must never be burned into an individual delivery asset. When transparent candidates exist, the runtime may add transparent-only canvas padding without changing subject pixels; inspect the resulting white, black, and checkerboard sheets under `delivery.transparent_review_sheets`.
7. Accept a source crop or composite only when the confirmed asset count and names match, each subject is complete and uncontaminated, identity and view are correct, no unintended text, caption, watermark, border, duplicate, or foreign foreground remains, and the manifest has no unresolved triage or repair item. The contact sheet is a review artifact; `delivery.images` are the primary production assets. `delivery.transparent_images` are optional production variants only after their independent quality gate passes; `alpha_images`, `transparent_candidates`, and masks are not approved deliverables.
8. Submit a visual verdict for every primary route, not only generated reconstruction. Use `pass` only after all primary success conditions pass. Review transparent candidates separately with `--transparent-verdict pass`, `retryable`, or `reject`; a missing or rejected optional transparent variant does not block a valid primary delivery. On `retryable`, name the failed condition, revise the candidate choice or plan, re-apply, and review again. Retry only when a concrete change addresses the failure; if the same failure repeats twice, stop with explicit failure evidence instead of looping indefinitely.
9. If status is `needs_user_decision`, finish semantic triage before proceeding. If status is `awaiting_user_approval`, run `ultrasplit repair prepare`; show deliverable, repair, and ignored counts, every clean repair preview plus original context, reason, target count, call count, and two-attempt limit, then wait for explicit approval.
10. After approval, record it with `ultrasplit repair approve`. Generate one regular grid per conflict group, ingest it, and return to the same delivery review gate. Never retry a repair group more than twice. Deliver the final status, counts, absolute output directory, review contact sheet, manifest, and title-free production asset paths.

Generated completion is inferred content. Always identify it as reconstruction, never extraction or factual recovery.

Read [references/repair-workflow.md](references/repair-workflow.md) only when repair is requested. Read [references/evaluation.md](references/evaluation.md) before deciding whether an output passes or should be retried.

## Commands

Use the Skill wrapper for the explicit model-guided workflow in a repository checkout:

```powershell
python .agents/skills/splitting-image-grids-by-content/scripts/ultrasplit.py scan input.png --output-dir output/asset-set/_work --mode auto
# Inspect scan.json and its previews, align ambiguous scope, then write output/asset-set/plan.json.
python .agents/skills/splitting-image-grids-by-content/scripts/ultrasplit.py apply input.png --scan output/asset-set/_work/scan.json --plan output/asset-set/plan.json --output-dir output/asset-set
python .agents/skills/splitting-image-grids-by-content/scripts/ultrasplit.py evaluate output/asset-set/manifest.json --visual-verdict pass --transparent-verdict pass
```

Use `ultrasplit` directly after `python -m pip install -e .`.

`ultrasplit run` is a deterministic smoke-test shortcut for unambiguous framed or simple-background inputs. It uses `auto_plan`, bypasses host-model inventory and scope alignment, and must not be the default Skill workflow or a final-delivery path without the same visual review gate.

## Boundaries

- Simple foreground masks are not semantic instance segmentation.
- The host model should identify text, captions, and watermarks during inventory and review, but semantic recognition alone cannot remove pixels or create missing candidate boundaries. If text and a subject share an inseparable region, rescan, clean through an available source-pixel route, or report the case as unsupported; do not pretend that recognizing the text removed it.
- Bright, reflective, translucent, white, or fine-haired subjects can be damaged by color-distance alpha extraction. Never promote an alpha candidate merely because it exists; inspect it on white, black, and checkerboard backgrounds and omit the transparent variant when the mask is unsafe.
- bbox overlap alone never authorizes generated reconstruction.
- Source clipping, occlusion, or shared semantic ownership requires repair or review.
- Edge contact alone does not prove that reconstruction is appropriate. The 0.65 visibility threshold is a repair eligibility floor, not a semantic score: the primary content must still be recognizable. Lower-visibility loss, missing identity anchors, and isolated fragments should default to `ignore`, not generation.
- Never call an image generator before showing the bounded request and receiving user approval.
- An unverified or exhausted result is not success.
