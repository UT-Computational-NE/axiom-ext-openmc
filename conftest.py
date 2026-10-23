# Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""sys.path plumbing only.

This file used to assume it lived at ``packages/<name>/conftest.py`` inside a
monorepo and indexed ``parents[2] / "src"`` so a vendored ``axiom`` tree won
over other editable installs. This repository is the extension itself, at the
checkout root, so that index does not exist. ``axiom`` comes from the
installed ``axiom-os-lm`` package. A sibling source tree is prepended only
when it is actually there.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _monorepo_axiom_src() -> Path | None:
    parents = Path(__file__).resolve().parents
    if len(parents) <= 2:
        return None
    candidate = parents[2] / "src"
    if (candidate / "axiom" / "__init__.py").is_file():
        return candidate
    return None


_src = _monorepo_axiom_src()
if _src is not None and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))
    for _mod in list(sys.modules):
        if _mod == "axiom" or _mod.startswith("axiom."):
            del sys.modules[_mod]
