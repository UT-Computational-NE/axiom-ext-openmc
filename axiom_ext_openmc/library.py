# Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""The library the OpenMC toolkit calls.

Skills validate parameters and return a ``SkillResult``. The operations live
here so a person, a test, or another extension can do the same work without
an agent in the loop. Importing this module does not import OpenMC and does
not import the adapter, so listing cases and grading references works on a
machine that has neither.

Grading never reports agreement against a provisional reference. A missing
reference is ``no_reference``. A placeholder is ``provisional``. Only a
reference whose ``provisional`` flag has been cleared is compared, and then
only as a magnitude check against its stated uncertainty.
"""

from __future__ import annotations

import math
import shutil
from pathlib import Path
from typing import Any

from axiom_ext_openmc.references.nrc_ml2327 import OPENMC_NRC_ML2327_REFERENCES
from axiom_ext_openmc.references.ornl_tm_0728 import OPENMC_ORNL_TM_0728_REFERENCES

__all__ = [
    "grade",
    "list_cases",
    "parse_summary",
    "run_input",
    "runner_status",
]


def _specs() -> list[Any]:
    return [*OPENMC_NRC_ML2327_REFERENCES, *OPENMC_ORNL_TM_0728_REFERENCES]


def _find_spec(reference_uri: str) -> Any | None:
    for spec in _specs():
        if spec.uri == reference_uri:
            return spec
    return None


def runner_status() -> dict[str, Any]:
    """What is present on this machine, stated as separate facts.

    The Python package plus a nuclear-data file is what a real verification
    run needs. The ``openmc`` binary and Docker are what the adapter's
    runners need. Those are not the same check, so this does not collapse
    them into one boolean.
    """
    from axiom_ext_openmc.verification.availability import (
        can_run_openmc,
        cross_sections_path,
        openmc_available,
        unavailable_reason,
    )

    data = cross_sections_path()
    return {
        "python_package": openmc_available(),
        "cross_sections": str(data) if data is not None else None,
        "openmc_binary": shutil.which("openmc") is not None,
        "docker": shutil.which("docker") is not None,
        "can_run_openmc": can_run_openmc(),
        "reason": unavailable_reason(),
    }


def list_cases() -> list[dict[str, Any]]:
    """The verification ladder, in registration order, without running it.

    Importing the builtin cases registers them. Builders import OpenMC only
    when called, so listing the ladder does not require OpenMC.
    """
    import axiom_ext_openmc.verification.builtin_cases  # noqa: F401 — registers
    from axiom_ext_openmc.verification.cases import default_registry

    cases = []
    for case in default_registry().all():
        cases.append(
            {
                "name": case.name,
                "description": case.description,
                "reference_uri": case.reference_uri,
                "n_particles": case.n_particles,
                "n_active_cycles": case.n_active_cycles,
                "n_inactive_cycles": case.n_inactive_cycles,
                "rng_seed": case.rng_seed,
            }
        )
    return cases


def grade(
    reference_uri: str,
    k_eff: float,
    k_eff_std: float | None = None,
) -> dict[str, Any]:
    """Compare ``k_eff`` to the reference at ``reference_uri``.

    Returns a dict with ``status`` of ``no_reference``, ``provisional``, or
    ``compared``. ``agrees`` is a bool only when ``status`` is ``compared``.
    Otherwise it is ``None``. Provisional specs do not contribute their
    placeholder value to the result.
    """
    spec = _find_spec(reference_uri)
    base: dict[str, Any] = {
        "reference_uri": reference_uri,
        "k_eff": k_eff,
        "k_eff_std": k_eff_std,
    }
    if spec is None:
        return {
            **base,
            "status": "no_reference",
            "agrees": None,
            "reason": f"no reference declared for {reference_uri}",
        }
    if getattr(spec, "provisional", False):
        return {
            **base,
            "status": "provisional",
            "agrees": None,
            "source": spec.source,
            "citation": spec.citation,
            "reason": (
                "reference value is a placeholder and was not compared; "
                "agreement is not reported"
            ),
        }

    delta = float(k_eff) - float(spec.value)
    tolerance = _tolerance(float(spec.uncertainty), k_eff_std)
    return {
        **base,
        "status": "compared",
        "agrees": abs(delta) <= tolerance,
        "reference_value": float(spec.value),
        "delta": delta,
        "tolerance": tolerance,
        "unit": spec.unit,
        "source": spec.source,
        "citation": spec.citation,
        "reason": (
            "compared |k_eff - reference| to the root-sum-square of the "
            "reference uncertainty and the reported standard deviation "
            "(the reference uncertainty alone when no standard deviation "
            "is supplied). This is a magnitude check, not a hypothesis test."
        ),
    }


def _tolerance(reference_uncertainty: float, k_eff_std: float | None) -> float:
    if k_eff_std is None:
        return reference_uncertainty
    return math.sqrt(reference_uncertainty**2 + float(k_eff_std) ** 2)


def parse_summary(input_dir: str | Path) -> dict[str, Any]:
    """Read the canonical summary the adapter already knows how to read.

    Host-side HDF5 parsing is not implemented on the adapter. This function
    does not add a second parser. It calls ``OpenMCKernelAdapter._parse_statepoint``
    and lets that method's ``NotImplementedError`` or ``FileNotFoundError``
    through.
    """
    path = Path(input_dir)
    if not path.is_dir():
        raise FileNotFoundError(
            f"input_dir does not exist or is not a directory: {path}"
        )
    from axiom_ext_openmc.adapter import OpenMCKernelAdapter

    return OpenMCKernelAdapter()._parse_statepoint(path)


def run_input(
    input_dir: str | Path,
    *,
    n_particles: int,
    n_active_cycles: int,
    n_inactive_cycles: int,
    rng_seed: int,
    kernel_options: dict[str, Any] | None = None,
    xs_library: str | None = None,
) -> Any:
    """Execute one input directory through the production adapter.

    Statistics are arguments, not a second default copied from a verification
    case. The caller passes the case's own counts. Returns the adapter's
    ``KernelResult``.
    """
    from axiom_ext_openmc.adapter import OpenMCKernelAdapter

    state: dict[str, Any] = {
        "input_dir": str(input_dir),
        "n_particles": n_particles,
        "n_active_cycles": n_active_cycles,
        "n_inactive_cycles": n_inactive_cycles,
        "rng_seed": rng_seed,
    }
    if xs_library is not None:
        state["xs_library"] = xs_library
    return OpenMCKernelAdapter().execute(state, dict(kernel_options or {}))
