# Evaluation policy

Deterministic checks and visual comparison serve different purposes. Every delivery route passes through this review gate; source crops and composites are not exempt.

The CLI checks expected occupied cells, cell resolution, uniform background, edge contact, safe margin, and obvious duplicates. The host model must still compare source-visible identity anchors:

- category and count;
- pose, orientation, and silhouette;
- colors, materials, ornaments, and design language;
- missing, duplicated, merged, or added parts;
- unrelated subjects, labels, borders, and watermarks.

Evaluate `delivery.images` as the primary finished production assets. Their pixels must not contain preview titles, card chrome, status labels, or other presentation markup. `review/contact-sheet.png` is the named, automatically arranged delivery preview; `pending_repair_images`, `ignored_images`, and the triage sheet are diagnostic evidence. A visual `pass` cannot override an unresolved `needs_semantic_triage` item.

Transparent output is an optional, independently reviewed variant:

- `alpha_images` and `transparent_candidates` are candidate paths for compatibility and review, not finished assets;
- `transparent_images` contains only candidates whose primary assets passed first and that then passed automatic checks plus an explicit visual transparent verdict;
- the runtime may standardize candidate margin by adding transparent-only canvas pixels; it must not resample or regenerate the subject while doing so;
- inspect `transparent_review_sheets.white`, `.black`, and `.checkerboard` for holes, halos, erased light materials, damaged hair, foreign pixels, edge contact, and insufficient margin;
- `retryable` or `reject` removes every transparent candidate from `transparent_images` without invalidating a primary delivery that already passed;
- masks remain diagnostic artifacts and are never promoted automatically.

Before the primary `pass`, compare the confirmed asset inventory with the contact sheet and then open every primary delivery image at useful resolution. Require exact intended count and order, correct identity and view, semantic completeness, no unintended text, caption, watermark, border, duplicate, merged subject, foreign foreground, or missing part, and no unresolved manifest state. Approve transparent variants only after the separate three-background review.

On failure, record the concrete failed condition. Revise the candidate set or semantic plan and re-apply when the source pixels can satisfy it; use approval-gated repair only when source pixels are genuinely missing. Repeat review after every revision. Retry only while the next attempt changes a named cause. If the same cause fails twice, stop with explicit evidence instead of reporting success.

Return for every route:

- `pass` only when deterministic checks and visible identity anchors pass;
- `retryable` for a prompt-correctable layout or detail failure;
- `identity_uncertain` when the source cannot support a reliable judgment.

After one failed generation, revise the prompt from the concrete failure. After two attempts, stop with `retry_exhausted` and deliver the best artifacts plus failure evidence.
