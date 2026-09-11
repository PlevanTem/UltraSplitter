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
  "exclude_regions": ["cc-009"],
  "exclusions": [
    {
      "id": "excluded-001",
      "label": "edge-fragment",
      "regions": ["cc-009"],
      "missing_severity": "severe",
      "visible_fraction_estimate": 0.1,
      "critical_parts_missing": ["identity"],
      "identity_confidence": "low",
      "recommended_action": "ignore",
      "reason": ["isolated_fragment", "insufficient_identity_evidence"]
    }
  ],
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
        "missing_severity": "none",
        "visible_fraction_estimate": 1.0,
        "critical_parts_missing": [],
        "identity_confidence": "high",
        "recommended_action": "deliver"
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
- `visual_assessment` is required for clipped, contaminated, touching, or ambiguous candidates. `recommended_action` is `deliver`, `clean`, or `repair`; `missing_severity` is `none`, `minor`, or `repairable` for retained items.
- `visible_fraction_estimate` is advisory. Do not use area alone: missing identity-defining structure can make an otherwise large fragment unsuitable for reconstruction.
- Severely incomplete or identity-ambiguous candidates must not appear in `items`. Put their region IDs in `exclude_regions` and describe them in `exclusions` with `recommended_action: ignore` and `missing_severity: severe`.
- Use `allow_shared_regions_for_repair: true` only when multiple semantic subjects genuinely occupy the same connected component. Every item sharing that region must be marked for generated repair.
- Regions may otherwise appear in only one item. Explicit noise, captions, or dividers belong in `exclude_regions`.
