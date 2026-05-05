# Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""ORNL-TM-0728 reference solutions — MSR (Molten Salt Reactor) physics benchmark.

Source: ORNL-TM-0728, "Molten Salt Reactor Experiment (MSRE) Design and
Operations Report Part I" — the canonical primary-physics reference for
historical MSRE configurations and the basis for the modern MSR progression
problem set N_1..N_5.

Phase 5 ships a small seed set covering the MSR neutronics progression
problems N_1..N_5; specific values are placeholders pending domain review
(same as the NRC ML2327 module's TRIGA seeds). Reviewers replace the
TBD-FROM-DOC values with actual ORNL-TM-0728 §X values before Phase 5d
real-OpenMC integration on the MSR set.

The structure is canonical so consumers (NeutronOS MSRProvider) can wire
against the URIs today.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReferenceSpec:
    """A reference value declared by this module.

    Mirrors the NRC ML2327 ReferenceSpec shape for consistency.
    """

    uri: str
    value: float
    uncertainty: float
    unit: str
    source: str = "ORNL-TM-0728"
    citation: str = "ORNL-TM-0728, Molten Salt Reactor Experiment Design and Operations Report Part I"


# Phase 5 seed set — placeholders for canonical MSR progression problems.
# Real values from ORNL-TM-0728 to be confirmed by domain reviewers.

OPENMC_ORNL_TM_0728_REFERENCES: list[ReferenceSpec] = [
    # MSR N_1: Salt-bath / minimum-fuel critical configuration
    ReferenceSpec(
        uri="reference://ornl-tm-0728/msr-N_1/k-eff",
        value=1.00120,        # placeholder
        uncertainty=0.00060,  # placeholder — 60 pcm typical for benchmark MSR cases
        unit="pcm",
    ),
    # MSR N_2: Pin-cell-equivalent for MSR fuel salt geometry
    ReferenceSpec(
        uri="reference://ornl-tm-0728/msr-N_2/k-eff",
        value=1.00342,        # placeholder
        uncertainty=0.00050,  # placeholder
        unit="pcm",
    ),
    # MSR N_3: 2D core slice w/ fuel salt + graphite moderator + control rods
    ReferenceSpec(
        uri="reference://ornl-tm-0728/msr-N_3/k-eff",
        value=0.99850,        # placeholder
        uncertainty=0.00075,  # placeholder
        unit="pcm",
    ),
    # MSR N_4: 3D full core configuration (cold critical)
    ReferenceSpec(
        uri="reference://ornl-tm-0728/msr-N_4/k-eff",
        value=1.00021,        # placeholder
        uncertainty=0.00075,  # placeholder
        unit="pcm",
    ),
    # MSR N_5: 3D full core w/ fission product evolution (depletion-aware)
    ReferenceSpec(
        uri="reference://ornl-tm-0728/msr-N_5/k-eff",
        value=0.99750,        # placeholder
        uncertainty=0.00100,  # depletion uncertainties typically larger
        unit="pcm",
    ),
]


def install_references(registry) -> int:
    """Register all ORNL-TM-0728 references into the given registry; return count installed."""
    from dataclasses import asdict

    count = 0
    for spec in OPENMC_ORNL_TM_0728_REFERENCES:
        try:
            from neutron_os.extensions.builtins.twin.references import Reference
            registry.register(Reference(**asdict(spec)))
        except ImportError:
            registry.register(asdict(spec))
        count += 1
    return count
