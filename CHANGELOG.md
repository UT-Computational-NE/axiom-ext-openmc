# Changelog

All notable changes to this extension are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this extension adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- README states what the extension is, and diagrams the package, the Axiom runtime, and AEOS.

## [0.2.0] - 2026-10-23

### Added

- A public library, `axiom_ext_openmc.library`, for runner status, the verification ladder, summary parsing, running one prepared input directory, and grading a k-eff.
- A toolkit of skills (`openmc.check_runner`, `openmc.list_cases`, `openmc.parse_summary`, `openmc.run_input`, `openmc.grade`) that call that library, plus the `grade-a-run` recipe.
- AEOS manifest at the repository root, compound layout, and `tests/unit_tests/test_standard.py` inheriting `axiom_tests`.

### Changed

- The extension is a standalone distribution (`builtin = false`). It declares `aeos_version = "0.2.0"` and chain level C, which is the additive chain-readiness minor inside the governing AEOS 0.1 document. AEOS 1.0 is a draft and is not claimed.
- Grading a provisional reference reports `provisional` and does not report agreement. A missing reference reports `no_reference`.

### Fixed

- The adapter manifest block uses the schema's `integration` field and exposes `connect`. The previous `name` field and `[extension.distribution]` table were not in the AEOS schema.

## [0.1.0] - 2026-09-07

### Added

- Initial standalone extraction: OpenMC `CodeAdapter`, provisional reference seeds, and the verification ladder.
