# Agent plan schema v3

Plans select exact scan candidate IDs and may attach visible semantic evidence:

```json
{
  "schema_version": 3,
  "mode": "objects",
  "candidate_set": "objects-components-001",
  "expected_count": 2,
  "padding": 0.03,
  "emit": "auto",
  "items": [
    {
      "id": "item-001",
      "label": "front",
      "regions": ["cc-003"],
      "visual_assessment": {
        "complete": true,
        "occluded": false,
        "touching": false,
        "semantic_subject_count": 1,
        "confidence": "high"
      }
    }
  ]
}
```

- `mode` must match the candidate kind.
- `candidate_set` and `regions` must use exact IDs from `scan.json`.
- `expected_count` equals `items.length`.
- `padding` defaults to `0` for panels and `0.03` for objects.
- `emit` is `auto`, `crop`, `rgba`, or `all`.
- `visual_assessment` records host-model evidence; omit it when there is no visible issue.
- Use `allow_shared_regions_for_repair: true` only when multiple semantic subjects genuinely occupy the same connected component. Every item sharing that region must be marked for generated repair.
- Regions may otherwise appear in only one item. Explicit noise, captions, or dividers belong in `exclude_regions`.
