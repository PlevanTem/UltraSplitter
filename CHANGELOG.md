# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Replaced the synthetic README example with a real tested four-panel input, its actual contact sheet, and individually accessible source-faithful outputs.
- Added a complete Simplified Chinese README with bidirectional language navigation.

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
