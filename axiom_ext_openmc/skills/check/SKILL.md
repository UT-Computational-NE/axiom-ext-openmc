---
name: openmc.check
description: "Check OPENMC_CROSS_SECTIONS, the data files it names, and a model's nuclide names."
license: Apache-2.0
---

Read-only. Calls `axiom_ext_openmc.library.check_cross_sections`.

Optional inputs: `path` (an index file) and `model_dir`. With neither, the environment variable is checked. Element names are listed and not matched to the index.
