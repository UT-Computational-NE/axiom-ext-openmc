# Third-party notices

This package is Apache-2.0 licensed. It incorporates work from the projects
below under their own terms, which are reproduced here as those licences
require.

---

## OpenMC Crash Course

**Author:** Harrison Reisinger, The University of Texas at Austin
**Source:** https://github.com/sarhon/OpenMC_Crash_Course
**Licence:** MIT

### What is used, and where

`src/axiom_ext_openmc/verification/builtin_cases.py` adapts two problems from
the course's `examples/` progression into verification cases:

| Rung | Adapted from |
|---|---|
| `pincell_uo2` | `examples/02_infinite_pincell` |
| `assembly_17x17` | `examples/04_assembly` |

The material compositions, pin dimensions (0.39 cm fuel radius, 0.45 cm
cladding radius, 1.26 cm pitch), the 17×17 lattice layout and its five
guide-tube positions are taken from that course. Only the packaging into this
package's `VerificationCase` shape is original here.

The course is a teaching progression that introduces these problems in order of
increasing difficulty. That ordering is precisely what a verification ladder
needs — each rung adding one source of difficulty so a failure localises — which
is why it was adopted rather than reinvented.

### Licence text

```
MIT License

Copyright (c) 2026 Harrison Reisinger and The University of Texas at Austin

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### Status

The upstream repository declares MIT in its packaging classifiers but did not
carry a `LICENSE` file at the time of adoption. Adding it is proposed in
[sarhon/OpenMC_Crash_Course#1](https://github.com/sarhon/OpenMC_Crash_Course/pull/1).
Update this section when that merges.
