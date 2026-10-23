---
name: openmc.run_input
description: "Run one existing OpenMC input directory through the production adapter. Does not author geometry."
license: Apache-2.0
---

Writes solver output into `input_dir` (statepoint, and `result.json` when the container runner is used). Calls `axiom_ext_openmc.library.run_input`, which calls `OpenMCKernelAdapter.execute`.

Inputs: `input_dir`, `n_particles`, `n_active_cycles`, `n_inactive_cycles`, `rng_seed`. Optional: `kernel_options`, `xs_library`.

Copy the counts from the verification case (`openmc.list_cases`). This skill has no hidden particle default.

On success, `value.k_eff` is the multiplication factor to pass to `openmc.grade`. A fault returns `ok=false` and still includes `value` when the adapter produced a partial summary.
