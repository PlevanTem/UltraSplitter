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

## Evaluation criteria and evaluator index

Use the same three-part description for each category: **method → dimension → keywords**. The evaluator index links to the implementation; host visual review is not performed by Python and `evaluate_manifest()` only consumes its verdict.

| Method | Dimension | Keywords / criteria | Evaluator method (source index) |
|---|---|---|---|
| Deterministic grid check | Repair-grid integrity | Resolution (at least 512 px per cell); expected vs. occupied count; background consistency; edge contact; safe margin (at least 8%); possible duplicate shapes are reported for review. | [`evaluate_grid()`](../src/ultrasplitter/evaluator.py#L27) |
| Host multimodal visual review | Inventory and visual consistency | Reconcile the confirmed inventory with delivered assets (no missing or extra subjects); compare each asset with the source for identity, pose, silhouette, color, material, ornament, and no redesign. | Host review; [`evaluate_manifest()`](../src/ultrasplitter/evaluator.py#L115) consumes `visual_verdict` but does not inspect images. |
| Manifest gate | Workflow eligibility | Schema version 3; completed semantic triage; approved conflict groups; repair-attempt limit; required visual verdict is `pass`. | [`require_v3()`](../src/ultrasplitter/contracts.py#L48), [`evaluate_manifest()`](../src/ultrasplitter/evaluator.py#L115) |
| Transparent-variant check and review | Alpha integrity and compositing quality | Real alpha channel; transparent background; non-empty foreground; no edge contact; at least 8% safe margin; interior transparency is flagged for visual review; preview on white, black, and checkerboard. | [`inspect_transparent_candidate()`](../src/ultrasplitter/transparency.py#L60), [`apply_transparent_verdict()`](../src/ultrasplitter/transparency.py#L199); primary success is enforced by [`evaluate_manifest()`](../src/ultrasplitter/evaluator.py#L115). |
| PSD export | Delivery integrity | Native-pixel layers; pages stay within 30,000 px per side; oversized assets are tiled; paths and export details are recorded in the manifest. | [`export_layered_psd()`](../src/ultrasplitter/layered_psd.py#L119) |

Deterministic checks apply to generated repair grids; they do not certify semantic identity. Possible duplicate shapes are reported as evidence and still require review. The visual verdict comes from the host review, while the manifest gate controls whether that verdict and other workflow state permit delivery.

`ultrasplit run` creates and routes the manifest; it does not itself pass the evaluation gate. The CLI `evaluate` command, or repair ingestion after a successful grid check, calls `evaluate_manifest` and can reach PSD export.
