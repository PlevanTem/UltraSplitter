# UltraSplitter

[English](README.md) | [简体中文](README.zh-CN.md)

UltraSplitter turns panels, turnarounds, contact sheets, and simple-background object collages into individually accessible image assets. It combines multimodal judgment with deterministic pixel operations instead of assuming that every source is an evenly spaced grid.

> Status: v0.1.0 provides a working deterministic splitter and a provider-neutral contract for generated repair. It does not call an image-generation API by itself.

## Why

Uniform slicing fails when panels have uneven widths, captions sit outside frames, subjects are scattered, or rectangular detection boxes overlap. UltraSplitter separates three decisions:

1. **Source crop** — preserve the original pixels when the subject is already complete.
2. **Source composite** — isolate separable foreground pixels and place them on a clean canvas when boxes overlap but silhouettes do not.
3. **Generated reconstruction** — prepare an auditable repair packet when pixels are missing or subjects cannot be separated. An agent must obtain user approval before generation.

Before routing, multimodal triage removes noise, recommends ignoring severely incomplete fragments, and prevents unassessed edge contact from becoming an automatic generation request.

## Tested examples

These real inputs were run through the current workflow. Each case uses one result image: a delivery contact sheet for successful cases or a labeled triage sheet when approval is still required. All previews use the same 8:5 canvas. Click an input or result to open the full image.

| Case and verified result | Input | Result |
| --- | --- | --- |
| **Uneven layout**<br>`success` · 4 subjects<br>4 source crops, reordered by the multimodal plan; no generated pixels. | [<img src="docs/assets/case-uneven-input-preview.png" alt="Uneven character turnaround input" width="320">](docs/assets/case-uneven-input.png) | [<img src="docs/assets/case-uneven-output-preview.png" alt="Four extracted character views" width="320">](docs/assets/case-uneven-output.png) |
| **Dense asset sheet**<br>`success` after visual evaluation · 11 subjects<br>6 source crops + 5 source composites; one border-line false candidate was rejected by the plan. | [<img src="docs/assets/case-dense-input-preview.png" alt="Dense weapon asset sheet input" width="320">](docs/assets/case-dense-input.png) | [<img src="docs/assets/case-dense-output-preview.png" alt="Eleven extracted weapon assets" width="320">](docs/assets/case-dense-output.png) |
| **Edge-clipped collage**<br>`awaiting_user_approval`<br>2 deliverable · 1 repair candidate · 5 ignored fragments. The repair reference was mask-cleaned; no generation was executed. | [<img src="docs/assets/case-clipped-input-preview.png" alt="Edge-clipped subject collage input" width="320">](docs/assets/case-clipped-input.png) | [<img src="docs/assets/case-clipped-output-preview.png" alt="Labeled deliver, repair, and ignore triage sheet" width="320">](docs/assets/case-clipped-output.png) |

## Practical strengths

- **Content-aware, not grid-bound** — finds subject extents when positions, widths, scales, and spacing are uneven.
- **Useful on dense sheets** — combines source crops with foreground composites when rectangular boxes overlap but pixels remain separable.
- **Multimodal judgment at the right layer** — the host model can reject noise, group disconnected parts, name and order outputs, and assess semantic completeness without inventing pixel coordinates.
- **Safe handling of missing content** — repairable loss stops at an explicit approval gate, while severe or identity-ambiguous fragments are recommended for exclusion instead of consuming generation calls.
- **Source fidelity and traceability** — deterministic routes preserve original pixels; every output is linked to its route, source coordinates, evaluation, provenance, and absolute delivery path in `manifest.json`.
- **Agent-native integration** — the CLI and Skill contract work with Codex, Claude Code, and other multimodal coding agents without coupling the core package to one generation provider.

## Install and run

```bash
git clone https://github.com/PlevanTem/UltraSplitter.git
cd UltraSplitter
python -m pip install -e .
ultrasplit run input.png --name character-views
```

Explicit agent planning remains available:

```bash
ultrasplit scan input.png --output-dir work/scan
ultrasplit apply input.png --scan work/scan/scan.json --plan work/plan.json --output-dir output/task
ultrasplit inspect output/task/manifest.json
```

For a repair-required result:

```bash
ultrasplit repair prepare output/task/manifest.json
# The host agent shows the request to the user and waits for approval.
ultrasplit repair approve output/task/manifest.json --group conflict-001
# The host generates one grid from the repair packet, then returns it:
ultrasplit repair ingest output/task/manifest.json --group conflict-001 --grid generated-grid.png
ultrasplit evaluate output/task/manifest.json --visual-verdict pass
```

## Architecture

```text
image → deterministic scan → multimodal triage + plan → route
                    ├─ ignore severe fragments         ├─ source crop
                    ├─ request semantic decision       ├─ source composite
                    └─ classify repairable loss        └─ repair packet → user approval
                                                                            ↓
                                                              external image generation
                                                                            ↓
                                                         ingest → split → evaluate → exit
```

Every run writes a schema-v3 manifest with exact source coordinates, route evidence, provenance, approval state, bounded repair attempts, evaluation status, and absolute delivery paths. See [ARCHITECTURE.md](ARCHITECTURE.md).

## AI-native use

The repository includes a Codex-compatible skill under `skills/splitting-image-grids-by-content`. The same CLI contract can be called from Claude Code or other multimodal coding agents. Model providers remain outside the core package.

## Current boundary

- Supports framed panels and spatially separated objects on transparent or approximately uniform backgrounds.
- Does not perform complex semantic instance segmentation.
- Generated completion is reconstructed content, not recovered source truth.
- Dense, transparent, touching, or clipped cases return an explicit review or approval state instead of silent success.

## Roadmap

- Calibrate foreground-conflict thresholds on a larger licensed benchmark.
- Add provider adapters without coupling credentials to the core package.
- Add independent multimodal identity scoring and richer transparent-edge handling.
- Publish benchmark reports only after reproducible evaluation exists.

## License

MIT
