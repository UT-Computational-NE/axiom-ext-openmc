# axiom-ext-openmc — contributor and agent guide

Read this before changing anything here. It is written for both humans and
coding agents; `CLAUDE.md` is a symlink to it so Claude Code picks it up.

`README.md` explains what this package is *for*. This file explains how to work
in it without reintroducing the two failure modes it has already had.

---

## The one-paragraph version

This package wraps OpenMC as an Axiom extension. `adapter.py` runs a directory
that already contains OpenMC inputs. `verification/` builds those directories
from declared cases, so the package can prove it runs real physics rather than
asserting it against mocks. `references/` holds published values a run can be
graded against. Nothing here authors reactor geometry — that belongs to the
model-construction libraries upstream.

---

## Two failure modes this repo has already had

Both were silent, both passed CI, and both are now guarded by tests. Do not
recreate them.

### 1. Green results computed against values nobody published

`references/` seeds placeholder values so consumers can wire against canonical
URIs before reviewers extract the real numbers from a source document. Those
placeholders were installed silently, so verification axis A3 — *does the
computed value agree with the published reference?* — reported agreement against
`value=1.00203, # placeholder`.

**The rule:** every `ReferenceSpec` carries `provisional`. `install_specs`
refuses provisional specs unless the caller passes `include_provisional=True`,
and logs every skipped URI.

- Set `include_provisional=True` **only** in tests that assert on wiring.
- Never set it on a path that reports agreement to a user.
- When a reviewer extracts a real value, clear the flag in the same commit that
  changes the number.

A case with no reference must report *no reference*. It must never report
agreement.

### 2. Code written against an API that did not exist

A downstream bridge consumed `coreforge.materials.list_all()`. `coreforge.materials`
is a module and has no such attribute, so the call returned an empty list
through a default lambda, raised nothing, and logged nothing. Its tests passed
because they mocked the imagined shape.

**The rule:** if an interface you need does not exist yet, **say so at runtime**
and return nothing. Do not guess at a second shape, and do not write a test that
mocks an API you have not read. Read the dependency's source and cite what you
found.

---

## The verification ladder

`verification/` is the only place real OpenMC runs. Everything else mocks the
solver, which means everything else can be wrong without anyone noticing.

```
verification/
  availability.py   can this machine run OpenMC, and if not, which half is missing?
  cases.py          VerificationCase + the ordered registry
  builtin_cases.py  the shipped ladder; importing it registers the cases
  runner.py         build a case, delegate to the adapter. no execution logic.
```

The ladder is **ordered, simplest first**, and each rung adds exactly one source
of difficulty so a failure localises:

| Rung | Adds | A failure here means |
|---|---|---|
| `infinite_medium_uo2` | nothing — one material | materials or nuclear data |
| `pincell_uo2` | radial heterogeneity | geometry or boundary conditions |
| `assembly_17x17` | lattice + guide tubes | lattice construction, not pin physics |

`CaseRegistry.all()` preserves registration order because that order is the
argument.

Rungs 2 and 3 are adapted from the OpenMC Crash Course by Harrison Reisinger,
MIT licensed — see `THIRD_PARTY_NOTICES.md`. His course teaches these problems
in order of increasing difficulty, which is exactly the property a verification
ladder needs, so it was adopted rather than reinvented.

### Running it for real

```bash
conda install -c conda-forge openmc
# data library from https://openmc.org/data/
export OPENMC_CROSS_SECTIONS=/path/to/endfb-vii.1-hdf5/cross_sections.xml
pytest -k verification_integration
```

Without those, the integration tests skip with a message naming exactly what is
missing. A skipped verification suite is honest; a mocked one is not.

### Adding a rung

1. Write the builder. It takes `(directory, case)` and writes OpenMC inputs into
   `directory`. It receives the case so the statistics it writes into
   `settings.xml` are the ones the case declares — never a second copy.
2. **Import `openmc` lazily, inside the function.** Importing
   `verification` must not require OpenMC, so the ladder stays inspectable on a
   machine that cannot run it.
3. Register a `VerificationCase` with a `reference://` URI, a description saying
   what this rung isolates, and particle and cycle counts that converge in
   seconds.
4. The generic assertions in `test_verification_integration.py` — runs, plausible,
   reports uncertainty, loses no particles, reproducible — are parametrized over
   the registry and pick up a new rung automatically. Add a rung-specific test
   only for a physical relationship you can defend without a reference, the way
   `test_moderated_lattices_thermalise_above_the_bare_medium` does.

**Assert weakly until references are real.** Every reference in this package is
provisional, so integration tests check plausibility, self-consistency and
reproducibility — never equality with an unverified number. Asserting against a
value nobody has checked is the fabricated-agreement bug in a new costume.

Never write inputs beside your source file. The runner owns the directory so
concurrent runs cannot collide.

---

## Onboarding a different physics code

This is the template. A code is onboarded when it has all four, and not before:

| | Piece | Where it lives |
|---|---|---|
| 1 | **An adapter** that runs an input directory and returns a canonical `value_summary` | `<code>/adapter.py` |
| 2 | **A graduated case ladder** whose builders emit that code's input directory | `<code>/verification/builtin_cases.py` |
| 3 | **References** for each rung, provisional until a reviewer extracts real values | `<code>/references/` |
| 4 | **An integration suite** that runs the ladder and skips with a reason | `<code>/tests/` |

The ladder is what makes "add a code" gradeable rather than reviewable: running
it produces real numbers, and **those numbers are what clear the provisional
flags on the references**. Today every reference here is provisional precisely
because nobody has run the ladder yet. That is the loop to close, in that order.

The same four pieces work for a systems thermal-hydraulics code, but its case
*vocabulary* will not be geometry — loops, junctions and heat structures rather
than pin cells. Share the pattern, not the nouns.

---

## Conventions

**Tests first.** Write the failing test, watch it fail for the reason you
expect, then implement. If implementing reveals the test drove out a bad shape,
change the test and say so in the commit — that is the design working, not a
process violation.

**A test that encodes a bug is worse than no test.** Several tests here asserted
the broken behaviour. When you fix a defect, expect to update the tests that
protected it, and say which and why.

**Failing decisions are `xfail(strict=True)`, not red trunk.** A known defect
that needs a human decision gets an xfail with the decision in the reason
string. The trunk stays green, and the marker fails as XPASS the moment someone
fixes it, so it cannot be quietly left behind.

**Do not duplicate the adapter.** `runner.py` builds inputs and delegates.
Runner selection, invocation, statepoint parsing and lost-particle faulting live
in `adapter.py` and must have exactly one implementation, or verification
verifies a path production does not take.

**Shared fixtures live in `tests/conftest.py`.** The repository-root
`conftest.py` is sys.path plumbing only. Use the `statepoint(**overrides)`
factory rather than restating a seven-key dict — a test should show the one field
it is about.

**Vendored teaching material keeps its attribution.** Adapted work is credited
in the module docstring, in the function that uses it, and in
`THIRD_PARTY_NOTICES.md` with the upstream licence text and a table saying which
rung came from which source file. Adapt into our shapes; do not copy files
wholesale, and never drop the author's name.

**Every module docstring says why, not what.** The what is readable from the
code. Explain the failure the module prevents.

---

## Commands

```bash
pytest src/axiom_ext_openmc/tests/ -q        # full suite (integration skips without OpenMC)
pytest -k verification -q                     # ladder only
pytest -rs                                    # show skip reasons
ruff check src/                               # lint
```

---

_Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs. Apache-2.0 licensed._
