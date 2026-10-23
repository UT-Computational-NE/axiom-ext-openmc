---
name: openmc.parse_summary
description: "Read the canonical value summary from an OpenMC output directory using the adapter's parser."
license: Apache-2.0
---

Read-only. Calls `axiom_ext_openmc.library.parse_summary`, which calls `OpenMCKernelAdapter._parse_statepoint`. There is no second parser.

Input: `input_dir`, the directory OpenMC wrote.

A `result.json` in that directory is read. Without one, `statepoint.*.h5` is read by `axiom_ext_openmc.statepoint`, the same reader `openmc.stat` uses. There is still one parser.
