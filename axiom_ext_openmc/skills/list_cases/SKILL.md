---
name: openmc.list_cases
description: "List the verification ladder in registration order, with each case's reference URI and the particle and cycle counts that case declares."
license: Apache-2.0
---

Read-only. Calls `axiom_ext_openmc.library.list_cases`. Does not build inputs and does not import OpenMC.

No inputs.

The result's `value.cases` is the ladder. Copy a case's `reference_uri` and counts into `openmc.run_input` and `openmc.grade`. Do not choose a second set of statistics.
