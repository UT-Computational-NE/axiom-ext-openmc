# Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""OpenMC physics-code extension — per ADR-018.

This package's top-level import is intentionally minimal so submodules
(notably `axiom_ext_openmc.references`) can be imported by consumers that
don't have axiom.compute on their import path (e.g., NeutronOS contexts that
seed reference solutions without invoking the adapter).

To register the OpenMC CodeAdapter with axiom.compute.adapters, import the
adapter module directly:

    from axiom_ext_openmc.adapter import OpenMCKernelAdapter

The adapter self-registers on import.
"""

__version__ = "0.1.0"
__all__: list[str] = []
