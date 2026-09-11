# Generated repair workflow

Use repair only when source pixels are missing or cannot be separated without damage.

```powershell
ultrasplit repair prepare output/task/manifest.json
ultrasplit repair approve output/task/manifest.json --group conflict-001
ultrasplit repair ingest output/task/manifest.json --group conflict-001 --grid generated.png
ultrasplit evaluate output/task/manifest.json --visual-verdict pass
```

Before approval, show the user one concise decision summary: deliverable count, repair candidate count, recommended ignored count, clean source montage, original `context.png`, target map, target order, reasons, number of groups/calls, and maximum of two attempts per group.

Do not prepare repair while the manifest is `needs_user_decision`; first classify every clipped or ambiguous target. Severe fragments and candidates without enough identity evidence belong in structured exclusions and do not consume generation calls.

For each group, pass its clean `source.png`, original `context.png`, and `target-map.png` to the available image-generation tool with the exact generated `prompt.txt`. Produce all group subjects in one evenly spaced grid. Do not generate one subject at a time unless the prepared group contains only one subject.

Approval covers only the listed groups and retry budget. New targets or expanded scope require a new user decision. The CLI rejects unapproved ingestion and retains every attempt for audit.
