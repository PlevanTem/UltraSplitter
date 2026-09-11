# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Added a reproducible illustrated README motion banner that shows an AIGC sheet becoming reviewed, individual asset files, plus a static alternative and compact shortcut badges.
- Added a product roadmap and evaluation protocol focused on a packaged GUI, three user-facing measures, and a planned competitor baseline.
- Added owner-provided WeChat consulting details and direct Afdian / Buy Me a Coffee sponsorship links to both READMEs, without QR codes and with consulting separate from sponsorship.
- Added a reusable README showcase renderer with automatic card grids, normalized subject scale, and consistent preview canvases.
- Added a stylized SVG architecture overview for the bilingual READMEs.
- Added a validated 0.65 visible-fraction repair floor plus an explicit `primary_content_recognizable` gate, preventing recognizable majority subjects from being silently ignored.
- Added structured multimodal triage for deliver, clean, repair, and ignore decisions, including missing severity, identity evidence, and exclusion reasons.
- Added separate delivery and triage contact sheets plus deliverable, repair, and ignored counts in CLI and manifest output.
- Added clean repair-reference montages while retaining the original dispute region as context.

### Changed

- Promoted compact card contact sheets from a README-only renderer to the product delivery path, with near-square layouts, uniform canvases, longest-edge subject normalization, safe background trimming, and manifest layout metadata.
- Updated the edge-clipped real-world example after an approved three-subject reconstruction: the first generated grid failed safe-margin checks and the second passed deterministic and visual evaluation.
- Replaced the synthetic README example with a real tested four-panel input, its actual contact sheet, and individually accessible source-faithful outputs.
- Added a complete Simplified Chinese README with bidirectional language navigation.
- Reworked both README examples around three verified real-world cases with uniform previews and concise capability evidence.

### Fixed

- Made the Skill launcher discover either an installed package or a nearby repository checkout, so an independently installed Skill no longer assumes the repository source tree is adjacent.
- Cleared `delivery.pending_repair_images` after successful repair ingestion.
- Prevented unassessed edge contact from automatically authorizing generated repair; it now returns `needs_user_decision` with zero generation calls.
- Prevented pending repair candidates and severe ignored fragments from appearing in `delivery.images` or the final delivery contact sheet.
- Removed unrelated disconnected foreground from repair previews before an approval request is shown.

## [0.1.0] - 2026-09-11

### Added

- Content-aware scanning for framed panels and simple-background connected components.
- Agent-authored plans with exact candidate identifiers instead of model-guessed coordinates.
- Source crops, transparent outputs, masks, contact sheets, and absolute delivery paths.
- Three-route schema-v3 contract: source crop, source composite, and generated reconstruction.
- Conflict groups, isolated-repair batching, reference montages, user-approval recording, provider-neutral repair packets, grid ingestion, and two-attempt limits.
- Deterministic repair-grid checks and multimodal visual-verdict handoff.
- Codex Skill integration, reproducible synthetic fixtures, and Windows/Linux CI.

[Unreleased]: https://github.com/PlevanTem/UltraSplitter/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/PlevanTem/UltraSplitter/releases/tag/v0.1.0
