# Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""Can this machine actually run OpenMC?

Two things are needed and they fail differently: the Python package, and a
nuclear data library the ``OPENMC_CROSS_SECTIONS`` environment variable points
at. Answering that in one place, with a reason a human can act on, keeps the
"we verified nothing" case loud instead of letting it hide behind a bare
``importorskip``.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

__all__ = [
    "openmc_available",
    "cross_sections_path",
    "unavailable_reason",
    "can_run_openmc",
]

CROSS_SECTIONS_ENV = "OPENMC_CROSS_SECTIONS"


def openmc_available() -> bool:
    """True when the ``openmc`` package can be imported.

    Uses ``find_spec`` rather than importing: OpenMC is expensive to import and
    the answer is needed during collection, before any case runs.
    """
    try:
        return importlib.util.find_spec("openmc") is not None
    except (ImportError, ValueError):
        return False


def cross_sections_path() -> Path | None:
    """The configured nuclear data library, if it exists on disk.

    An exported variable pointing at a missing file is worse than an unset one,
    because it looks configured — so the file must exist to count.
    """
    raw = os.environ.get(CROSS_SECTIONS_ENV, "").strip()
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_file() else None


def unavailable_reason() -> str | None:
    """Why OpenMC cannot run here, or ``None`` when it can."""
    missing: list[str] = []

    if not openmc_available():
        missing.append(
            "the 'openmc' package is not importable "
            "(conda install -c conda-forge openmc)"
        )

    if cross_sections_path() is None:
        missing.append(
            f"{CROSS_SECTIONS_ENV} is unset or does not point at an existing "
            "file (download a data library from https://openmc.org/data/ and "
            f"export {CROSS_SECTIONS_ENV}=/path/to/cross_sections.xml)"
        )

    if not missing:
        return None
    return "OpenMC cannot run here: " + "; ".join(missing)


def can_run_openmc() -> bool:
    """True when a real OpenMC run is possible."""
    return unavailable_reason() is None
