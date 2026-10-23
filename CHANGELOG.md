# Changelog

All notable changes to this extension are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this extension adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Library operations, shared by `axiom-openmc` and the skills `openmc.validate`, `openmc.show`, `openmc.stat`, `openmc.diff`, `openmc.check`, and `openmc.review`: validate materials, geometry, settings, and tallies; summarize a model; read a statepoint's k-eff and tally tables; compare two statepoints; check `OPENMC_CROSS_SECTIONS`; dry-run a directory without starting OpenMC.
- Optional `statepoint` extra (`h5py`). Without it, statepoint reading raises ImportError and names the extra. Tests use HDF5 fixtures, not a solver.

### Changed

- Host-side `statepoint.*.h5` reading goes through `axiom_ext_openmc.statepoint`. The adapter calls that reader when `result.json` is absent. A non-HDF5 file is an error, not `NotImplementedError`.
- README states what the extension is, and diagrams the package, the Axiom runtime, and AEOS.

## [0.2.0] - 2026-10-23

### Added

- A public library, `axiom_ext_openmc.library`, for runner status, the verification ladder, summary parsing, running one prepared input directory, and grading a k-eff.
- A toolkit of skills (`openmc.check_runner`, `openmc.list_cases`, `openmc.parse_summary`, `openmc.run_input`, `openmc.grade`) that call that library, plus the `grade-a-run` recipe.
- AEOS manifest at the repository root, compound layout, and `tests/unit_tests/test_standard.py` inheriting `axiom_tests`.

### Changed

- The extension is a standalone distribution (`builtin = false`). It declares `aeos_version = "0.1.0"` and chain level A. AEOS 0.2 chain-readiness is a draft amendment: the shipped recipe would score chain level C, and claiming C requires `aeos_version >= "0.2"` (AEOS101). Lint records AEOS103. AEOS 1.0 is a draft and is not claimed. Package version 0.2.0 is this extension's semver, not the AEOS spec version.
- Grading a provisional reference reports `provisional` and does not report agreement. A missing reference reports `no_reference`.

### Fixed

- The adapter manifest block uses the schema's `integration` field and exposes `connect`. The previous `name` field and `[extension.distribution]` table were not in the AEOS schema.

## [0.1.0] - 2026-09-07

### Added

- Initial standalone extraction: OpenMC `CodeAdapter`, provisional reference seeds, and the verification ladder.
