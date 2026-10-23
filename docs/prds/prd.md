# OpenMC extension

## What this is

An Axiom extension that lets OpenMC participate in dispatch, and that gives an agent a small toolkit for running a prepared deck and grading the result.

## Toolkit and library

AEOS does not define capability kinds named "toolkit" or "library". In this extension those words mean:

- **Toolkit.** The `kind = "skill"` capabilities and the `axiom-openmc` command (`kind = "cmd"`, noun `openmc`). Per AEOS §4.9 a skill is the executable capability. MCP tools are the projector's view of a skill (`surfaces` includes `mcp`). The command verbs call the same library functions. This extension does not author a second input schema per surface.
- **Library.** `axiom_ext_openmc.library`, the public Python API those skills and verbs call. It validates a deck, summarizes it, reads statepoints, compares two of them, checks `OPENMC_CROSS_SECTIONS`, and plans a run without starting one, in addition to grading and running through the adapter. The skills and the command do not reimplement the adapter or the statepoint reader.

The extension does not author reactor geometry. A run consumes a directory that already contains OpenMC inputs.

## Grading

A reference that is still a placeholder is provisional. Grading it reports `provisional` and does not report agreement. A URI with no declared reference reports `no_reference`. Agreement is reported only after a reviewer clears `provisional` on a real published value.

## Out of scope

- Sigstore signing of a release. The manifest says signing is required. The publish workflow does not sign yet.
- Renaming the GitHub repository. The checkout directory is `axiom-ext-openmc`. The schema requires the manifest name `axiom_ext_openmc`. `axi ext lint` AEOS030 compares those strings byte-for-byte.
- AEOS 1.0 rights declarations. That document is a draft and says 0.1 still governs.
