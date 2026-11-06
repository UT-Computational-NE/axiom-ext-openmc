---
name: openmc.diff
description: "Compare two OpenMC statepoints. The tolerance is the root-sum-square of the reported standard deviations."
license: Apache-2.0
---

Read-only. Calls `axiom_ext_openmc.library.compare_statepoints`.

Inputs: `left` and `right`.

`delta` is the left reported value minus the right. This is not agreement with a published reference.
