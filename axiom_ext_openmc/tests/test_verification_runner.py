# Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""The runner builds a case's inputs and hands them to the adapter.

It deliberately owns no execution logic of its own. ``OpenMCKernelAdapter``
already selects a runner, invokes OpenMC, parses the statepoint and faults on
lost particles; duplicating any of that here would create a second code path
that drifts. The runner's whole job is: make the input directory, translate the
case's settings into the adapter's determinism state, delegate.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from axiom_ext_openmc.adapter import OpenMCKernelAdapter
from axiom_ext_openmc.verification import runner
from axiom_ext_openmc.verification.cases import VerificationCase


def _writing_case(**overrides) -> VerificationCase:
    """A case that writes the three files OpenMC requires."""

    def build(directory: Path, case: VerificationCase) -> None:
        for name in ("geometry.xml", "materials.xml", "settings.xml"):
            (directory / name).write_text("<xml/>", encoding="utf-8")

    defaults = dict(
        name="toy",
        description="writes minimal inputs",
        reference_uri="reference://test/toy/k-eff",
        build=build,
        n_particles=100,
        n_active_cycles=5,
        n_inactive_cycles=2,
    )
    defaults.update(overrides)
    return VerificationCase(**defaults)


def test_run_case_builds_inputs_then_delegates_to_the_adapter(
    tmp_path: Path, statepoint
):
    case = _writing_case()

    with patch.object(OpenMCKernelAdapter, "_run_openmc_subprocess") as run, patch.object(
        OpenMCKernelAdapter, "_parse_statepoint"
    ) as parse:
        run.return_value = (0, "", "")
        parse.return_value = statepoint()
        result = runner.run_case(case, tmp_path, kernel_options={"runner": "subprocess"})

    assert result.fault is None
    assert result.value_summary["k_eff"] == pytest.approx(1.00342)
    assert (tmp_path / "geometry.xml").exists()


def test_case_settings_reach_the_adapter(tmp_path: Path, statepoint):
    """Particle and cycle counts are the case's, not the adapter's defaults —
    a case that quietly ran with different statistics is not the case."""
    case = _writing_case(n_particles=4321, n_active_cycles=7, n_inactive_cycles=3)

    with patch.object(OpenMCKernelAdapter, "execute") as execute:
        execute.return_value = None
        runner.run_case(case, tmp_path)

    state = execute.call_args.args[0] if execute.call_args.args else execute.call_args.kwargs["determinism_state"]
    assert state["n_particles"] == 4321
    assert state["n_active_cycles"] == 7
    assert state["n_inactive_cycles"] == 3
    assert Path(state["input_dir"]) == tmp_path


def test_a_case_that_writes_nothing_fails_before_openmc_is_invoked(tmp_path: Path):
    """Otherwise the adapter reports a confusing OpenMC parse error for what is
    really a broken case builder."""
    case = _writing_case(build=lambda directory, case: None)

    with patch.object(OpenMCKernelAdapter, "execute") as execute:
        with pytest.raises(RuntimeError, match="wrote no OpenMC input files"):
            runner.run_case(case, tmp_path)

    execute.assert_not_called()


def test_the_working_directory_is_created_when_absent(tmp_path: Path, statepoint):
    workdir = tmp_path / "nested" / "run"
    case = _writing_case()

    with patch.object(OpenMCKernelAdapter, "_run_openmc_subprocess") as run, patch.object(
        OpenMCKernelAdapter, "_parse_statepoint"
    ) as parse:
        run.return_value = (0, "", "")
        parse.return_value = statepoint()
        runner.run_case(case, workdir, kernel_options={"runner": "subprocess"})

    assert workdir.is_dir()


def test_a_deterministic_seed_is_passed_through(tmp_path: Path, statepoint):
    """Verification runs must be reproducible; the seed is part of the case's
    identity, not a per-invocation accident."""
    case = _writing_case()

    with patch.object(OpenMCKernelAdapter, "execute") as execute:
        execute.return_value = None
        runner.run_case(case, tmp_path)

    state = execute.call_args.args[0] if execute.call_args.args else execute.call_args.kwargs["determinism_state"]
    assert state["rng_seed"] == case.rng_seed
