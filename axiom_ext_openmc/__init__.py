# Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""OpenMC physics-code extension — per ADR-018.

The public surface is the library: runner status, the verification ladder,
model checks, statepoint tables, a dry-run plan, summary parsing, a run
through the production adapter, and reference grading that does not treat a
placeholder as agreement. Importing this package does not import the adapter
or h5py, so it does not require ``axiom.compute`` or a statepoint reader
until one of those functions is called.

The toolkit (``axiom_ext_openmc.skills.bind``) and the ``axiom-openmc``
command register the same operations. Neither is imported here.
"""

from axiom_ext_openmc.library import (
    check_cross_sections,
    compare_statepoints,
    grade,
    list_cases,
    parse_summary,
    plan_run,
    read_statepoint,
    run_input,
    runner_status,
    summarize_model,
    validate_model,
)

__version__ = "0.2.0"

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
