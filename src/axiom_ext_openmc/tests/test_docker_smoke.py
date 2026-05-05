# Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""Phase 2c — real Docker integration smoke test.

This test actually runs OpenMC inside the openmc/openmc container against a
trivial 2D pin cell, then dispatches it through axiom.compute.dispatch to
verify the full chain produces a signed receipt with a real k-eff.

Marked `slow` (and `docker`) — opt-in only. Skips automatically if Docker
is not available or the openmc/openmc image isn't pulled. Real run takes
~20 seconds on Apple Silicon via Rosetta.

Invoke with: pytest -v -m docker
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

pytestmark = [pytest.mark.docker, pytest.mark.slow]


def _docker_available() -> bool:
    """Check Docker is installed and responsive."""
    if not shutil.which("docker"):
        return False
    try:
        proc = subprocess.run(
            ["docker", "info"], capture_output=True, timeout=10,
        )
        return proc.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def _openmc_image_present() -> bool:
    """Check the openmc/openmc image is locally pulled."""
    try:
        proc = subprocess.run(
            ["docker", "image", "inspect", "openmc/openmc:latest"],
            capture_output=True, timeout=10,
        )
        return proc.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


@pytest.fixture(scope="module")
def docker_or_skip():
    if not _docker_available():
        pytest.skip("Docker not available; skipping real-OpenMC smoke test")
    if not _openmc_image_present():
        pytest.skip(
            "openmc/openmc:latest image not pulled; "
            "run `docker pull --platform linux/amd64 openmc/openmc:latest` first"
        )


def test_real_pin_cell_via_dispatch(docker_or_skip, tmp_path):
    """End-to-end real run: spec.json → docker openmc → result.json → signed receipt."""
    from axiom.compute import dispatch, DispatchSpec, verify_signature

    # Build a spec.json — the smallest pin cell that converges quickly.
    input_dir = tmp_path / "openmc_input"
    input_dir.mkdir()
    spec = {
        "n_particles": 5000,
        "n_active_cycles": 20,
        "n_inactive_cycles": 10,
        "rng_seed": 42,
    }
    (input_dir / "spec.json").write_text(json.dumps(spec))

    dispatch_spec = DispatchSpec(
        model_id="openmc-pincell-smoke",
        composition_hash="sha256:" + "0" * 64,
        kernel="openmc",
        peer_id="laptop",
        determinism_class="D-stat",  # Monte Carlo is statistical given seed
        determinism_state={
            "input_dir": str(input_dir),
            "n_particles": spec["n_particles"],
            "n_active_cycles": spec["n_active_cycles"],
            "n_inactive_cycles": spec["n_inactive_cycles"],
            "rng_seed": spec["rng_seed"],
            "xs_library": "ENDF/B-VIII.0",
        },
        kernel_options={"runner": "docker"},
    )

    result = dispatch(dispatch_spec)

    # Real run produced a signed receipt with a k-eff.
    assert not result.halted, f"unexpected halt: {result}"
    assert result.uri.startswith("axiom://compute/sha256:")
    assert result.value_summary["k_eff"] is not None
    # Smoke check: pin cell with reflective BCs at 4.95% enrichment is
    # over-fissile; k-eff should be > 1.0 by a wide margin.
    assert result.value_summary["k_eff"] > 1.0
    assert result.value_summary["k_eff"] < 2.0
    assert result.value_summary["k_eff_std"] > 0.0

    # Signature on the real receipt verifies.
    assert verify_signature(result) is True
