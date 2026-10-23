# Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""OpenMC physics-code extension — per ADR-018.

The public surface is the library: runner status, the verification ladder,
summary parsing, a run through the production adapter, and reference grading
that does not treat a placeholder as agreement. Importing this package does
not import the adapter, so it does not require ``axiom.compute`` until one of
those two functions is called.

The toolkit (``axiom_ext_openmc.skills.bind``) registers the same operations
as skills. It is not imported here, so a consumer that only wants the library
does not load the skill registry.
"""

from axiom_ext_openmc.library import (
    grade,
    list_cases,
    parse_summary,
    run_input,
    runner_status,
)

__version__ = "0.2.0"

__all__ = [
    "grade",
    "list_cases",
    "parse_summary",
    "run_input",
    "runner_status",
]
