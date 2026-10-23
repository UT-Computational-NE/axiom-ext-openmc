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
            "using the adapter's parser, including its refusal to parse HDF5 "
            "on the host."
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
                surfaces=("mcp", "skill_md"),
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
