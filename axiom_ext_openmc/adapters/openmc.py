# Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""Manifest entry for the OpenMC adapter.

Re-exports the one :class:`~axiom_ext_openmc.adapter.OpenMCKernelAdapter`.
A second class here would be a second code path.
"""

from axiom_ext_openmc.adapter import OpenMCKernelAdapter

__all__ = ["OpenMCKernelAdapter"]
