# Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""Read OpenMC XML inputs without importing OpenMC.

A deck can be rejected before a run on a machine that has no solver and no
nuclear data. The checks are the references visible in the XML: ids that
must exist, densities and units OpenMC accepts, particle and batch counts,
and a source where a run mode requires one. They are not a geometry proof
and they are not a k-eff.

``check_cross_sections`` is the same kind of check for
``OPENMC_CROSS_SECTIONS``: the index file and the data files it names, and,
when a model is supplied, the nuclide and S(a,b) names the model uses.
Element names are not matched. OpenMC expands those itself, and this module
does not invent the expansion.
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

__all__ = [
    "check_cross_sections",
    "summarize_model",
    "validate_model",
]

_DENSITY_UNITS = frozenset(
    {"g/cm3", "g/cc", "kg/m3", "atom/b-cm", "atom/cm3", "sum", "macro"}
)
_RUN_MODES = frozenset({"eigenvalue", "fixed source", "volume", "plot"})
_SOURCE_MODES = frozenset({"eigenvalue", "fixed source"})
_INPUTS = ("materials.xml", "geometry.xml", "settings.xml")
_HALFSPACE = re.compile(r"[+-]\d+")
_REGION_LEFTOVER = re.compile(r"[0-9A-Za-z_.]+")


def validate_model(
    input_dir: str | Path,
    *,
    use_openmc: bool = False,
) -> dict[str, Any]:
    """Check materials, geometry, settings, and tallies in ``input_dir``.

    ``ok`` is false when a structural error was found. ``use_openmc`` also
    asks the OpenMC package to parse the same directory. That package is
    optional: if it is not importable the result says so and does not
    substitute a second parser.
    """
    directory = Path(input_dir)
    loaded = _load(directory)
    errors = list(loaded["errors"])
    warnings = list(loaded["warnings"])
    checkers = ["xml"]
    if use_openmc:
        checkers.append("openmc")
        errors.extend(_openmc_model_errors(directory))
    return {
        "ok": not errors,
        "input_dir": str(directory),
        "files": loaded["files"],
        "errors": errors,
        "warnings": warnings,
        "checkers": checkers,
    }


def summarize_model(input_dir: str | Path) -> dict[str, Any]:
    """List cells, materials, surfaces, tallies, and the settings that were written.

    Counts and names come from the XML. A file that does not parse contributes
    an error and an empty section, not a guessed model.
    """
    directory = Path(input_dir)
    loaded = _load(directory)
    materials = loaded["materials"]
    cells = loaded["cells"]
    surfaces = loaded["surfaces"]
    tallies = loaded["tallies"]
    return {
        "input_dir": str(directory),
        "files": loaded["files"],
        "materials": materials,
        "cells": cells,
        "surfaces": surfaces,
        "lattices": loaded["lattices"],
        "tallies": tallies,
        "settings": loaded["settings"],
        "declared_cross_sections": loaded["declared_cross_sections"],
        "counts": {
            "materials": len(materials),
            "cells": len(cells),
            "surfaces": len(surfaces),
            "tallies": len(tallies),
        },
        "errors": loaded["errors"],
        "warnings": loaded["warnings"],
    }


def check_cross_sections(
    path: str | Path | None = None,
    model_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Report whether nuclear data is actually present.

    An explicit ``path`` wins, then ``OPENMC_CROSS_SECTIONS``, then a
    ``<cross_sections>`` element in the model's ``materials.xml``. A set
    variable that points nowhere is the result; it is not replaced by a
    later candidate. Nuclide and S(a,b) names are matched as written.
    """
    env_value = os.environ.get("OPENMC_CROSS_SECTIONS", "").strip() or None
    declared = _declared_only(model_dir) if model_dir is not None else None
    if path is not None and str(path).strip():
        source = "argument"
        chosen: str | None = str(path)
    elif env_value is not None:
        source = "environment"
        chosen = env_value
    elif declared is not None:
        source = "materials.xml"
        chosen = declared
    else:
        source = None
        chosen = None

    report: dict[str, Any] = {
        "ok": False,
        "environment": {
            "variable": "OPENMC_CROSS_SECTIONS",
            "value": env_value,
        },
        "materials_xml": declared,
        "selected": {"source": source, "path": chosen},
        "libraries": [],
        "missing_files": [],
        "nuclides_in_model": [],
        "sab_in_model": [],
        "elements_in_model": [],
        "nuclides_missing": [],
        "sab_missing": [],
        "errors": [],
    }
    if chosen is None:
        report["errors"].append(
            {
                "code": "cross_sections_unset",
                "message": (
                    "OPENMC_CROSS_SECTIONS is unset, no path was passed, and "
                    "materials.xml does not name a cross_sections file. "
                    "Download a library from https://openmc.org/data/ and "
                    "export OPENMC_CROSS_SECTIONS=/path/to/cross_sections.xml."
                ),
            }
        )
        return report

    index = Path(chosen)
    if not index.is_file():
        report["errors"].append(
            {
                "code": "cross_sections_missing",
                "message": f"cross-section index is not an existing file: {index}",
            }
        )
        return report

    try:
        root = ET.parse(index).getroot()
    except ET.ParseError as exc:
        report["errors"].append(
            {
                "code": "cross_sections_xml",
                "message": f"could not parse {index}: {exc}",
            }
        )
        return report
    if _local(root.tag) != "cross_sections":
        report["errors"].append(
            {
                "code": "cross_sections_root",
                "message": f"{index} root is <{_local(root.tag)}>, expected <cross_sections>",
            }
        )
        return report

    covered: set[str] = set()
    for node in root:
        if _local(node.tag) != "library":
            continue
        tokens = (node.attrib.get("materials") or "").split()
        covered.update(tokens)
        raw_path = (node.attrib.get("path") or "").strip()
        resolved = _resolve_library_path(index, raw_path) if raw_path else None
        exists = resolved is not None and resolved.is_file()
        report["libraries"].append(
            {
                "materials": tokens,
                "path": raw_path or None,
                "type": node.attrib.get("type"),
                "resolved_path": str(resolved) if resolved is not None else None,
                "exists": exists,
            }
        )
        if raw_path and not exists:
            report["missing_files"].append(str(resolved) if resolved is not None else raw_path)

    if not report["libraries"]:
        report["errors"].append(
            {
                "code": "cross_sections_empty",
                "message": f"{index} has no <library> entries",
            }
        )

    if model_dir is not None:
        summary = summarize_model(model_dir)
        nuclides = sorted(
            {
                nuc["name"]
                for mat in summary["materials"]
                for nuc in mat["nuclides"]
                if nuc.get("name")
            }
        )
        sab = sorted(
            {name for mat in summary["materials"] for name in mat["sab"] if name}
        )
        elements = sorted(
            {
                el["name"]
                for mat in summary["materials"]
                for el in mat["elements"]
                if el.get("name")
            }
        )
        report["nuclides_in_model"] = nuclides
        report["sab_in_model"] = sab
        report["elements_in_model"] = elements
        report["nuclides_missing"] = [name for name in nuclides if name not in covered]
        report["sab_missing"] = [name for name in sab if name not in covered]
        report["elements_note"] = (
            "Element names are listed and not matched. OpenMC expands an "
            "element to nuclides; this check does not."
        )

    if report["missing_files"]:
        report["errors"].append(
            {
                "code": "library_file_missing",
                "message": "a library entry points at a file that is not on disk",
            }
        )
    if report["nuclides_missing"] or report["sab_missing"]:
        report["errors"].append(
            {
                "code": "nuclide_not_in_library",
                "message": "a model nuclide or S(a,b) name is not in the index",
            }
        )
    report["ok"] = not report["errors"]
    return report


def _declared_only(model_dir: str | Path | None) -> str | None:
    if model_dir is None:
        return None
    path = Path(model_dir)
    materials = path / "materials.xml" if path.is_dir() else None
    if materials is None or not materials.is_file():
        return None
    try:
        root = ET.parse(materials).getroot()
    except ET.ParseError:
        return None
    for node in root:
        if _local(node.tag) == "cross_sections" and (node.text or "").strip():
            return node.text.strip()
    return None


def _resolve_library_path(index: Path, raw: str) -> Path:
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate
    return index.parent / candidate


def _openmc_model_errors(directory: Path) -> list[dict[str, str]]:
    try:
        import openmc
    except ImportError:
        return [
            {
                "code": "openmc_unavailable",
                "message": (
                    "use_openmc=True but the openmc package is not importable. "
                    "Install it with conda install -c conda-forge openmc. "
                    "The XML check above does not require it."
                ),
            }
        ]
    try:
        openmc.Model.from_xml(directory)
    except Exception as exc:
        return [{"code": "openmc_model", "message": f"{type(exc).__name__}: {exc}"}]
    return []


def _load(directory: Path) -> dict[str, Any]:
    files = {name: (directory / name).is_file() for name in (*_INPUTS, "tallies.xml")}
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    empty: dict[str, Any] = {
        "files": files,
        "errors": errors,
        "warnings": warnings,
        "materials": [],
        "cells": [],
        "surfaces": [],
        "lattices": [],
        "tallies": [],
        "settings": _empty_settings(),
        "declared_cross_sections": None,
    }
    if not directory.is_dir():
        errors.append(
            {
                "code": "not_a_directory",
                "message": f"input directory does not exist: {directory}",
            }
        )
        return empty

    materials_root = _parse_root(directory / "materials.xml", "materials", errors)
    geometry_root = _parse_root(directory / "geometry.xml", "geometry", errors)
    settings_root = _parse_root(directory / "settings.xml", "settings", errors)
    tallies_root = None
    if files["tallies.xml"]:
        tallies_root = _parse_root(directory / "tallies.xml", "tallies", errors)

    materials, declared = _materials(materials_root, errors)
    cells, surfaces, lattices = _geometry(geometry_root, errors, warnings)
    _link_geometry(materials, cells, surfaces, lattices, errors, warnings)
    settings = _settings(settings_root, errors)
    tallies = _tallies(tallies_root, errors)
    empty["materials"] = materials
    empty["cells"] = cells
    empty["surfaces"] = surfaces
    empty["lattices"] = lattices
    empty["tallies"] = tallies
    empty["settings"] = settings
    empty["declared_cross_sections"] = declared
    return empty


def _parse_root(
    path: Path,
    expected: str,
    errors: list[dict[str, str]],
) -> ET.Element | None:
    if not path.is_file():
        if expected != "tallies":
            errors.append(
                {
                    "code": "missing_file",
                    "message": f"missing {path.name}",
                    "file": path.name,
                }
            )
        return None
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        errors.append(
            {
                "code": "xml_parse",
                "message": f"{path.name}: {exc}",
                "file": path.name,
            }
        )
        return None
    if _local(root.tag) != expected:
        errors.append(
            {
                "code": "wrong_root",
                "message": f"{path.name} root is <{_local(root.tag)}>, expected <{expected}>",
                "file": path.name,
            }
        )
        return None
    return root


def _materials(
    root: ET.Element | None,
    errors: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], str | None]:
    if root is None:
        return [], None
    materials: list[dict[str, Any]] = []
    declared = None
    seen: set[int] = set()
    for node in root:
        tag = _local(node.tag)
        if tag == "cross_sections" and (node.text or "").strip():
            declared = node.text.strip()
            continue
        if tag != "material":
            continue
        ident = _int_attr(node, "id")
        if ident is None:
            errors.append(
                {
                    "code": "missing_id",
                    "message": "a <material> has no integer id",
                    "file": "materials.xml",
                }
            )
            continue
        if ident in seen:
            errors.append(
                {
                    "code": "duplicate_id",
                    "message": f"duplicate material id {ident}",
                    "file": "materials.xml",
                }
            )
        seen.add(ident)
        density_node = next((c for c in node if _local(c.tag) == "density"), None)
        density = None
        units = None
        if density_node is None:
            errors.append(
                {
                    "code": "missing_density",
                    "message": f"material {ident} has no <density>",
                    "file": "materials.xml",
                }
            )
        else:
            units = density_node.attrib.get("units")
            density = _float_attr(density_node, "value")
            if density is None or density <= 0:
                errors.append(
                    {
                        "code": "bad_density",
                        "message": f"material {ident} density must be a number greater than 0",
                        "file": "materials.xml",
                    }
                )
            if units not in _DENSITY_UNITS:
                errors.append(
                    {
                        "code": "bad_units",
                        "message": (
                            f"material {ident} density units {units!r} are not one of "
                            + ", ".join(sorted(_DENSITY_UNITS))
                        ),
                        "file": "materials.xml",
                    }
                )
        nuclides = [_composition(c) for c in node if _local(c.tag) == "nuclide"]
        elements = [_composition(c) for c in node if _local(c.tag) == "element"]
        sab = [
            (c.attrib.get("name") or "").strip()
            for c in node
            if _local(c.tag) == "sab" and (c.attrib.get("name") or "").strip()
        ]
        if not nuclides and not elements:
            errors.append(
                {
                    "code": "empty_composition",
                    "message": f"material {ident} has no <nuclide> or <element>",
                    "file": "materials.xml",
                }
            )
        for entry in (*nuclides, *elements):
            if not entry["name"]:
                errors.append(
                    {
                        "code": "missing_nuclide_name",
                        "message": f"material {ident} has a composition entry with no name",
                        "file": "materials.xml",
                    }
                )
            if entry["ao"] is None and entry["wo"] is None:
                errors.append(
                    {
                        "code": "missing_fraction",
                        "message": f"material {ident} entry {entry['name'] or '(unnamed)'} needs ao or wo",
                        "file": "materials.xml",
                    }
                )
        materials.append(
            {
                "id": ident,
                "name": node.attrib.get("name"),
                "depletable": node.attrib.get("depletable", "").lower() == "true",
                "density": density,
                "density_units": units,
                "nuclides": nuclides,
                "elements": elements,
                "sab": sab,
            }
        )
    return materials, declared


def _composition(node: ET.Element) -> dict[str, Any]:
    return {
        "name": (node.attrib.get("name") or "").strip(),
        "ao": _float_attr(node, "ao"),
        "wo": _float_attr(node, "wo"),
    }


def _geometry(
    root: ET.Element | None,
    errors: list[dict[str, str]],
    warnings: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    if root is None:
        return [], [], []
    cells: list[dict[str, Any]] = []
    surfaces: list[dict[str, Any]] = []
    lattices: list[dict[str, Any]] = []
    seen_cells: set[int] = set()
    seen_surfaces: set[int] = set()
    for node in root:
        tag = _local(node.tag)
        if tag == "cell":
            ident = _int_attr(node, "id")
            if ident is None:
                errors.append(
                    {
                        "code": "missing_id",
                        "message": "a <cell> has no integer id",
                        "file": "geometry.xml",
                    }
                )
                continue
            if ident in seen_cells:
                errors.append(
                    {
                        "code": "duplicate_id",
                        "message": f"duplicate cell id {ident}",
                        "file": "geometry.xml",
                    }
                )
            seen_cells.add(ident)
            material = node.attrib.get("material")
            fill = node.attrib.get("fill")
            if material is None and fill is None:
                errors.append(
                    {
                        "code": "missing_material_or_fill",
                        "message": f"cell {ident} needs a material or a fill",
                        "file": "geometry.xml",
                    }
                )
            if material is not None and fill is not None:
                errors.append(
                    {
                        "code": "material_and_fill",
                        "message": f"cell {ident} sets both material and fill",
                        "file": "geometry.xml",
                    }
                )
            region = node.attrib.get("region")
            if region is not None:
                _warn_unparsed_region(region, ident, warnings)
            cells.append(
                {
                    "id": ident,
                    "name": node.attrib.get("name"),
                    "material": material,
                    "fill": fill,
                    "region": region,
                    "universe": node.attrib.get("universe"),
                }
            )
        elif tag == "surface":
            ident = _int_attr(node, "id")
            if ident is None:
                errors.append(
                    {
                        "code": "missing_id",
                        "message": "a <surface> has no integer id",
                        "file": "geometry.xml",
                    }
                )
                continue
            if ident in seen_surfaces:
                errors.append(
                    {
                        "code": "duplicate_id",
                        "message": f"duplicate surface id {ident}",
                        "file": "geometry.xml",
                    }
                )
            seen_surfaces.add(ident)
            kind = node.attrib.get("type")
            if not kind:
                errors.append(
                    {
                        "code": "missing_surface_type",
                        "message": f"surface {ident} has no type",
                        "file": "geometry.xml",
                    }
                )
            surfaces.append(
                {
                    "id": ident,
                    "name": node.attrib.get("name"),
                    "type": kind,
                    "boundary": node.attrib.get("boundary"),
                }
            )
        elif tag == "lattice":
            ident = _int_attr(node, "id")
            if ident is None:
                errors.append(
                    {
                        "code": "missing_id",
                        "message": "a <lattice> has no integer id",
                        "file": "geometry.xml",
                    }
                )
                continue
            lattices.append({"id": ident, "name": node.attrib.get("name")})
    if not cells:
        errors.append(
            {
                "code": "no_cells",
                "message": "geometry.xml has no <cell>",
                "file": "geometry.xml",
            }
        )
    return cells, surfaces, lattices


def _link_geometry(
    materials: list[dict[str, Any]],
    cells: list[dict[str, Any]],
    surfaces: list[dict[str, Any]],
    lattices: list[dict[str, Any]],
    errors: list[dict[str, str]],
    warnings: list[dict[str, str]],
) -> None:
    material_ids = {item["id"] for item in materials}
    surface_ids = {item["id"] for item in surfaces}
    universes = {item["id"] for item in lattices}
    for cell in cells:
        raw = cell.get("universe")
        if raw is None:
            universes.add(0)
            continue
        parsed = _int_text(raw)
        if parsed is None:
            warnings.append(
                {
                    "code": "bad_universe",
                    "message": f"cell {cell['id']} universe {raw!r} is not an integer",
                    "file": "geometry.xml",
                }
            )
        else:
            universes.add(parsed)
    for cell in cells:
        material = cell.get("material")
        if material is not None and material != "void":
            parsed = _int_text(material)
            if parsed is None or parsed not in material_ids:
                errors.append(
                    {
                        "code": "unknown_material",
                        "message": f"cell {cell['id']} material {material!r} is not a material id or void",
                        "file": "geometry.xml",
                    }
                )
        fill = cell.get("fill")
        if fill is not None:
            parsed = _int_text(fill)
            if parsed is None:
                errors.append(
                    {
                        "code": "bad_fill",
                        "message": f"cell {cell['id']} fill {fill!r} is not an integer universe id",
                        "file": "geometry.xml",
                    }
                )
            elif parsed not in universes:
                errors.append(
                    {
                        "code": "unknown_fill",
                        "message": f"cell {cell['id']} fill {parsed} matches no cell universe or lattice id",
                        "file": "geometry.xml",
                    }
                )
        region = cell.get("region") or ""
        for token in _HALFSPACE.findall(region):
            sid = int(token[1:])
            if sid not in surface_ids:
                errors.append(
                    {
                        "code": "unknown_surface",
                        "message": f"cell {cell['id']} region references surface {sid}, which is not defined",
                        "file": "geometry.xml",
                    }
                )


def _warn_unparsed_region(
    region: str,
    cell_id: int,
    warnings: list[dict[str, str]],
) -> None:
    stripped = _HALFSPACE.sub(" ", region)
    for char in "()|~&":
        stripped = stripped.replace(char, " ")
    leftover = _REGION_LEFTOVER.findall(stripped)
    if leftover:
        warnings.append(
            {
                "code": "unparsed_region",
                "message": f"cell {cell_id} region has tokens that were not read as halfspaces: {' '.join(leftover)}",
                "file": "geometry.xml",
            }
        )


def _settings(root: ET.Element | None, errors: list[dict[str, str]]) -> dict[str, Any]:
    settings = _empty_settings()
    if root is None:
        return settings
    settings["run_mode"] = _child_text(root, "run_mode")
    settings["particles"] = _child_int(root, "particles")
    settings["batches"] = _child_int(root, "batches")
    settings["inactive"] = _child_int(root, "inactive")
    settings["generations_per_batch"] = _child_int(root, "generations_per_batch")
    settings["seed"] = _child_int(root, "seed")
    settings["source"] = any(_local(node.tag) == "source" for node in root)
    mode = settings["run_mode"]
    if mode is not None and mode not in _RUN_MODES:
        errors.append(
            {
                "code": "bad_run_mode",
                "message": f"run_mode {mode!r} is not one of {', '.join(sorted(_RUN_MODES))}",
                "file": "settings.xml",
            }
        )
    if mode in _SOURCE_MODES or mode is None:
        _require_positive(settings["particles"], "particles", errors)
        _require_positive(settings["batches"], "batches", errors)
        inactive = settings["inactive"]
        batches = settings["batches"]
        if inactive is not None and inactive < 0:
            errors.append(
                {
                    "code": "bad_inactive",
                    "message": "inactive batch count must be zero or greater",
                    "file": "settings.xml",
                }
            )
        if inactive is not None and batches is not None and inactive >= batches:
            errors.append(
                {
                    "code": "bad_inactive",
                    "message": "inactive batch count must be less than batches",
                    "file": "settings.xml",
                }
            )
        generations = settings["generations_per_batch"]
        if generations is not None and generations < 1:
            errors.append(
                {
                    "code": "bad_generations",
                    "message": "generations_per_batch must be at least 1",
                    "file": "settings.xml",
                }
            )
        if not settings["source"] and (mode in _SOURCE_MODES or mode is None):
            errors.append(
                {
                    "code": "missing_source",
                    "message": "settings.xml has no <source>. eigenvalue and fixed source runs require one.",
                    "file": "settings.xml",
                }
            )
    return settings


def _require_positive(value: int | None, name: str, errors: list[dict[str, str]]) -> None:
    if value is None or value <= 0:
        errors.append(
            {
                "code": f"bad_{name}",
                "message": f"{name} must be a positive integer",
                "file": "settings.xml",
            }
        )


def _tallies(root: ET.Element | None, errors: list[dict[str, str]]) -> list[dict[str, Any]]:
    if root is None:
        return []
    tallies: list[dict[str, Any]] = []
    seen: set[int] = set()
    for node in root:
        if _local(node.tag) != "tally":
            continue
        ident = _int_attr(node, "id")
        if ident is None:
            errors.append(
                {
                    "code": "missing_id",
                    "message": "a <tally> has no integer id",
                    "file": "tallies.xml",
                }
            )
            continue
        if ident in seen:
            errors.append(
                {
                    "code": "duplicate_id",
                    "message": f"duplicate tally id {ident}",
                    "file": "tallies.xml",
                }
            )
        seen.add(ident)
        scores = _score_names(node)
        if not scores:
            errors.append(
                {
                    "code": "tally_missing_scores",
                    "message": f"tally {ident} has no scores",
                    "file": "tallies.xml",
                }
            )
        nuclides: list[str] = []
        for child in node:
            if _local(child.tag) == "nuclides" and (child.text or "").strip():
                nuclides.extend(child.text.split())
        filters = []
        for child in node:
            if _local(child.tag) == "filter":
                filters.append(
                    {"type": child.attrib.get("type"), "bins": child.attrib.get("bins")}
                )
            if _local(child.tag) == "filters":
                for filt in child:
                    if _local(filt.tag) == "filter":
                        filters.append(
                            {
                                "type": filt.attrib.get("type"),
                                "bins": filt.attrib.get("bins"),
                            }
                        )
        tallies.append(
            {
                "id": ident,
                "name": node.attrib.get("name"),
                "scores": scores,
                "nuclides": nuclides,
                "filters": filters,
            }
        )
    return tallies


def _score_names(node: ET.Element) -> list[str]:
    names: list[str] = []
    for child in node:
        tag = _local(child.tag)
        if tag == "scores" and (child.text or "").strip():
            names.extend(child.text.split())
        elif tag == "score" and (child.text or "").strip():
            names.extend(child.text.split())
    return names


def _empty_settings() -> dict[str, Any]:
    return {
        "run_mode": None,
        "particles": None,
        "batches": None,
        "inactive": None,
        "generations_per_batch": None,
        "seed": None,
        "source": False,
    }


def _child_text(root: ET.Element, tag: str) -> str | None:
    for node in root:
        if _local(node.tag) == tag and (node.text or "").strip():
            return node.text.strip()
    return None


def _child_int(root: ET.Element, tag: str) -> int | None:
    text = _child_text(root, tag)
    if text is None:
        return None
    return _int_text(text)


def _int_attr(node: ET.Element, name: str) -> int | None:
    return _int_text(node.attrib.get(name))


def _float_attr(node: ET.Element, name: str) -> float | None:
    raw = node.attrib.get(name)
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _int_text(raw: str | None) -> int | None:
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
