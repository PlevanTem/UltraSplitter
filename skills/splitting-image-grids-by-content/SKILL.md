---
name: splitting-image-grids-by-content
description: Split framed image grids and simple-background object collages into user-accessible assets, preserving source pixels when possible and preparing approval-gated repair grids when clipping, occlusion, or touching subjects require generated reconstruction.
---

# Split Images by Content

Use the host model for semantic judgment and UltraSplitter for exact source-pixel operations. Do not estimate final crop coordinates from a resized model view.

## Workflow

1. Infer `panels` for framed grids/turnarounds and `objects` for separated subjects on a simple background.
2. Run `ultrasplit scan`, inspect the numbered preview, and write a plan using exact region IDs.
3. Add `visual_assessment` only when the image visibly shows clipping, occlusion, touching subjects, or multiple subjects inside one connected component.
4. Run `ultrasplit apply`, then inspect the source and contact sheet.
5. Accept `source_crop` and `source_composite` only when the requested subjects are complete and unpolluted.
6. If status is `awaiting_user_approval`, run `ultrasplit repair prepare`, show the user every conflict-group preview, reason, target count, call count, and two-attempt limit, then wait for explicit approval.
7. After approval, record it with `ultrasplit repair approve`. Generate one regular grid per conflict group, not one image per subject, and ingest it.
8. Compare reconstructed subjects against visible identity anchors and submit `pass`, `retryable`, or `identity_uncertain`. Never retry a group more than twice.
9. Deliver the status, count, absolute output directory, contact sheet, manifest, and accessible image paths.

Generated completion is inferred content. Always identify it as reconstruction, never extraction or factual recovery.

Read [references/plan-schema.md](references/plan-schema.md) before authoring plans. Read [references/repair-workflow.md](references/repair-workflow.md) only when repair is requested. Read [references/evaluation.md](references/evaluation.md) when validating outputs or deciding whether to retry.

## Commands

Use the repository wrapper when the package is not installed:

```powershell
python skills/splitting-image-grids-by-content/scripts/ultrasplit.py run input.png --name asset-set
```

Use `ultrasplit` directly after `python -m pip install -e .`.

## Boundaries

- Simple foreground masks are not semantic instance segmentation.
- bbox overlap alone never authorizes generated reconstruction.
- Source clipping, occlusion, or shared semantic ownership requires repair or review.
- Never call an image generator before showing the bounded request and receiving user approval.
- An unverified or exhausted result is not success.
