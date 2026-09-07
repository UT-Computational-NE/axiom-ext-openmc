# Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""End-to-end: build a case, run OpenMC for real, get a number back.

Every other test in this package mocks the solver. This module does not — it is
the only place where the extension's claim to run OpenMC is actually exercised,
and therefore the only place a wrong answer can be detected rather than
asserted.

It is skipped unless OpenMC and its cross-section data are both present, with a
message naming what is missing. That is a deliberate trade: a suite that
silently substitutes a mock for the solver reports success while verifying
nothing, which is the same failure class as a reference value that is silently a
placeholder.

Running it locally::

    conda install -c conda-forge openmc
    export OPENMC_CROSS_SECTIONS=/path/to/endfb-vii.1-hdf5/cross_sections.xml
    pytest -k verification_integration

The values these runs produce are what eventually replace the placeholder
reference values in ``axiom_ext_openmc.references`` — see AGENTS.md.
"""

from __future__ import annotations

import pytest

from axiom_ext_openmc.verification import cases, runner

pytestmark = pytest.mark.usefixtures("openmc_runnable")


@pytest.fixture(scope="module")
def infinite_medium():
    from axiom_ext_openmc.verification import builtin_cases  # noqa: F401

    return cases.default_registry().get("infinite_medium_uo2")


def test_infinite_medium_runs_and_returns_a_multiplication_factor(
    infinite_medium, tmp_path
):
    result = runner.run_case(infinite_medium, tmp_path)

    assert result.fault is None, f"OpenMC faulted: {result.fault}"
    k_eff = result.value_summary["k_eff"]
    assert 0.5 < k_eff < 3.0, (
        f"k-infinity of {k_eff} is outside any physically plausible range for a "
        "fuel-bearing infinite medium; the case or the data library is wrong"
    )


def test_the_run_reports_its_own_uncertainty(infinite_medium, tmp_path):
    """A multiplication factor without a standard deviation cannot be compared
    to a reference, which is the only reason to compute it here."""
    result = runner.run_case(infinite_medium, tmp_path)

    assert result.value_summary["k_eff_std"] > 0


def test_the_same_seed_reproduces_the_same_result(infinite_medium, tmp_path):
    """Verification is worthless if a rerun moves. The seed lives on the case."""
    first = runner.run_case(infinite_medium, tmp_path / "a")
    second = runner.run_case(infinite_medium, tmp_path / "b")

    assert first.value_summary["k_eff"] == pytest.approx(
        second.value_summary["k_eff"], rel=1e-12
    )


def test_no_particles_are_lost(infinite_medium, tmp_path):
    """Lost particles mean the geometry has a hole. The adapter already faults on
    this; asserting it here makes the case itself the thing under test."""
    result = runner.run_case(infinite_medium, tmp_path)

    assert result.fault is None or result.fault.name != "lost_particles"
