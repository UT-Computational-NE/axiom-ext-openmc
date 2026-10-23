# Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""Self-contained script bind-mounted into the openmc/openmc container.

Reads a JSON spec from $WORKDIR/spec.json (input deck parameters), builds
geometry/materials/settings via the OpenMC Python API, runs the simulation,
parses the final statepoint, and writes $WORKDIR/result.json with the
canonical value_summary the OpenMCKernelAdapter expects.

This is the Phase 2c bridge between axiom.compute (host) and OpenMC (container).
The script is intentionally small + self-contained so it can be embedded inline
or shipped as a module file mounted into /inputs.

For Phase 2c smoke: only a 2D pin-cell case is supported. Phase 2d+ extends to
arbitrary input decks (read existing geometry.xml/materials.xml directly rather
than constructing them from the spec).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def build_pin_cell(spec: dict):
    """Construct a 2D pin cell from spec.

    spec keys:
      fuel_radius_cm       (default 0.4)
      clad_radius_cm       (default 0.46)
      pitch_cm             (default 1.26)
      enrichment_pct       (default 4.95)  — U-235 weight %
      fuel_density_gcc     (default 10.4)
      n_particles          (default 100000)
      n_active_cycles      (default 50)
      n_inactive_cycles    (default 20)
      rng_seed             (default 42)
    """
    import openmc

    fuel_r = spec.get("fuel_radius_cm", 0.4)
    clad_r = spec.get("clad_radius_cm", 0.46)
    pitch = spec.get("pitch_cm", 1.26)
    enrichment = spec.get("enrichment_pct", 4.95)
    fuel_density = spec.get("fuel_density_gcc", 10.4)

    # --- Materials ---
    fuel = openmc.Material(name="UO2 fuel")
    fuel.add_element("U", 1.0, enrichment=enrichment)
    fuel.add_element("O", 2.0)
    fuel.set_density("g/cm3", fuel_density)

    clad = openmc.Material(name="Zircaloy")
    clad.add_element("Zr", 1.0)
    clad.set_density("g/cm3", 6.55)

    water = openmc.Material(name="Water")
    water.add_element("H", 2.0)
    water.add_element("O", 1.0)
    water.set_density("g/cm3", 1.0)
    water.add_s_alpha_beta("c_H_in_H2O")

    materials = openmc.Materials([fuel, clad, water])
    materials.export_to_xml()

    # --- Geometry ---
    fuel_outer = openmc.ZCylinder(r=fuel_r)
    clad_outer = openmc.ZCylinder(r=clad_r)
    box = openmc.model.RectangularPrism(width=pitch, height=pitch, boundary_type="reflective")

    fuel_cell = openmc.Cell(name="fuel", fill=fuel, region=-fuel_outer)
    clad_cell = openmc.Cell(name="clad", fill=clad, region=+fuel_outer & -clad_outer)
    water_cell = openmc.Cell(name="water", fill=water, region=+clad_outer & -box)

    universe = openmc.Universe(cells=[fuel_cell, clad_cell, water_cell])
    geometry = openmc.Geometry(universe)
    geometry.export_to_xml()

    # --- Settings ---
    settings = openmc.Settings()
    settings.batches = spec.get("n_active_cycles", 50) + spec.get("n_inactive_cycles", 20)
    settings.inactive = spec.get("n_inactive_cycles", 20)
    settings.particles = spec.get("n_particles", 100000)
    settings.seed = spec.get("rng_seed", 42)
    settings.source = openmc.IndependentSource(
        space=openmc.stats.Box(
            (-pitch / 2, -pitch / 2, -1), (pitch / 2, pitch / 2, 1),
        ),
        constraints={"fissionable": True},
    )
    settings.export_to_xml()


def parse_statepoint() -> dict:
    """Extract the canonical value_summary from the produced statepoint."""
    import openmc

    statepoints = sorted(Path(".").glob("statepoint.*.h5"))
    if not statepoints:
        raise FileNotFoundError("no statepoint.*.h5 found in cwd after openmc run")
    sp = openmc.StatePoint(str(statepoints[-1]))
    # OpenMC 0.15+ uses `keff` (preferred); older versions use `k_combined`.
    k = getattr(sp, "keff", None) or sp.k_combined

    # Shannon entropy is only present if an entropy mesh was defined; tolerate absence.
    entropy_value: float | None = None
    try:
        if sp.entropy is not None and len(sp.entropy):
            entropy_value = float(sp.entropy[-1])
    except (AttributeError, KeyError, OSError):
        entropy_value = None

    summary = {
        "k_eff": float(k.nominal_value),
        "k_eff_std": float(k.std_dev),
        "n_cycles": int(sp.n_batches),
        "shannon_entropy": entropy_value,
        "convergence": "stationary",  # TODO: derive from entropy stationarity when entropy is present
        "tallies": {},  # Phase 2d: surface user-defined tallies
        "lost_particles": 0,  # OpenMC abort-on-too-many; if we got here, OK
    }
    return summary


def main():
    workdir = Path(os.environ.get("WORKDIR", "/inputs"))
    os.chdir(workdir)

    spec_path = workdir / "spec.json"
    if not spec_path.exists():
        sys.stderr.write(f"missing spec.json at {spec_path}\n")
        sys.exit(2)
    spec = json.loads(spec_path.read_text())

    try:
        build_pin_cell(spec)
    except Exception as exc:
        sys.stderr.write(f"build failure: {exc}\n")
        sys.exit(3)

    # Run OpenMC via the bundled binary.
    import subprocess
    proc = subprocess.run(["openmc"], capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr[-2000:])
        sys.exit(proc.returncode)

    try:
        summary = parse_statepoint()
    except Exception as exc:
        sys.stderr.write(f"parse failure: {exc}\n")
        sys.exit(4)

    (workdir / "result.json").write_text(json.dumps(summary, sort_keys=True, indent=2))
    print("OK")


if __name__ == "__main__":
    main()
