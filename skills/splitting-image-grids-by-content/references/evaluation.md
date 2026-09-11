# Evaluation policy

Deterministic checks and visual comparison serve different purposes.

The CLI checks expected occupied cells, cell resolution, uniform background, edge contact, safe margin, and obvious duplicates. The host model must still compare source-visible identity anchors:

- category and count;
- pose, orientation, and silhouette;
- colors, materials, ornaments, and design language;
- missing, duplicated, merged, or added parts;
- unrelated subjects, labels, borders, and watermarks.

Evaluate only `delivery.images` as finished assets. `pending_repair_images`, `ignored_images`, and the triage sheet are review evidence. A visual `pass` cannot override an unresolved `needs_semantic_triage` item.

Return:

- `pass` only when deterministic checks and visible identity anchors pass;
- `retryable` for a prompt-correctable layout or detail failure;
- `identity_uncertain` when the source cannot support a reliable judgment.

After one failed generation, revise the prompt from the concrete failure. After two attempts, stop with `retry_exhausted` and deliver the best artifacts plus failure evidence.
