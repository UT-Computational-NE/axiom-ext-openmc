---
name: openmc.stat
description: "Read k-eff, its standard deviation, and tally tables from an OpenMC statepoint."
license: Apache-2.0
---

Read-only. Calls `axiom_ext_openmc.library.read_statepoint`, the same reader the adapter uses when no `result.json` is present.

Input: `path`, a `statepoint.*.h5` file or a directory containing one.

k-eff is the `k_combined` dataset. Tally means and standard deviations are reduced from the stored sum and sum of squares. `h5py` is optional; without it the call says to install the `statepoint` extra.
