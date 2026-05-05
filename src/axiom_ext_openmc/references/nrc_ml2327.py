# Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""NRC ML2327 reference solutions — TRIGA NETL Safety Analysis Report (2023).

Source: https://www.nrc.gov/docs/ML2327/ML23279A146.pdf (NRC ML2327)

This module declares reference solutions for benchmark cases that the OpenMC
extension can verify against (axis A3 of the 5-axis verification matrix).

Phase 2 ships a small seed set; consumers (NeutronOS twin extension via the
TRIGAProvider) install these references into their reference registry on import.

NOTE (Phase 2): Specific values below are **placeholders** marked TBD-FROM-DOC.
They will be populated with actual values from NRC ML2327 §4 (TRIGA reactor
physics) when those values are extracted by domain reviewers. The structure
is canonical so consumers can wire against the names today.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReferenceSpec:
    """A reference value declared by this module.

    The OpenMC extension exposes these via `OPENMC_NRC_ML2327_REFERENCES` so
    consumers can iterate and register them into a ReferenceRegistry of their
    choice (per the InMemoryReferenceRegistry in the NeutronOS twin extension).
    """
    uri: str
    value: float
    uncertainty: float
    unit: str
    source: str = "NRC ML2327"
    citation: str = "NETL TRIGA Safety Analysis Report, NRC ML2327, August 2023"


# Phase 2 seed set — placeholders for canonical TRIGA NETL Problem 1A (2D pin cell).
# Real values come from the SAR; reviewers replace the TBD-FROM-DOC values
# before Phase 2c real-OpenMC integration.

OPENMC_NRC_ML2327_REFERENCES: list[ReferenceSpec] = [
    # TRIGA NETL Problem 1A — 2D pin cell at room temperature (cold critical config)
    ReferenceSpec(
        uri="reference://nrc-ml2327/triga-netl-P1A/k-eff",
        value=1.00203,        # placeholder — to be confirmed from NRC ML2327
        uncertainty=0.00050,  # placeholder — 50 pcm
        unit="pcm",
    ),
    # TRIGA NETL Problem 1B — 2D pin cell at 600 K fuel temperature
    ReferenceSpec(
        uri="reference://nrc-ml2327/triga-netl-P1B/k-eff",
        value=0.99821,        # placeholder
        uncertainty=0.00050,
        unit="pcm",
    ),
    # TRIGA NETL Problem 1C — 2D pin cell at 823.15 K (peak allowed fuel T per SAR §4.4)
    ReferenceSpec(
        uri="reference://nrc-ml2327/triga-netl-P1C/k-eff",
        value=0.99650,        # placeholder
        uncertainty=0.00050,
        unit="pcm",
    ),
]


def install_references(registry) -> int:
    """Register all NRC ML2327 references into the given registry; return count installed.

    Compatible with any ReferenceRegistry that implements .register(reference)
    accepting a dict-like or Reference-shaped object. The duck-typing here keeps
    the openmc extension free of NeutronOS imports while still being usable from
    the NeutronOS twin extension's InMemoryReferenceRegistry.
    """
    from dataclasses import asdict

    count = 0
    for spec in OPENMC_NRC_ML2327_REFERENCES:
        # Pass as a dict so the consumer can adapt to its Reference dataclass.
        try:
            # Try the structured form (works with neutron_os Reference).
            from neutron_os.extensions.builtins.twin.references import Reference
            registry.register(Reference(**asdict(spec)))
        except ImportError:
            # Consumer is using a different Reference type or dict registry.
            registry.register(asdict(spec))
        count += 1
    return count
