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
    "check",
    "check_runner",
    "diff",
    "grade",
    "list_cases",
    "parse_summary",
    "review",
    "run_input",
    "show",
    "stat",
    "validate",
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
                "A result.json in that directory is read. Otherwise "
                "statepoint.*.h5 is read by the shared statepoint reader."
            ],
        )
    try:
        summary = library.parse_summary(input_dir)
    except (FileNotFoundError, NotImplementedError, OSError, ValueError, ImportError) as exc:
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


def _required_str(params: dict[str, Any], key: str, fix: str) -> tuple[str | None, Any]:
    value = params.get(key)
    if not isinstance(value, str) or not value:
        return None, _result(ok=False, errors=[fix])
    return value, None


def validate(params: dict[str, Any], ctx: Any) -> Any:
    """Validate an input directory. Does not start a solve."""
    del ctx
    input_dir, failed = _required_str(
        params,
        "input_dir",
        "Pass input_dir pointing at a directory that contains materials.xml, "
        "geometry.xml, and settings.xml.",
    )
    if failed is not None:
        return failed
    use_openmc = params.get("use_openmc", False)
    if not isinstance(use_openmc, bool):
        return _result(ok=False, errors=["use_openmc must be a boolean when supplied."])
    report = library.validate_model(input_dir, use_openmc=use_openmc)
    return _result(
        ok=bool(report["ok"]),
        value=report,
        errors=[item["message"] for item in report["errors"]],
    )


def show(params: dict[str, Any], ctx: Any) -> Any:
    """Summarize the model that was written. Does not start a solve."""
    del ctx
    input_dir, failed = _required_str(
        params,
        "input_dir",
        "Pass input_dir pointing at a directory that contains materials.xml, "
        "geometry.xml, and settings.xml.",
    )
    if failed is not None:
        return failed
    report = library.summarize_model(input_dir)
    return _result(
        ok=not report["errors"],
        value=report,
        errors=[item["message"] for item in report["errors"]],
    )


def stat(params: dict[str, Any], ctx: Any) -> Any:
    """Read one statepoint. The numbers are the ones in the file."""
    del ctx
    path, failed = _required_str(
        params,
        "path",
        "Pass path to a statepoint.*.h5 file or a directory that contains one.",
    )
    if failed is not None:
        return failed
    try:
        report = library.read_statepoint(path)
    except (FileNotFoundError, ValueError, ImportError, OSError) as exc:
        return _result(ok=False, errors=[str(exc)])
    return _result(ok=True, value=report)


def diff(params: dict[str, Any], ctx: Any) -> Any:
    """Compare two statepoints. delta is left minus right."""
    del ctx
    left, failed = _required_str(params, "left", "Pass left as the path of the first statepoint.")
    if failed is not None:
        return failed
    right, failed = _required_str(params, "right", "Pass right as the path of the second statepoint.")
    if failed is not None:
        return failed
    try:
        report = library.compare_statepoints(left, right)
    except (FileNotFoundError, ValueError, ImportError, OSError) as exc:
        return _result(ok=False, errors=[str(exc)])
    return _result(ok=True, value=report)


def check(params: dict[str, Any], ctx: Any) -> Any:
    """Check the cross-section index and, when asked, the model's nuclide names."""
    del ctx
    path = params.get("path")
    model = params.get("model_dir")
    if path is not None and not isinstance(path, str):
        return _result(ok=False, errors=["path must be a string when supplied."])
    if model is not None and not isinstance(model, str):
        return _result(ok=False, errors=["model_dir must be a string when supplied."])
    report = library.check_cross_sections(path or None, model or None)
    return _result(
        ok=bool(report["ok"]),
        value=report,
        errors=[item["message"] for item in report["errors"]],
    )


def review(params: dict[str, Any], ctx: Any) -> Any:
    """Plan a run. executed is false. OpenMC is not started."""
    del ctx
    input_dir, failed = _required_str(
        params,
        "input_dir",
        "Pass input_dir pointing at a directory that contains materials.xml, "
        "geometry.xml, and settings.xml.",
    )
    if failed is not None:
        return failed
    runner = params.get("runner")
    if runner is not None and not isinstance(runner, str):
        return _result(ok=False, errors=["runner must be a string when supplied."])
    options = {"runner": runner} if runner else None
    report = library.plan_run(input_dir, kernel_options=options)
    errors = []
    if not report["validation"]["ok"]:
        errors.extend(item["message"] for item in report["validation"]["errors"])
    if not report["cross_sections"]["ok"]:
        errors.extend(item["message"] for item in report["cross_sections"]["errors"])
    if not report["runner"].get("connected"):
        reason = report["runner"].get("reason")
        if reason:
            errors.append(reason)
    return _result(ok=bool(report["ready"]), value=report, errors=errors)
