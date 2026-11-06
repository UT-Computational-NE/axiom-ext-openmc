---
name: openmc.review
description: "Dry-run plan for an OpenMC directory. Does not start a solve."
license: Apache-2.0
---

Read-only. Calls `axiom_ext_openmc.library.plan_run`.

Input: `input_dir`. Optional `runner` is passed to `connect` and does not start OpenMC.

`value.executed` is false. Particle and batch counts in the plan are the ones in `settings.xml`. The adapter does not rewrite that file.
