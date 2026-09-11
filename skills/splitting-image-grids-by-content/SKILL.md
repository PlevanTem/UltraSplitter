---
name: splitting-image-grids-by-content
description: Split framed image grids and simple-background object collages into user-accessible assets, preserving source pixels when possible and preparing approval-gated repair grids when clipping, occlusion, or touching subjects require generated reconstruction.
---

# Split Images by Content

Use the host model for semantic judgment and UltraSplitter for exact source-pixel operations. Do not estimate final crop coordinates from a resized model view.

## Runtime

Prefer an existing `ultrasplit` command. In an UltraSplitter checkout, use `scripts/ultrasplit.py`. If this Skill was installed independently and the runtime is missing, install it into the active Python environment with `python -m pip install git+https://github.com/PlevanTem/UltraSplitter.git`, using the host's normal permission flow for package installation, then continue the requested split. Do not replace an existing installed version silently.

## Workflow

1. Infer `panels` for framed grids/turnarounds and `objects` for separated subjects on a simple background.
2. Run `ultrasplit scan`, inspect the numbered preview, and write a plan using exact region IDs.
3. For every clipped, contaminated, touching, or ambiguous candidate, add `visual_assessment` and choose `deliver`, `clean`, or `repair`. A clipped subject with `visible_fraction_estimate >= 0.65`, recognizable primary content, and identity confidence above `low` must be offered for repair instead of silently ignored. Put lower-visibility fragments or identity-ambiguous remnants in `exclude_regions` plus structured `exclusions` with `recommended_action: ignore`.
4. Run `ultrasplit apply`, then inspect the source and `review/triage-sheet.png`.
5. Treat only `delivery.images` and `review/contact-sheet.png` as deliverable. Repair and ignored previews are diagnostic evidence.
6. Accept `source_crop` and `source_composite` only when the requested subjects are complete and unpolluted. If status is `needs_user_decision`, finish semantic triage before preparing repair.
7. If status is `awaiting_user_approval`, run `ultrasplit repair prepare`; show deliverable, repair, and ignored counts, every clean repair preview plus original context, reason, target count, call count, and two-attempt limit, then wait for explicit approval.
8. After approval, record it with `ultrasplit repair approve`. Generate one regular grid per conflict group, not one image per subject, and ingest it.
9. Compare reconstructed subjects against visible identity anchors and submit `pass`, `retryable`, or `identity_uncertain`. Never retry a group more than twice.
10. Deliver the status, deliverable/repair/ignored counts, absolute output directory, compact contact sheet, manifest, and accessible image paths. The contact sheet is a presentation artifact: it uses a near-square card grid, a uniform background, and longest-edge subject normalization, while the individual delivered files remain unchanged.

Generated completion is inferred content. Always identify it as reconstruction, never extraction or factual recovery.

Read [references/plan-schema.md](references/plan-schema.md) before authoring plans. Read [references/repair-workflow.md](references/repair-workflow.md) only when repair is requested. Read [references/evaluation.md](references/evaluation.md) when validating outputs or deciding whether to retry.

## Commands

Use the Skill wrapper when the package is installed or a repository checkout is available:

```powershell
python skills/splitting-image-grids-by-content/scripts/ultrasplit.py run input.png --name asset-set
```

Use `ultrasplit` directly after `python -m pip install -e .`.

## Boundaries

- Simple foreground masks are not semantic instance segmentation.
- bbox overlap alone never authorizes generated reconstruction.
- Source clipping, occlusion, or shared semantic ownership requires repair or review.
- Edge contact alone does not prove that reconstruction is appropriate. The 0.65 visibility threshold is a repair eligibility floor, not a semantic score: the primary content must still be recognizable. Lower-visibility loss, missing identity anchors, and isolated fragments should default to `ignore`, not generation.
- Never call an image generator before showing the bounded request and receiving user approval.
- An unverified or exhausted result is not success.
