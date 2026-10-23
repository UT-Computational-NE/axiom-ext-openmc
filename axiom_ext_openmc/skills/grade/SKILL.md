---
name: openmc.grade
description: "Compare a computed k-eff to a declared reference. A provisional reference is not compared and does not report agreement."
license: Apache-2.0
---

Read-only. Calls `axiom_ext_openmc.library.grade`.

Inputs: `reference_uri` (`reference://...`), `k_eff`, and optional `k_eff_std`.

`value.status` is `no_reference`, `provisional`, or `compared`. `value.agrees` is a boolean only when the status is `compared`. A provisional spec's placeholder number is not included in the result.
