# Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""Toolkit callables. Each one checks its arguments and calls the library.

Nothing in this module starts OpenMC except ``run_input``, and that function
does it by calling :func:`axiom_ext_openmc.library.run_input`, which calls
the production adapter. There is no second runner here.
"""

from __future__ import annotations

from typing import Any

from axiom_ext_openmc import library

__all__ = [
    "check_runner",
    "grade",
    "list_cases",
    "parse_summary",
    "run_input",
]


def _result(*, ok: bool, value: Any = None, errors: list[str] | None = None) -> Any:
    """Build the platform ``SkillResult``.

    If that type cannot be imported, say so. Do not invent a stand-in result
    type for the caller to mistake for the real one.
    """
    try:
        from axiom.infra.skills import SkillResult
    except ImportError as exc:
        raise ImportError(
            "axiom.infra.skills.SkillResult is not importable, so this "
            "toolkit skill cannot return a result. Install axiom-os-lm. "
            "The same operation is available as a plain function in "
            "axiom_ext_openmc.library."
        ) from exc
    return SkillResult(ok=ok, value=value, errors=list(errors or []))


def check_runner(params: dict[str, Any], ctx: Any) -> Any:
    """Report runner and nuclear-data availability. Reads nothing the user wrote."""
    del params, ctx
    return _result(ok=True, value=library.runner_status())


def list_cases(params: dict[str, Any], ctx: Any) -> Any:
    """List the verification ladder. Does not build or run a case."""
    del params, ctx
    cases = library.list_cases()
    return _result(ok=True, value={"cases": cases, "count": len(cases)})


def grade(params: dict[str, Any], ctx: Any) -> Any:
    """Grade one k-eff. Provisional references do not come back as agreement."""
    del ctx
    uri = params.get("reference_uri")
    if not isinstance(uri, str) or not uri.startswith("reference://"):
        return _result(
            ok=False,
            errors=[
                "reference_uri must be a reference:// URI. "
                "Take it from openmc.list_cases (each case's reference_uri) "
                "or from the verification case you ran."
            ],
        )
    raw = params.get("k_eff")
    try:
        k_eff = float(raw)
    except (TypeError, ValueError):
        return _result(
            ok=False,
            errors=[
                "k_eff must be a number. Pass the k_eff produced by "
                "openmc.run_input or openmc.parse_summary."
            ],
        )
    std_raw = params.get("k_eff_std")
    k_eff_std: float | None
    if std_raw is None or std_raw == "":
        k_eff_std = None
    else:
        try:
            k_eff_std = float(std_raw)
        except (TypeError, ValueError):
            return _result(
                ok=False,
                errors=["k_eff_std must be a number when it is supplied."],
            )
    return _result(ok=True, value=library.grade(uri, k_eff, k_eff_std))


def parse_summary(params: dict[str, Any], ctx: Any) -> Any:
    """Parse the summary the adapter already parses. No second HDF5 reader."""
    del ctx
    input_dir = params.get("input_dir")
    if not isinstance(input_dir, str) or not input_dir:
        return _result(
            ok=False,
            errors=[
                "pass input_dir as the path of the directory OpenMC wrote. "
                "A result.json in that directory is read; a statepoint with "
                "no result.json is reported as host-side HDF5 parsing not "
                "implemented, which is the adapter's own answer."
            ],
        )
    try:
        summary = library.parse_summary(input_dir)
    except (FileNotFoundError, NotImplementedError, OSError, ValueError) as exc:
        return _result(ok=False, errors=[str(exc)])
    return _result(ok=True, value=summary)


def run_input(params: dict[str, Any], ctx: Any) -> Any:
    """Run one input directory. Statistics come from the caller, not a hidden default."""
    del ctx
    input_dir = params.get("input_dir")
    if not isinstance(input_dir, str) or not input_dir:
        return _result(
            ok=False,
            errors=[
                "pass input_dir pointing at a directory that contains "
                "geometry.xml, materials.xml, and settings.xml, or a spec.json "
                "for the container runner. Build a verification case into a "
                "fresh directory first; this skill does not invent geometry."
            ],
        )
    counts: dict[str, int] = {}
    for key in ("n_particles", "n_active_cycles", "n_inactive_cycles", "rng_seed"):
        raw = params.get(key)
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return _result(
                ok=False,
                errors=[
                    f"{key} must be an integer. Copy it from the verification "
                    "case (openmc.list_cases) rather than choosing a second set."
                ],
            )
        if key != "rng_seed" and value <= 0:
            return _result(
                ok=False,
                errors=[f"{key} must be positive; a run with no particles is not a result."],
            )
        counts[key] = value

    options = params.get("kernel_options") or {}
    if not isinstance(options, dict):
        return _result(
            ok=False,
            errors=["kernel_options must be a mapping (runner, docker_image, timeout_seconds)."],
        )
    xs = params.get("xs_library")
    if xs is not None and not isinstance(xs, str):
        return _result(ok=False, errors=["xs_library must be a string when supplied."])

    try:
        result = library.run_input(
            input_dir,
            n_particles=counts["n_particles"],
            n_active_cycles=counts["n_active_cycles"],
            n_inactive_cycles=counts["n_inactive_cycles"],
            rng_seed=counts["rng_seed"],
            kernel_options=options,
            xs_library=xs,
        )
    except (ValueError, RuntimeError, FileNotFoundError, NotImplementedError) as exc:
        return _result(ok=False, errors=[str(exc)])

    summary = dict(result.value_summary or {})
    fault = result.fault
    value = {
        "k_eff": summary.get("k_eff"),
        "k_eff_std": summary.get("k_eff_std"),
        "value_summary": summary,
        "fault": None
        if fault is None
        else {"name": fault.name, "evidence": dict(fault.evidence)},
    }
    if fault is not None:
        return _result(
            ok=False,
            value=value,
            errors=[f"OpenMC run faulted: {fault.name}"],
        )
    return _result(ok=True, value=value)
