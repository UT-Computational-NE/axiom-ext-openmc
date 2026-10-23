# Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""The toolkit is a thin projection of the library, and it matches the manifest."""

from __future__ import annotations

import tomllib
from pathlib import Path

from axiom.infra.skills import SkillRegistry, SkillResult

from axiom_ext_openmc.skills import DECLARATIONS, bind

_ROOT = Path(__file__).resolve().parents[2]


def _manifest_skills() -> list[dict]:
    manifest = tomllib.loads((_ROOT / "axiom-extension.toml").read_text())
    return [block for block in manifest["extension"]["provides"] if block.get("kind") == "skill"]


def _norm_requires(items):
    out = []
    for item in items or []:
        out.append(
            {
                "id": item["id"],
                "description": item["description"],
                "fix": item["fix"],
                "consumes": item.get("consumes", ""),
                "param": item.get("param", ""),
            }
        )
    return out


def _norm_produces(items):
    return [
        {
            "kind": item["kind"],
            "how_to_use": item["how_to_use"],
            "field": item.get("field", ""),
        }
        for item in items or []
    ]


def _norm_steps(items):
    return [
        {
            "target": item["target"],
            "when": item.get("when", "ok"),
            "why": item["why"],
            "feeds": dict(item.get("feeds") or {}),
        }
        for item in items or []
    ]


def test_manifest_skills_match_the_declarations():
    """The TOML tables and the SkillSpec source are one declaration written twice."""
    declared = {item["name"]: item for item in DECLARATIONS}
    found = {block["name"]: block for block in _manifest_skills()}
    assert set(declared) == set(found)
    for name, item in declared.items():
        block = found[name]
        assert block["description"] == item["description"]
        assert block["entry"] == f"axiom_ext_openmc.skills.impl:{item['fn'].__name__}"
        assert block["risk"] == item["risk"]
        assert block["side_effects"] is item["side_effects"]
        assert block["idempotent"] is item["idempotent"]
        assert block["open_world"] is item["open_world"]
        assert block.get("recipes", []) == item["recipes"]
        assert _norm_requires(block.get("requires")) == _norm_requires(item["requires"])
        assert _norm_produces(block.get("produces")) == _norm_produces(item["produces"])
        assert _norm_steps(block.get("next_steps")) == _norm_steps(item["next_steps"])


def test_bind_registers_each_skill_once():
    registry = SkillRegistry()
    names = bind(registry)
    assert names == [item["name"] for item in DECLARATIONS]
    assert bind(registry) == names
    assert registry.list("openmc") == sorted(names)


def test_check_runner_and_list_cases_return_skill_results():
    registry = SkillRegistry()
    bind(registry)
    checked = registry.invoke("openmc.check_runner", {}, _ctx(registry))
    listed = registry.invoke("openmc.list_cases", {}, _ctx(registry))
    assert isinstance(checked, SkillResult) and checked.ok
    assert "can_run_openmc" in checked.value
    assert isinstance(listed, SkillResult) and listed.ok
    assert listed.value["count"] == 3


def test_grade_skill_refuses_a_provisional_reference():
    registry = SkillRegistry()
    bind(registry)
    result = registry.invoke(
        "openmc.grade",
        {
            "reference_uri": "reference://ornl-tm-0728/msr-N_1/k-eff",
            "k_eff": 1.00120,
        },
        _ctx(registry),
    )
    assert result.ok
    assert result.value["status"] == "provisional"
    assert result.value["agrees"] is None


def test_grade_skill_rejects_a_bad_uri():
    registry = SkillRegistry()
    bind(registry)
    result = registry.invoke(
        "openmc.grade",
        {"reference_uri": "k-eff", "k_eff": 1.0},
        _ctx(registry),
    )
    assert result.ok is False
    assert result.errors


def test_run_input_demands_the_case_counts():
    registry = SkillRegistry()
    bind(registry)
    result = registry.invoke(
        "openmc.run_input",
        {"input_dir": "/tmp"},
        _ctx(registry),
    )
    assert result.ok is False
    assert "n_particles" in result.errors[0]


def _ctx(registry):
    from axiom.infra.skills import SkillContext

    return SkillContext(registry=registry, state_dir=Path("/tmp"), logger=_Silent())


class _Silent:
    def exception(self, *args, **kwargs):
        return None

    def info(self, *args, **kwargs):
        return None

    def warning(self, *args, **kwargs):
        return None

    def debug(self, *args, **kwargs):
        return None
