# Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""The shipped ladder, simplest rung first.

Each rung adds exactly one source of difficulty, so a failure localises:

1. **infinite medium** — one material, no geometry. A wrong answer is materials
   or nuclear data, never geometry.
2. **pin cell** — adds radial heterogeneity: self-shielding in the fuel and
   thermalisation in the moderator. A wrong answer here with rung 1 passing is a
   geometry or boundary-condition problem.
3. **assembly** — adds lattice heterogeneity and guide tubes. A wrong answer
   here with rung 2 passing is lattice construction, not pin physics.

Rungs 2 and 3 are adapted from the OpenMC Crash Course by Harrison Reisinger
(https://github.com/sarhon/OpenMC_Crash_Course), MIT licensed, used with
permission and reproduced under THIRD_PARTY_NOTICES.md. The dimensions,
compositions and lattice layout are his; only the packaging into
:class:`VerificationCase` is ours. His course exists to teach these problems in
order, which is exactly the property a verification ladder needs.

Importing this module registers its cases; it does **not** import OpenMC, so the
ladder is inspectable on a machine that cannot run it. Every builder imports
``openmc`` lazily, inside the call.

Adding a rung is described in AGENTS.md.
"""

from __future__ import annotations

from pathlib import Path

from axiom_ext_openmc.verification.cases import VerificationCase, register

__all__ = [
    "build_infinite_medium_uo2",
    "build_pincell_uo2",
    "build_assembly_17x17",
]

#: Enough to converge in seconds while keeping the standard deviation small
#: enough to compare against a reference. Rungs get more particles as geometric
#: detail grows, because the same statistical precision costs more histories.
_QUICK = dict(n_particles=2000, n_active_cycles=40, n_inactive_cycles=10)
_ASSEMBLY = dict(n_particles=4000, n_active_cycles=40, n_inactive_cycles=10)

#: Light-water-reactor pin geometry, in centimetres. From the crash course.
FUEL_RADIUS_CM = 0.39
CLADDING_RADIUS_CM = 0.45
PIN_PITCH_CM = 1.26
ASSEMBLY_SIZE = 17


def _course_materials():
    """Fuel, cladding and moderator as defined in the crash course.

    5% enriched UO2, zirconium cladding, and light water with the
    hydrogen-in-water thermal scattering law — without which a thermal system
    is badly wrong rather than slightly wrong.

    Rung 1 uses its own 3% composition because it is testing the material path
    in isolation; these are the course's numbers, kept as the course states them
    so a divergence from published results is attributable.
    """
    import openmc

    fuel = openmc.Material(name="fuel")
    fuel.add_nuclide("U235", 0.05)
    fuel.add_nuclide("U238", 0.95)
    fuel.add_nuclide("O16", 2.0)
    fuel.set_density("g/cm3", 10.0)

    cladding = openmc.Material(name="zirc")
    cladding.add_element("Zr", 1.0)
    cladding.set_density("g/cm3", 6.5)

    moderator = openmc.Material(name="water")
    moderator.add_nuclide("H1", 2.0)
    moderator.add_nuclide("O16", 1.0)
    moderator.set_density("g/cm3", 1.0)
    moderator.add_s_alpha_beta("c_H_in_H2O")

    return fuel, cladding, moderator


def _pin_universe(fuel, cladding, moderator):
    """One fuel pin: fuel, cladding annulus, surrounding moderator."""
    import openmc

    fuel_outer = openmc.ZCylinder(r=FUEL_RADIUS_CM)
    clad_outer = openmc.ZCylinder(r=CLADDING_RADIUS_CM)

    universe = openmc.Universe(name="fuel pin")
    universe.add_cells(
        [
            openmc.Cell(name="fuel", fill=fuel, region=-fuel_outer),
            openmc.Cell(
                name="cladding",
                fill=cladding,
                region=+fuel_outer & -clad_outer,
            ),
            openmc.Cell(name="moderator", fill=moderator, region=+clad_outer),
        ]
    )
    return universe


def _write_settings(directory, case, openmc):
    """Write settings.xml from the case's own declared statistics.

    Shared by every rung so a case cannot disagree with what it ran.
    """
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

    _write_settings(directory, case, openmc)


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


def build_pincell_uo2(directory: Path, case: VerificationCase) -> None:
    """Write an infinite lattice of light-water-reactor fuel pins.

    Periodic boundaries on the pin pitch make this an infinite lattice of
    identical pins, so the result isolates *radial* heterogeneity — resonance
    self-shielding inside the fuel and thermalisation in the moderator — from
    everything a real assembly adds. Rung 1 passing and this failing points at
    geometry or boundary conditions, not at the data library.

    Adapted from the OpenMC Crash Course by Harrison Reisinger (MIT).
    """
    import openmc

    fuel, cladding, moderator = _course_materials()
    openmc.Materials([fuel, cladding, moderator]).export_to_xml(
        directory / "materials.xml"
    )

    pin = _pin_universe(fuel, cladding, moderator)
    prism = openmc.model.RectangularPrism(
        width=PIN_PITCH_CM, height=PIN_PITCH_CM, boundary_type="periodic"
    )
    root = openmc.Universe(cells=[openmc.Cell(fill=pin, region=-prism)])
    openmc.Geometry(root).export_to_xml(directory / "geometry.xml")

    _write_settings(directory, case, openmc)


def build_assembly_17x17(directory: Path, case: VerificationCase) -> None:
    """Write a 17x17 fuel assembly with five water guide tubes.

    Adds lattice heterogeneity: the guide tubes are local moderator excesses
    that flatten flux nearby, so a lattice built with the wrong pitch or a
    misplaced tube shows up here while rung 2 stays green. Reflective outer
    boundaries make it an infinite array of identical assemblies.

    Guide tubes sit at the centre and inboard of the four corners, as in the
    course. Adapted from the OpenMC Crash Course by Harrison Reisinger (MIT).
    """
    import numpy as np
    import openmc

    fuel, cladding, moderator = _course_materials()
    openmc.Materials([fuel, cladding, moderator]).export_to_xml(
        directory / "materials.xml"
    )

    pin = _pin_universe(fuel, cladding, moderator)

    guide_tube = openmc.Universe(name="water guide tube")
    guide_tube.add_cells([openmc.Cell(fill=moderator)])

    size = ASSEMBLY_SIZE
    lattice = openmc.RectLattice()
    lattice.lower_left = (-PIN_PITCH_CM * size / 2, -PIN_PITCH_CM * size / 2)
    lattice.pitch = (PIN_PITCH_CM, PIN_PITCH_CM)

    universes = np.full((size, size), pin)
    centre = size // 2
    for row, col in (
        (centre, centre),
        (3, 3),
        (3, size - 4),
        (size - 4, 3),
        (size - 4, size - 4),
    ):
        universes[row, col] = guide_tube
    lattice.universes = universes

    width = PIN_PITCH_CM * size
    prism = openmc.model.RectangularPrism(
        width=width, height=width, boundary_type="reflective"
    )
    root = openmc.Universe(cells=[openmc.Cell(fill=lattice, region=-prism)])
    openmc.Geometry(root).export_to_xml(directory / "geometry.xml")

    _write_settings(directory, case, openmc)


register(
    VerificationCase(
        name="pincell_uo2",
        description=(
            "Infinite lattice of 5%-enriched UO2 pins in water, 1.26 cm pitch. "
            "Isolates radial heterogeneity — self-shielding and thermalisation "
            "— from lattice effects."
        ),
        reference_uri="reference://verification/pincell-uo2/k-eff",
        build=build_pincell_uo2,
        **_QUICK,
    )
)

register(
    VerificationCase(
        name="assembly_17x17",
        description=(
            "17x17 pin assembly with five water guide tubes, reflective outer "
            "boundary. Adds lattice heterogeneity on top of the pin cell."
        ),
        reference_uri="reference://verification/assembly-17x17/k-eff",
        build=build_assembly_17x17,
        **_ASSEMBLY,
    )
)
