# Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""AEOS adapter capability. The class itself stays in ``adapter`` so the
Docker runner script, which is located beside that module, keeps one path.
"""

from axiom_ext_openmc.adapter import OpenMCKernelAdapter

__all__ = ["OpenMCKernelAdapter"]
