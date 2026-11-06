# Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""``python -m axiom_ext_openmc`` is the same CLI as ``axiom-openmc``."""

from axiom_ext_openmc.commands.openmc import main

raise SystemExit(main())
