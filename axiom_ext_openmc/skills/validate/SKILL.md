---
name: openmc.validate
description: "Check an OpenMC input directory's materials, geometry, settings, and tallies before a run."
license: Apache-2.0
---

Read-only. Calls `axiom_ext_openmc.library.validate_model`. Does not start a solve and does not report a k-eff.

Input: `input_dir`. Optional `use_openmc` asks the OpenMC package to parse the same directory; if that package is missing the result says so.
