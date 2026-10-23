# Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""End-to-end: build every rung, run OpenMC for real, get numbers back.

Every other test in this package mocks the solver. This module does not — it is
the only place where the extension's claim to run OpenMC is actually exercised,
and therefore the only place a wrong answer can be detected rather than
asserted.

It is skipped unless OpenMC and its cross-section data are both present, with a
message naming what is missing. That is a deliberate trade: a suite that
silently substitutes a mock for the solver reports success while verifying
nothing, which is the same failure class as a reference value that is silently a
placeholder.

The assertions here are deliberately weak — plausibility, self-consistency and
reproducibility — because **this package has no verified reference values yet**.
Every entry in ``references`` is provisional. Producing real numbers is what
these runs are for; asserting against a number nobody has verified would be the
fabricated-agreement bug in a new costume.

Running it locally::

    conda install -c conda-forge openmc
    export OPENMC_CROSS_SECTIONS=/path/to/endfb-vii.1-hdf5/cross_sections.xml
    pytest -k verification_integration
"""

from __future__ import annotations

import pytest

from axiom_ext_openmc.verification import builtin_cases  # noqa: F401  (registers)
from axiom_ext_openmc.verification import cases, runner

pytestmark = pytest.mark.usefixtures("openmc_runnable")

#: Every rung, parametrized by name so a failure says which one broke.
LADDER = [pytest.param(case, id=case.name) for case in cases.default_registry().all()]


@pytest.fixture(scope="module")
def results():
    """Run each rung once and share the outcome across assertions.

    Rebuilding per assertion would multiply the suite's cost by the number of
    checks for no additional coverage.
    """
    return {}


def _result(case, results, tmp_path_factory):
    if case.name not in results:
        workdir = tmp_path_factory.mktemp(case.name)
        results[case.name] = runner.run_case(case, workdir)
    return results[case.name]


@pytest.mark.parametrize("case", LADDER)
def test_rung_runs_without_faulting(case, results, tmp_path_factory):
    result = _result(case, results, tmp_path_factory)
    assert result.fault is None, f"{case.name} faulted: {result.fault}"


@pytest.mark.parametrize("case", LADDER)
def test_rung_returns_a_plausible_multiplication_factor(
    case, results, tmp_path_factory
):
    """Weak on purpose: no reference for this case has been verified yet."""
    k_eff = _result(case, results, tmp_path_factory).value_summary["k_eff"]
    assert 0.5 < k_eff < 3.0, (
        f"{case.name} gave k = {k_eff}, outside any physically plausible range "
        "for a fuel-bearing system; the case or the data library is wrong"
    )


@pytest.mark.parametrize("case", LADDER)
def test_rung_reports_its_own_uncertainty(case, results, tmp_path_factory):
    """A multiplication factor without a standard deviation cannot be compared
    to a reference, which is the only reason to compute it here."""
    assert _result(case, results, tmp_path_factory).value_summary["k_eff_std"] > 0


@pytest.mark.parametrize("case", LADDER)
def test_rung_loses_no_particles(case, results, tmp_path_factory):
    """Lost particles mean the geometry has a hole. The adapter already faults
    on this; asserting per rung makes the case itself the thing under test."""
    fault = _result(case, results, tmp_path_factory).fault
    assert fault is None or fault.name != "lost_particles"


@pytest.mark.parametrize("case", LADDER)
def test_rung_is_reproducible(case, tmp_path_factory):
    """Verification is worthless if a rerun moves. The seed lives on the case."""
    first = runner.run_case(case, tmp_path_factory.mktemp(f"{case.name}_a"))
    second = runner.run_case(case, tmp_path_factory.mktemp(f"{case.name}_b"))

    assert first.value_summary["k_eff"] == pytest.approx(
        second.value_summary["k_eff"], rel=1e-12
    )


def test_moderated_lattices_thermalise_above_the_bare_medium(
    results, tmp_path_factory
):
    """The one cross-rung physics assertion the ladder can make without a
    reference: adding a moderator to enriched UO2 must raise the multiplication
    factor, because thermal fission cross sections dwarf fast ones. If the pin
    cell does not beat the bare medium, the moderator or its thermal scattering
    law is not doing anything.
    """
    registry = cases.default_registry()
    bare = _result(registry.get("infinite_medium_uo2"), results, tmp_path_factory)
    pincell = _result(registry.get("pincell_uo2"), results, tmp_path_factory)

    assert pincell.value_summary["k_eff"] > bare.value_summary["k_eff"], (
        "a moderated pin lattice did not out-multiply an unmoderated medium; "
        "check that c_H_in_H2O is being applied"
    )
