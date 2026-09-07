# Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""Verification cases — the graduated ladder that onboards a physics code.

A case builds one physics code's input directory and declares the reference it
should be graded against. Running the ladder produces real numbers, and those
numbers are what eventually replace the placeholder values in
:mod:`axiom_ext_openmc.references`.

The ladder is ordered: it starts at a problem simple enough that a wrong answer
is obvious, and climbs. That ordering is the point, so ``all()`` preserves
registration order rather than sorting by name.

Registration follows the same declare-then-look-up idiom as the builder
registries in the model-construction libraries, so there is one pattern to learn
across the stack rather than three.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator

__all__ = ["VerificationCase", "CaseRegistry", "default_registry", "register"]

#: Signature of a case builder: write this code's inputs into ``directory``.
#: The case is passed too, so the statistics written into the solver's settings
#: are the ones the case declares rather than a second copy that can drift.
CaseBuilder = Callable[[Path, "VerificationCase"], None]

#: Fixed so a rerun reproduces a run exactly. Verification that moves between
#: invocations cannot be compared to a reference.
DEFAULT_RNG_SEED = 1


@dataclass(frozen=True)
class VerificationCase:
    """One runnable problem with a reference to be graded against."""

    name: str
    description: str
    reference_uri: str
    build: CaseBuilder
    n_particles: int
    n_active_cycles: int
    n_inactive_cycles: int
    rng_seed: int = DEFAULT_RNG_SEED

    def __post_init__(self) -> None:
        for attr in ("n_particles", "n_active_cycles", "n_inactive_cycles"):
            if getattr(self, attr) <= 0:
                raise ValueError(
                    f"{attr} must be positive; a case that transports no "
                    f"particles still reports a multiplication factor, and it "
                    f"means nothing"
                )
        if not self.reference_uri.startswith("reference://"):
            raise ValueError(
                f"reference_uri must be a reference:// URI, got "
                f"{self.reference_uri!r}"
            )

    @property
    def total_batches(self) -> int:
        """What the solver calls ``batches`` — inactive plus active."""
        return self.n_inactive_cycles + self.n_active_cycles


class CaseRegistry:
    """Ordered, name-unique collection of verification cases."""

    def __init__(self) -> None:
        self._cases: dict[str, VerificationCase] = {}

    def register(self, case: VerificationCase) -> VerificationCase:
        """Add ``case``; refuse a duplicate name.

        Two cases under one name means one of them silently never runs, which is
        the class of quiet failure this whole module exists to avoid.
        """
        if case.name in self._cases:
            raise ValueError(
                f"a verification case named {case.name!r} is already registered"
            )
        self._cases[case.name] = case
        return case

    def get(self, name: str) -> VerificationCase:
        """Look up a case, naming what does exist when it is missing."""
        try:
            return self._cases[name]
        except KeyError:
            known = ", ".join(self._cases) or "(none registered)"
            raise KeyError(
                f"no verification case named {name!r}; registered cases: {known}"
            ) from None

    def all(self) -> list[VerificationCase]:
        """Every case, in registration order — simplest rung first."""
        return list(self._cases.values())

    def __len__(self) -> int:
        return len(self._cases)

    def __iter__(self) -> Iterator[VerificationCase]:
        return iter(self._cases.values())


_DEFAULT = CaseRegistry()


def default_registry() -> CaseRegistry:
    """The registry the shipped ladder registers into."""
    return _DEFAULT


def register(case: VerificationCase) -> VerificationCase:
    """Register ``case`` into the default registry."""
    return _DEFAULT.register(case)
