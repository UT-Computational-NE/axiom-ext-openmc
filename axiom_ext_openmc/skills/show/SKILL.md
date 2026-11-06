---
name: openmc.show
description: "Summarize an OpenMC model: cells, materials, surfaces, tallies, and the settings written in the deck."
license: Apache-2.0
---

Read-only. Calls `axiom_ext_openmc.library.summarize_model`.

Input: `input_dir`.

The summary lists what the XML contains. It does not invent materials or batch counts that are not written there.
