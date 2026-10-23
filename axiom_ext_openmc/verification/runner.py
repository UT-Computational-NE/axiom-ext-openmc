# Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""Build a case's inputs, then hand them to the adapter.

This module owns no execution logic. :class:`~axiom_ext_openmc.adapter.
OpenMCKernelAdapter` already selects a runner, invokes OpenMC, parses the
statepoint and faults on lost particles. Reimplementing any of that here would
create a second code path that drifts from the one production uses — and then
verification would be verifying the wrong thing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from axiom_ext_openmc.adapter import OpenMCKernelAdapter
from axiom_ext_openmc.verification.cases import VerificationCase

__all__ = ["run_case", "REQUIRED_INPUTS"]

#: OpenMC will not start without these. Checking here turns a broken case
#: builder into a clear error instead of a confusing solver parse failure.
REQUIRED_INPUTS = ("geometry.xml", "materials.xml", "settings.xml")


def run_case(
    case: VerificationCase,
    workdir: Path,
    *,
    kernel_options: dict[str, Any] | None = None,
):
    """Build ``case`` into ``workdir`` and execute it.

    Args:
        case: the problem to build and run.
        workdir: directory to build into; created if absent. The runner owns it
            so concurrent runs of the same case cannot collide.
        kernel_options: passed through to the adapter — ``runner``,
            ``docker_image`` and friends.

    Returns:
        The adapter's ``KernelResult``.

    Raises:
        RuntimeError: if the case's builder wrote no OpenMC input files.
    """
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    case.build(workdir, case)

    written = [name for name in REQUIRED_INPUTS if (workdir / name).is_file()]
    if not written:
        raise RuntimeError(
            f"verification case {case.name!r} wrote no OpenMC input files into "
            f"{workdir}; expected at least one of {', '.join(REQUIRED_INPUTS)}"
        )

    determinism_state = {
        "input_dir": str(workdir),
        "n_particles": case.n_particles,
        "n_active_cycles": case.n_active_cycles,
        "n_inactive_cycles": case.n_inactive_cycles,
        "rng_seed": case.rng_seed,
    }

    return OpenMCKernelAdapter().execute(determinism_state, kernel_options or {})
