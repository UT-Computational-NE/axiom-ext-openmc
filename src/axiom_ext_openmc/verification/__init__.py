# Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""Run real physics, and say so when you cannot.

Everything else in this package mocks the solver. This subpackage is where the
extension's claim to run OpenMC is actually exercised: a ladder of cases, each
building an input directory that the production adapter executes.

Three pieces, each with one job:

- :mod:`~axiom_ext_openmc.verification.availability` — can this machine run
  OpenMC, and if not, which of the two prerequisites is missing?
- :mod:`~axiom_ext_openmc.verification.cases` — the ordered ladder of runnable
  problems and the registry that holds them.
- :mod:`~axiom_ext_openmc.verification.runner` — build a case, delegate to the
  adapter. No execution logic of its own.

Importing this package does not import OpenMC, so the ladder can be listed
anywhere. See AGENTS.md for adding a rung or onboarding another physics code.
"""

from __future__ import annotations

from axiom_ext_openmc.verification.availability import (
    can_run_openmc,
    cross_sections_path,
    openmc_available,
    unavailable_reason,
)
from axiom_ext_openmc.verification.cases import (
    CaseRegistry,
    VerificationCase,
    default_registry,
    register,
)
from axiom_ext_openmc.verification.runner import run_case

__all__ = [
    "CaseRegistry",
    "VerificationCase",
    "can_run_openmc",
    "cross_sections_path",
    "default_registry",
    "openmc_available",
    "register",
    "run_case",
    "unavailable_reason",
]
