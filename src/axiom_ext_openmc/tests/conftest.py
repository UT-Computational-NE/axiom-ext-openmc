# Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""Shared test fixtures.

The repository-root ``conftest.py`` handles sys.path plumbing. This one holds
fixtures, so path resolution and test data stay separable.
"""

from __future__ import annotations

from typing import Any, Callable

import pytest

from axiom_ext_openmc.verification.availability import unavailable_reason

#: A converged statepoint with no lost particles. Keyword overrides let a test
#: change only the field it is about, which keeps the interesting value visible
#: instead of buried in a seven-key literal repeated down the file.
_STATEPOINT_DEFAULTS: dict[str, Any] = {
    "k_eff": 1.00342,
    "k_eff_std": 0.00012,
    "n_cycles": 50,
    "shannon_entropy": 6.13,
    "convergence": "stationary",
    "tallies": {},
    "lost_particles": 0,
}


@pytest.fixture
def statepoint() -> Callable[..., dict[str, Any]]:
    """Return a factory for parsed-statepoint dicts.

    Usage::

        parse.return_value = statepoint()                     # healthy run
        parse.return_value = statepoint(lost_particles=8432)  # faulted run
    """

    def _make(**overrides: Any) -> dict[str, Any]:
        return {**_STATEPOINT_DEFAULTS, **overrides}

    return _make


@pytest.fixture(scope="session")
def openmc_runnable() -> None:
    """Skip a test unless OpenMC and its cross-section data are both usable.

    The skip message names what is missing, so a run that verifies nothing says
    so rather than reporting a quiet pass.
    """
    reason = unavailable_reason()
    if reason:
        pytest.skip(reason)
