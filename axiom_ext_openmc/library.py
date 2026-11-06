# Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""The library the OpenMC toolkit and ``axiom-openmc`` call.

Skills and CLI verbs check arguments and call these functions. Importing
this module does not import OpenMC, h5py, or the adapter, so listing cases,
grading references, and reading XML works on a machine that has none of
them. Statepoint reading imports h5py when called. Running or planning a
directory imports the adapter when called.

Grading never reports agreement against a provisional reference. A missing
reference is ``no_reference``. A placeholder is ``provisional``. Only a
reference whose ``provisional`` flag has been cleared is compared, and then
only as a magnitude check against its stated uncertainty. Comparing two
statepoints is a separate magnitude check of the numbers those files
reported, and it is not a reference grade.
"""

from __future__ import annotations

import math
import shutil
from pathlib import Path
from typing import Any

from axiom_ext_openmc.inputs import check_cross_sections, summarize_model, validate_model
from axiom_ext_openmc.references.nrc_ml2327 import OPENMC_NRC_ML2327_REFERENCES
from axiom_ext_openmc.references.ornl_tm_0728 import OPENMC_ORNL_TM_0728_REFERENCES
from axiom_ext_openmc.statepoint import compare_statepoints, read_statepoint

__all__ = [
    "check_cross_sections",
    "compare_statepoints",
    "grade",
    "list_cases",
    "parse_summary",
    "plan_run",
    "read_statepoint",
    "run_input",
    "runner_status",
    "summarize_model",
    "validate_model",
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

    This calls ``OpenMCKernelAdapter._parse_statepoint`` and does not parse
    the file a second time. A ``result.json`` written by the container runner
    is that summary. Otherwise the adapter reads ``statepoint.*.h5`` through
    :func:`read_statepoint`.
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


def plan_run(
    input_dir: str | Path,
    *,
    kernel_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Describe a run and do not start one.

    The particle and batch counts in the plan are the ones written in
    ``settings.xml``. The adapter does not rewrite that file, so counts
    passed to :func:`run_input` are not applied here and are not applied
    by ``execute`` either. ``ready`` means the XML check passed, the
    selected cross-section index is usable, and ``connect`` found a local
    runner. It does not mean a result will match a reference.
    """
    directory = Path(input_dir)
    validation = validate_model(directory)
    summary = summarize_model(directory)
    data = check_cross_sections(model_dir=directory if directory.is_dir() else None)
    from axiom_ext_openmc.adapter import OpenMCKernelAdapter

    connect = OpenMCKernelAdapter().connect(dict(kernel_options or {}))
    batches = summary["settings"].get("batches")
    spec_json = directory.is_dir() and (directory / "spec.json").is_file()
    outputs = ["summary.h5"]
    if isinstance(batches, int) and batches > 0:
        outputs.append(f"statepoint.{batches}.h5")
    else:
        outputs.append("statepoint.<batches>.h5")
    return {
        "executed": False,
        "ready": bool(validation["ok"] and data["ok"] and connect.get("connected")),
        "input_dir": str(directory),
        "validation": validation,
        "summary": summary,
        "cross_sections": data,
        "runner": connect,
        "spec_json": spec_json,
        "invocation": (
            "Dry run: OpenMC was not started. A subprocess run executes the "
            "openmc binary with its working directory set to the input "
            "directory. A docker run executes openmc in the container when "
            "spec.json is absent, and the container runner script when "
            "spec.json is present. Neither path rewrites settings.xml. "
            + ("spec.json is present." if spec_json else "spec.json is not present.")
        ),
        "expected_outputs": outputs,
    }
