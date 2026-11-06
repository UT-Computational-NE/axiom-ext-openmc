# Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""Register the OpenMC toolkit with a ``SkillRegistry``.

The manifest tables and the ``SkillSpec`` objects are built from the same
declarations so a reader of ``axiom-extension.toml`` and a caller of
:func:`bind` cannot drift. If ``axiom.infra.skills`` cannot be imported, this
says so and registers nothing. It does not invent a second registry.
"""

from __future__ import annotations

import logging
from typing import Any

from axiom_ext_openmc.skills import impl

logger = logging.getLogger(__name__)

__all__ = ["DECLARATIONS", "bind", "register"]

_INPUT_FIX = (
    "pass input_dir pointing at a directory that contains geometry.xml, "
    "materials.xml, and settings.xml, or a spec.json for the container runner"
)

#: Static projection of each skill. ``bind`` turns these into ``SkillSpec``s.
#: The manifest repeats them; ``tests/unit_tests/test_toolkit.py`` fails if
#: the two copies disagree.
DECLARATIONS: list[dict[str, Any]] = [
    {
        "name": "openmc.check_runner",
        "fn": impl.check_runner,
        "description": (
            "Report whether this machine can run OpenMC: the Python package, "
            "the nuclear-data file, the openmc binary, and Docker, as separate facts."
        ),
        "risk": "read",
        "side_effects": False,
        "idempotent": True,
        "open_world": False,
        "requires": [],
        "produces": [],
        "next_steps": [
            {
                "target": "openmc.list_cases",
                "when": "ok",
                "why": "See which verification cases exist before choosing one to run.",
            }
        ],
        "recipes": ["grade-a-run"],
        "inputs": {},
    },
    {
        "name": "openmc.list_cases",
        "fn": impl.list_cases,
        "description": (
            "List the verification ladder in order, including each case's "
            "reference URI and the particle and cycle counts the case declares."
        ),
        "risk": "read",
        "side_effects": False,
        "idempotent": True,
        "open_world": False,
        "requires": [],
        "produces": [
            {
                "kind": "reference_uri",
                "how_to_use": "pass as reference_uri to openmc.grade",
                "field": "cases",
            }
        ],
        "next_steps": [
            {
                "target": "openmc.run_input",
                "when": "ok",
                "why": "Run one case's input directory with the counts the case declares.",
            }
        ],
        "recipes": ["grade-a-run"],
        "inputs": {},
    },
    {
        "name": "openmc.parse_summary",
        "fn": impl.parse_summary,
        "description": (
            "Read the canonical value summary from an OpenMC output directory "
            "using the adapter's parser. result.json wins when present; "
            "otherwise the shared statepoint reader supplies k-eff and tally tables."
        ),
        "risk": "read",
        "side_effects": False,
        "idempotent": True,
        "open_world": False,
        "requires": [
            {
                "id": "input-dir",
                "description": "The output directory must exist.",
                "fix": _INPUT_FIX,
            }
        ],
        "produces": [
            {
                "kind": "k_eff",
                "how_to_use": "pass as k_eff to openmc.grade",
                "field": "k_eff",
            }
        ],
        "next_steps": [
            {
                "target": "openmc.grade",
                "when": "produced:k_eff",
                "why": "Grade a summary that was parsed rather than freshly run.",
                "feeds": {"k_eff": "k_eff"},
            }
        ],
        "recipes": [],
        "inputs": {"input_dir": "str"},
    },
    {
        "name": "openmc.run_input",
        "fn": impl.run_input,
        "description": (
            "Run one existing OpenMC input directory through the production "
            "adapter. Does not author geometry. Particle and cycle counts are "
            "the caller's, copied from the case, not a second default."
        ),
        "risk": "reversible-write",
        "side_effects": True,
        "idempotent": False,
        "open_world": True,
        "requires": [
            {
                "id": "input-dir",
                "description": "An OpenMC input directory must already exist.",
                "fix": _INPUT_FIX,
            }
        ],
        "produces": [
            {
                "kind": "k_eff",
                "how_to_use": "pass as k_eff to openmc.grade",
                "field": "k_eff",
            }
        ],
        "next_steps": [
            {
                "target": "openmc.grade",
                "when": "produced:k_eff",
                "why": (
                    "Grade the multiplication factor. A provisional reference "
                    "is reported as provisional and is not an agreement."
                ),
                "feeds": {"k_eff": "k_eff"},
            }
        ],
        "recipes": ["grade-a-run"],
        "inputs": {
            "input_dir": "str",
            "n_particles": "int",
            "n_active_cycles": "int",
            "n_inactive_cycles": "int",
            "rng_seed": "int",
            "kernel_options": "dict",
            "xs_library": "str",
        },
    },
    {
        "name": "openmc.grade",
        "fn": impl.grade,
        "description": (
            "Compare a computed k-eff to a declared reference. A missing "
            "reference is no_reference. A provisional reference is not compared "
            "and does not report agreement."
        ),
        "risk": "read",
        "side_effects": False,
        "idempotent": True,
        "open_world": False,
        "requires": [
            {
                "id": "k-eff",
                "description": "A computed multiplication factor.",
                "fix": "Call openmc.run_input or openmc.parse_summary and pass its k_eff.",
                "consumes": "k_eff",
                "param": "k_eff",
            },
            {
                "id": "reference-uri",
                "description": "The reference:// URI the case declares.",
                "fix": (
                    "Pass reference_uri from openmc.list_cases "
                    "(each case's reference_uri)."
                ),
            },
        ],
        "produces": [],
        "next_steps": [],
        "recipes": ["grade-a-run"],
        "inputs": {"reference_uri": "str", "k_eff": "float", "k_eff_std": "float"},
    },
    {
        "name": "openmc.validate",
        "fn": impl.validate,
        "description": (
            "Check an OpenMC input directory's materials, geometry, settings, "
            "and tallies before a run. Structural references only; it does not "
            "start a solve and it does not report a k-eff."
        ),
        "risk": "read",
        "side_effects": False,
        "idempotent": True,
        "open_world": False,
        "requires": [
            {
                "id": "model-dir",
                "description": "An OpenMC input directory must already exist.",
                "fix": (
                    "Pass input_dir pointing at a directory that contains "
                    "materials.xml, geometry.xml, and settings.xml."
                ),
            }
        ],
        "produces": [],
        "next_steps": [
            {
                "target": "openmc.show",
                "when": "ok",
                "why": "Summarize the cells, materials, tallies, and batch settings that validated.",
            }
        ],
        "recipes": [],
        "inputs": {"input_dir": "str", "use_openmc": "bool"},
        "surfaces": ["cli", "mcp", "skill_md"],
    },
    {
        "name": "openmc.show",
        "fn": impl.show,
        "description": (
            "Summarize an OpenMC model: cells, materials, surfaces, tallies, "
            "and the particle and batch settings written in settings.xml."
        ),
        "risk": "read",
        "side_effects": False,
        "idempotent": True,
        "open_world": False,
        "requires": [
            {
                "id": "model-dir",
                "description": "An OpenMC input directory must already exist.",
                "fix": (
                    "Pass input_dir pointing at a directory that contains "
                    "materials.xml, geometry.xml, and settings.xml."
                ),
            }
        ],
        "produces": [],
        "next_steps": [
            {
                "target": "openmc.review",
                "when": "ok",
                "why": "Build a dry-run plan from the summary. The plan does not start OpenMC.",
            }
        ],
        "recipes": [],
        "inputs": {"input_dir": "str"},
        "surfaces": ["cli", "mcp", "skill_md"],
    },
    {
        "name": "openmc.stat",
        "fn": impl.stat,
        "description": (
            "Read an OpenMC statepoint. k-eff and its standard deviation come "
            "from the k_combined dataset. Tally means and standard deviations "
            "are the sum and sum-of-squares reduction OpenMC stores."
        ),
        "risk": "read",
        "side_effects": False,
        "idempotent": True,
        "open_world": False,
        "requires": [
            {
                "id": "statepoint",
                "description": "A statepoint file, or a directory containing statepoint.*.h5.",
                "fix": "Pass path to statepoint.<batch>.h5 or to the directory OpenMC wrote.",
            }
        ],
        "produces": [
            {
                "kind": "k_eff",
                "how_to_use": "pass as k_eff to openmc.grade",
                "field": "k_eff",
            }
        ],
        "next_steps": [
            {
                "target": "openmc.grade",
                "when": "produced:k_eff",
                "why": "Grade the k-eff that was read from the statepoint.",
                "feeds": {"k_eff": "k_eff"},
            }
        ],
        "recipes": [],
        "inputs": {"path": "str"},
        "surfaces": ["cli", "mcp", "skill_md"],
    },
    {
        "name": "openmc.diff",
        "fn": impl.diff,
        "description": (
            "Compare two OpenMC statepoints. delta is the left reported value "
            "minus the right. The tolerance is the root-sum-square of the two "
            "reported standard deviations, not a published reference."
        ),
        "risk": "read",
        "side_effects": False,
        "idempotent": True,
        "open_world": False,
        "requires": [
            {
                "id": "two-statepoints",
                "description": "Two statepoint paths.",
                "fix": "Pass left and right, each a statepoint file or a directory containing one.",
            }
        ],
        "produces": [],
        "next_steps": [],
        "recipes": [],
        "inputs": {"left": "str", "right": "str"},
        "surfaces": ["cli", "mcp", "skill_md"],
    },
    {
        "name": "openmc.check",
        "fn": impl.check,
        "description": (
            "Check cross-section data: OPENMC_CROSS_SECTIONS or a path, the "
            "files the index names, and, when a model directory is given, the "
            "nuclide and S(a,b) names that model uses."
        ),
        "risk": "read",
        "side_effects": False,
        "idempotent": True,
        "open_world": False,
        "requires": [],
        "produces": [],
        "next_steps": [],
        "recipes": [],
        "inputs": {"path": "str", "model_dir": "str"},
        "surfaces": ["cli", "mcp", "skill_md"],
    },
    {
        "name": "openmc.review",
        "fn": impl.review,
        "description": (
            "Dry-run plan for an OpenMC directory: validation, model summary, "
            "cross-section check, and the runner connect would select. "
            "executed is false. OpenMC is not started."
        ),
        "risk": "read",
        "side_effects": False,
        "idempotent": True,
        "open_world": False,
        "requires": [
            {
                "id": "model-dir",
                "description": "An OpenMC input directory must already exist.",
                "fix": (
                    "Pass input_dir pointing at a directory that contains "
                    "materials.xml, geometry.xml, and settings.xml."
                ),
            }
        ],
        "produces": [],
        "next_steps": [],
        "recipes": [],
        "inputs": {"input_dir": "str", "runner": "str"},
        "surfaces": ["cli", "mcp", "skill_md"],
    },
]


def bind(registry: Any) -> list[str]:
    """Register every toolkit skill on ``registry``. Return the names registered.

    When ``axiom.infra.skills`` is missing, log the reason and return an empty
    list. The library remains usable without the toolkit registry.
    """
    try:
        from axiom.infra.skill_declarations import NextStep, Precondition, Ref
        from axiom.infra.skills import SkillSpec
    except ImportError:
        logger.error(
            "axiom.infra.skills is not importable; OpenMC toolkit skills were "
            "not registered. Install axiom-os-lm. axiom_ext_openmc.library "
            "does not need it."
        )
        return []

    names: list[str] = []
    for item in DECLARATIONS:
        if registry.has(item["name"]):
            names.append(item["name"])
            continue
        requires = tuple(
            Precondition(
                id=req["id"],
                description=req["description"],
                fix=req["fix"],
                consumes=req.get("consumes", ""),
                param=req.get("param", ""),
            )
            for req in item["requires"]
        )
        produces = tuple(
            Ref(kind=ref["kind"], how_to_use=ref["how_to_use"], field=ref.get("field", ""))
            for ref in item["produces"]
        )
        steps = tuple(
            NextStep(
                target=step["target"],
                when=step.get("when", "ok"),
                why=step["why"],
                feeds=dict(step.get("feeds") or {}),
            )
            for step in item["next_steps"]
        )
        registry.register_skill(
            SkillSpec(
                name=item["name"],
                fn=item["fn"],
                description=item["description"],
                inputs=dict(item["inputs"]),
                side_effects=item["side_effects"],
                idempotent=item["idempotent"],
                open_world=item["open_world"],
                surfaces=tuple(item.get("surfaces", ("mcp", "skill_md"))),
                risk=item["risk"],
                requires=requires,
                produces=produces,
                next_steps=steps,
                recipes=tuple(item["recipes"]),
            ),
            mutating=item["side_effects"] is True,
        )
        names.append(item["name"])
    return names


register = bind
