# Evaluator Pipeline

This diagram covers the two evaluator paths: deterministic checks for generated repair grids, and manifest review with the primary-review gate for layered PSD export.

```mermaid
flowchart TD
    subgraph A["Repair-grid checks: evaluate_grid"]
        A1["repair ingest receives generated grid"] --> A2["Check resolution, background, occupied-cell count, margins, edge contact, and duplicates"]
        A2 --> A3{"Checks pass?"}
        A3 -- "No" --> A4["Record failed attempt and issues; wait for retry or manual handling"]
        A3 -- "Yes" --> A5["Split repaired assets and update manifest and delivery"]
        A5 --> B1
    end

    subgraph B["Manifest review and PSD: evaluate_manifest"]
        B1["Load manifest and validate schema v3"] --> B2["Check semantic triage, conflict groups, repair attempts, and visual verdict"]
        B2 --> B3{"Any untriaged item?"}
        B3 -- "Yes" --> B4["needs_user_decision"]
        B3 -- "No" --> B31{"Pending conflict group without approval?"}
        B31 -- "Yes" --> B5["awaiting_user_approval"]
        B31 -- "No" --> B32{"Repair attempts exhausted?"}
        B32 -- "Yes" --> B6["retry_exhausted"]
        B32 -- "No" --> B33{"Visual verdict is identity_uncertain?"}
        B33 -- "Yes" --> B4
        B33 -- "No" --> B34{"Retryable, failed repair, or pending work?"}
        B34 -- "Yes" --> B7["needs_review"]
        B34 -- "No" --> B35{"Visual verdict is pass?"}
        B35 -- "Yes" --> B8["success"]
        B35 -- "No" --> B7
        B4 --> B9["Apply optional transparency verdict"]
        B5 --> B9
        B6 --> B9
        B7 --> B9
        B8 --> B9
        B9 --> B10{"Final status is success?"}
        B10 -- "No" --> B11["Do not export PSD; write review state"]
        B10 -- "Yes" --> B12["Export one or more PSD pages: layers.psd, layers-02.psd, …"]
        B12 --> B13["Record first path, all PSD paths, and export details in manifest"]
    end

    C["CLI: evaluate manifest.json"] --> B1
    A4 --> A1
```

`ultrasplit run` creates and routes the manifest; it does not itself pass the evaluation gate. The CLI `evaluate` command, or repair ingestion after a successful grid check, calls `evaluate_manifest` and can reach PSD export.
