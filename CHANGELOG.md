# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Added a validated 0.65 visible-fraction repair floor plus an explicit `primary_content_recognizable` gate, preventing recognizable majority subjects from being silently ignored.
- Added structured multimodal triage for deliver, clean, repair, and ignore decisions, including missing severity, identity evidence, and exclusion reasons.
- Added separate delivery and triage contact sheets plus deliverable, repair, and ignored counts in CLI and manifest output.
- Added clean repair-reference montages while retaining the original dispute region as context.

### Changed

- Updated the edge-clipped real-world example after an approved three-subject reconstruction: the first generated grid failed safe-margin checks and the second passed deterministic and visual evaluation.
- Replaced the synthetic README example with a real tested four-panel input, its actual contact sheet, and individually accessible source-faithful outputs.
- Added a complete Simplified Chinese README with bidirectional language navigation.
- Reworked both README examples around three verified real-world cases with uniform previews and concise capability evidence.

### Fixed

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
