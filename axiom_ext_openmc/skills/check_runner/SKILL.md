---
name: openmc.check_runner
description: "Report whether this machine can run OpenMC, as separate facts for the Python package, nuclear data, the openmc binary, and Docker."
license: Apache-2.0
---

Read-only. Calls `axiom_ext_openmc.library.runner_status`. Does not start a solver.

No inputs.

The result's `value` has `python_package`, `cross_sections`, `openmc_binary`, `docker`, `can_run_openmc`, and `reason` (null when a real run is possible).
