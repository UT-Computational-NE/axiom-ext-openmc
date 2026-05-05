# Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""OpenMC extension — adapter contract + runner selection tests.

Per ADR-018 + Twin OS Build March Phase 2.

Tests cover:
- Adapter contract (re-asserted from Phase 2a inline tests; now inside the extension)
- Runner selection logic (subprocess vs docker vs ssh)
- Docker invocation shape (mocked subprocess.run)
- Reference registration helper
"""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from axiom_ext_openmc.adapter import OpenMCKernelAdapter
from axiom_ext_openmc.references.nrc_ml2327 import (
    OPENMC_NRC_ML2327_REFERENCES,
    install_references,
)
from axiom.compute.adapters.base import KernelResult


@pytest.fixture
def adapter():
    return OpenMCKernelAdapter()


@pytest.fixture
def basic_state(tmp_path):
    input_dir = tmp_path / "openmc_input"
    input_dir.mkdir()
    return {
        "input_dir": str(input_dir),
        "n_particles": 100000,
        "n_active_cycles": 50,
        "n_inactive_cycles": 20,
        "rng_seed": 42,
        "xs_library": "ENDF/B-VIII.0",
    }


# ----- Adapter contract (regression of Phase 2a inline tests) -----


def test_adapter_name():
    assert OpenMCKernelAdapter.name == "openmc"


def test_adapter_returns_kernel_result_on_success(adapter, basic_state):
    fake_statepoint = {
        "k_eff": 1.00342,
        "k_eff_std": 0.00012,
        "n_cycles": 50,
        "shannon_entropy": 6.13,
        "convergence": "stationary",
        "tallies": {},
        "lost_particles": 0,
    }
    with patch.object(OpenMCKernelAdapter, "_run_openmc_subprocess") as run, \
         patch.object(OpenMCKernelAdapter, "_parse_statepoint") as parse:
        run.return_value = (0, "", "")
        parse.return_value = fake_statepoint
        result = adapter.execute(basic_state, kernel_options={"runner": "subprocess"})

    assert isinstance(result, KernelResult)
    assert result.fault is None
    assert result.value_summary["k_eff"] == pytest.approx(1.00342)


def test_adapter_detects_lost_particles(adapter, basic_state):
    statepoint_with_lost = {
        "k_eff": 1.0,
        "k_eff_std": 0.001,
        "n_cycles": 50,
        "shannon_entropy": 6.0,
        "convergence": "stationary",
        "tallies": {},
        "lost_particles": 8432,
    }
    with patch.object(OpenMCKernelAdapter, "_run_openmc_subprocess") as run, \
         patch.object(OpenMCKernelAdapter, "_parse_statepoint") as parse:
        run.return_value = (0, "", "")
        parse.return_value = statepoint_with_lost
        result = adapter.execute(basic_state, kernel_options={"runner": "subprocess"})

    assert result.fault is not None
    assert result.fault.name == "lost_particles"


def test_adapter_subprocess_failure(adapter, basic_state):
    with patch.object(OpenMCKernelAdapter, "_run_openmc_subprocess") as run:
        run.return_value = (1, "", "openmc: cannot read geometry.xml")
        result = adapter.execute(basic_state, kernel_options={"runner": "subprocess"})

    assert result.fault is not None
    assert result.fault.name == "subprocess_failure"


def test_adapter_missing_input_dir_raises(adapter):
    state = {
        "input_dir": "/nonexistent/path",
        "n_particles": 1000,
        "n_active_cycles": 10,
        "n_inactive_cycles": 5,
        "rng_seed": 1,
        "xs_library": "ENDF/B-VIII.0",
    }
    with pytest.raises(ValueError, match="input_dir does not exist"):
        adapter.execute(state, kernel_options={"runner": "subprocess"})


def test_adapter_self_registers_into_axiom_compute_registry():
    from axiom.compute.adapters import get_adapter
    a = get_adapter("openmc")
    assert isinstance(a, OpenMCKernelAdapter)


# ----- Runner selection -----


def test_explicit_runner_choice(adapter):
    """kernel_options['runner']='docker' overrides auto-detect."""
    assert adapter._select_runner({"runner": "docker"}) == "docker"
    assert adapter._select_runner({"runner": "subprocess"}) == "subprocess"
    assert adapter._select_runner({"runner": "ssh:rascal"}) == "ssh:rascal"


def test_auto_detect_prefers_native_openmc(adapter):
    """When 'openmc' is on PATH, auto-select is 'subprocess'."""
    with patch("axiom_ext_openmc.adapter.shutil.which") as which:
        which.side_effect = lambda name: "/usr/local/bin/openmc" if name == "openmc" else None
        assert adapter._select_runner({}) == "subprocess"


def test_auto_detect_falls_back_to_docker(adapter):
    """When 'openmc' is missing but Docker is available, auto-select is 'docker'."""
    with patch("axiom_ext_openmc.adapter.shutil.which") as which:
        which.side_effect = lambda name: "/usr/local/bin/docker" if name == "docker" else None
        assert adapter._select_runner({}) == "docker"


def test_auto_detect_raises_when_nothing_available(adapter):
    """Neither openmc nor docker → clear error pointing to install paths."""
    with patch("axiom_ext_openmc.adapter.shutil.which") as which:
        which.return_value = None
        with pytest.raises(RuntimeError, match="no OpenMC runner available"):
            adapter._select_runner({})


# ----- Docker runner -----


def test_docker_runner_invokes_docker_with_bind_mount(adapter, basic_state):
    """The docker runner constructs a 'docker run --rm -v ... openmc/openmc' command."""
    fake_statepoint = {
        "k_eff": 1.0,
        "k_eff_std": 0.001,
        "n_cycles": 10,
        "shannon_entropy": 6.0,
        "convergence": "stationary",
        "tallies": {},
        "lost_particles": 0,
    }
    with patch("axiom_ext_openmc.adapter.subprocess.run") as proc_run, \
         patch.object(OpenMCKernelAdapter, "_parse_statepoint") as parse:
        proc_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        parse.return_value = fake_statepoint

        result = adapter.execute(basic_state, kernel_options={"runner": "docker"})

        # Verify subprocess.run was called with docker invocation
        call_args = proc_run.call_args[0][0]
        assert call_args[0] == "docker"
        assert call_args[1] == "run"
        assert "--rm" in call_args
        assert "-v" in call_args
        assert any("openmc" in arg for arg in call_args)

    assert result.fault is None
    assert result.value_summary["k_eff"] == 1.0


def test_docker_runner_custom_image(adapter, basic_state):
    """kernel_options['docker_image'] overrides the default image."""
    fake_statepoint = {
        "k_eff": 1.0, "k_eff_std": 0.001, "n_cycles": 10,
        "shannon_entropy": 6.0, "convergence": "stationary",
        "tallies": {}, "lost_particles": 0,
    }
    with patch("axiom_ext_openmc.adapter.subprocess.run") as proc_run, \
         patch.object(OpenMCKernelAdapter, "_parse_statepoint") as parse:
        proc_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        parse.return_value = fake_statepoint

        adapter.execute(basic_state, kernel_options={
            "runner": "docker",
            "docker_image": "openmc/openmc:0.14.2-bundled-data",
        })

        call_args = proc_run.call_args[0][0]
        assert "openmc/openmc:0.14.2-bundled-data" in call_args


def test_ssh_runner_not_yet_implemented(adapter, basic_state):
    """SSH runner is Phase 2c+; raises NotImplementedError today."""
    with pytest.raises(NotImplementedError, match="ssh runner"):
        adapter.execute(basic_state, kernel_options={"runner": "ssh:rascal"})


def test_unknown_runner_raises(adapter, basic_state):
    """An unrecognized runner name fails fast."""
    with pytest.raises(ValueError, match="unknown OpenMC runner"):
        adapter.execute(basic_state, kernel_options={"runner": "warp-drive"})


# ----- References -----


def test_references_have_correct_shape():
    """All NRC ML2327 references declare URI, value, uncertainty, unit, source."""
    for ref in OPENMC_NRC_ML2327_REFERENCES:
        assert ref.uri.startswith("reference://nrc-ml2327/triga-netl-")
        assert ref.uri.endswith("/k-eff")
        assert ref.value > 0
        assert ref.uncertainty > 0
        assert ref.unit == "pcm"
        assert ref.source == "NRC ML2327"


def test_install_references_into_dict_backed_registry():
    """install_references works with a duck-typed registry that takes dicts."""
    captured = []
    class DictRegistry:
        def register(self, item):
            captured.append(item)

    count = install_references(DictRegistry())
    assert count == len(OPENMC_NRC_ML2327_REFERENCES)
    assert len(captured) == count
