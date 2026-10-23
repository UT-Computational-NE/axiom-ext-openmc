# OpenMC extension — technical specification

## Standard this extension conforms to

The governing document is AEOS 0.1.0, `docs/specs/spec-aeos-0.1.md` in `b-tree-labs/axiom-os`. Its header marks §4.11 (chain readiness) and §4.12 (recipe) as **0.2 draft amendments** carried in that file until 0.2 is ratified. The manifest schema remains `aeos-manifest-0.1.json`. `axi ext lint` in `axiom-os-lm` 0.70.2 enforces the schema and the draft chain rules.

AEOS 1.0 (`spec-aeos-1.0.md`) is marked draft. Its own header says 0.1 governs and that §§8–19 are skeletal. This extension does not claim 1.0 conformance.

`aeos_version = "0.1.0"`. `chain_level = "A"`. The draft rule AEOS101 says a claim of B or C requires `aeos_version >= "0.2"`. This package does not take that claim. The skills and `grade-a-run` still satisfy the draft's level C checks, and lint reports AEOS103 (achieved C, claimed A) with the fix "set chain_level = C and aeos_version >= 0.2". That fix is the conflict: following it would leave the governing version.

`extension.version`, `pyproject.toml` `version`, and `__version__` are `0.2.0`. That is this package's semver. It is not the AEOS spec version. A current `axi ext init` scaffold emits `aeos_version = "0.2.0"`; that scaffold follows the draft amendment, and this manifest does not.

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
| skill | `openmc.validate` | `library.validate_model` |
| skill | `openmc.show` | `library.summarize_model` |
| skill | `openmc.stat` | `library.read_statepoint` |
| skill | `openmc.diff` | `library.compare_statepoints` |
| skill | `openmc.check` | `library.check_cross_sections` |
| skill | `openmc.review` | `library.plan_run` |
| cmd | noun `openmc` | `axiom-openmc` verbs `validate`, `show`, `stat`, `diff`, `check`, `review`, same functions |
| recipe | `grade-a-run` | check, list, run, grade |

`openmc.validate`, `openmc.show`, `openmc.stat`, `openmc.diff`, `openmc.check`, and `openmc.review` declare `surfaces = ["cli", "mcp", "skill_md"]`. MCP tool names are the projector's derivation of those skill names. The `axiom.commands` entry point is `build_parser` for noun `openmc`.

Statepoint k-eff is the `k_combined` pair. `k_generation` is returned as stored and is not reduced into another k-eff. Tally mean is `sum / n_realizations`. The sample standard deviation uses OpenMC's sum and sum-of-squares formula. A single realization with a non-zero mean has a null standard deviation. Comparing two statepoints subtracts those reported values. `within_reported_uncertainty` is that magnitude check. It is not `grade`, and it is not agreement with a published reference.

`plan_run` sets `executed` to false. It does not call `execute`. Particle and batch counts in the plan are the ones in `settings.xml`. The adapter does not rewrite that file.

`connect` resolves a local runner and does not open an SSH session. Auth method is `none`. Declared capabilities are `execute`, `subprocess`, and `docker`. The ssh runner still raises `NotImplementedError`.

Kernel discovery for `axi model run --on local:openmc` stays on the `axiom.compute.adapters` entry point. AEOS validate checks `axiom.adapters`, keyed by `integration`, and `axiom.commands`, keyed by the cmd noun.

## Grading rule

`library.grade` returns:

- `no_reference` when the URI is not declared. `agrees` is null.
- `provisional` when the spec is provisional. The placeholder value is omitted. `agrees` is null.
- `compared` otherwise. `agrees` is true when the absolute difference is at most the root-sum-square of the reference uncertainty and `k_eff_std` (the reference uncertainty alone when no standard deviation is passed). That is a magnitude check. The extension's uncertainty posture is `magnitude-only`.

## Uncertainty

Modelled k-eff values carry a scalar standard deviation and no covariance, so the posture is `magnitude-only`.

## What is not claimed

Silver requires a Sigstore signature. The manifest sets `signing.required = true` and `methods = ["sigstore"]`. The publish workflow uploads an unsigned wheel. Gold requires attestation and quarantine, which this local solver does not implement (`federation.shareable = false`).
