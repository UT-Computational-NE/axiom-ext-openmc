# Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""The shipped ladder, simplest rung first.

Rung 1 is an infinite medium: one material, no geometry to get wrong, and a
multiplication factor that is a property of the material alone. If this rung is
wrong, nothing above it is worth debugging.

Importing this module registers its cases; it does **not** import OpenMC, so the
ladder is inspectable on a machine that cannot run it. Every builder imports
``openmc`` lazily, inside the call.

Adding a rung is described in AGENTS.md.
"""

from __future__ import annotations

from pathlib import Path

from axiom_ext_openmc.verification.cases import VerificationCase, register

__all__ = ["build_infinite_medium_uo2"]

#: Enough to converge an infinite medium in seconds while keeping the standard
#: deviation small enough to compare against a reference.
_QUICK = dict(n_particles=2000, n_active_cycles=40, n_inactive_cycles=10)


def build_infinite_medium_uo2(directory: Path, case: VerificationCase) -> None:
    """Write an infinite medium of 3%-enriched UO2.

    Reflective boundaries on a sphere make this an infinite medium: every
    escaping neutron returns, so the result is k-infinity for the material and
    depends on no geometric detail. That is what makes it the first rung — a
    wrong answer here is a materials or nuclear-data problem, never a geometry
    one.
    """
    import openmc  # imported lazily: the ladder is inspectable without OpenMC

    fuel = openmc.Material(name="uo2")
    fuel.add_nuclide("U235", 0.03)
    fuel.add_nuclide("U238", 0.97)
    fuel.add_nuclide("O16", 2.0)
    fuel.set_density("g/cm3", 10.4)
    openmc.Materials([fuel]).export_to_xml(directory / "materials.xml")

    boundary = openmc.Sphere(r=100.0, boundary_type="reflective")
    cell = openmc.Cell(name="medium", fill=fuel, region=-boundary)
    openmc.Geometry([cell]).export_to_xml(directory / "geometry.xml")

    settings = openmc.Settings()
    settings.run_mode = "eigenvalue"
    settings.particles = case.n_particles
    settings.batches = case.total_batches
    settings.inactive = case.n_inactive_cycles
    settings.seed = case.rng_seed
    settings.source = openmc.IndependentSource(
        space=openmc.stats.Point((0.0, 0.0, 0.0))
    )
    settings.export_to_xml(directory / "settings.xml")


register(
    VerificationCase(
        name="infinite_medium_uo2",
        description=(
            "Infinite medium of 3%-enriched UO2 at 10.4 g/cm3. k-infinity is a "
            "property of the material alone, so this rung isolates materials "
            "and nuclear data from geometry."
        ),
        reference_uri="reference://verification/infinite-medium-uo2/k-eff",
        build=build_infinite_medium_uo2,
        **_QUICK,
    )
)
