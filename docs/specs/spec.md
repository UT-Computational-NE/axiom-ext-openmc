# OpenMC extension — technical specification

## Standard this extension conforms to

The governing document is AEOS 0.1, `docs/specs/spec-aeos-0.1.md` in `b-tree-labs/axiom-os`, as amended on `main` through the 0.2 chain-readiness section (§4.11) and the manifest schema `aeos-manifest-0.1.json`. `axi ext lint` in `axiom-os-lm` 0.70.2 enforces that schema and those chain rules.

AEOS 1.0 (`spec-aeos-1.0.md`) is marked draft. Its own header says 0.1 governs and that §§8–19 are skeletal. This extension does not claim 1.0 conformance. `aeos_version = "0.2.0"` is the chain minor defined inside the 0.1 document, which is what a current `axi ext init` scaffold emits. `chain_level = "C"` is claimed because every skill declares `risk`, non-read skills declare `requires` with a `fix`, follow-ups resolve, and `grade-a-run` is a recipe whose steps are those skills.

## Layout

Compound layout. The package is `axiom_ext_openmc/` beside `axiom-extension.toml`, not under `src/`. `builtin = false`.

The manifest `name` is `axiom_ext_openmc` (schema pattern `^[a-z][a-z0-9_]*$`, and it is the import package). The PyPI / GitHub name keeps the hyphen. AEOS030 fails when lint is pointed at a directory literally named `axiom-ext-openmc`. Lint a directory whose name is `axiom_ext_openmc` (a copy or a correctly named checkout). That is a linter mismatch with PEP 503 distribution names, not a second manifest.

## Capabilities

| Kind | Name | Calls |
|---|---|---|
| adapter | integration `openmc` | `OpenMCKernelAdapter` |
| skill | `openmc.check_runner` | `library.runner_status` |
| skill | `openmc.list_cases` | `library.list_cases` |
| skill | `openmc.parse_summary` | `library.parse_summary` → adapter parser |
| skill | `openmc.run_input` | `library.run_input` → `OpenMCKernelAdapter.execute` |
| skill | `openmc.grade` | `library.grade` |
| recipe | `grade-a-run` | check, list, run, grade |

`connect` resolves a local runner and does not open an SSH session. Auth method is `none`. Declared capabilities are `execute`, `subprocess`, and `docker`. The ssh runner still raises `NotImplementedError`.

Kernel discovery for `axi model run --on local:openmc` stays on the `axiom.compute.adapters` entry point. AEOS validate checks `axiom.adapters`, keyed by `integration`.

## Grading rule

`library.grade` returns:

- `no_reference` when the URI is not declared. `agrees` is null.
- `provisional` when the spec is provisional. The placeholder value is omitted. `agrees` is null.
- `compared` otherwise. `agrees` is true when the absolute difference is at most the root-sum-square of the reference uncertainty and `k_eff_std` (the reference uncertainty alone when no standard deviation is passed). That is a magnitude check. The extension's uncertainty posture is `magnitude-only`.

## Uncertainty

Modelled k-eff values carry a scalar standard deviation and no covariance, so the posture is `magnitude-only`.

## What is not claimed

Silver requires a Sigstore signature. The manifest sets `signing.required = true` and `methods = ["sigstore"]`. The publish workflow uploads an unsigned wheel. Gold requires attestation and quarantine, which this local solver does not implement (`federation.shareable = false`).
