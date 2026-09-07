# Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""The case registry — a graduated ladder of runnable problems.

A verification case is the unit of onboarding for a physics code: it builds that
code's input directory, and running it produces a real number. The ladder starts
at a problem whose answer is analytically defensible and climbs toward a full
core, so a new builder can be graded rather than merely reviewed.

The registry follows the same shape as the builder registries in the model
construction libraries — declare, register, look up by name — so there is one
idiom to learn rather than three.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axiom_ext_openmc.verification import cases


@pytest.fixture
def registry():
    return cases.CaseRegistry()


def _case(name: str = "toy", **overrides) -> cases.VerificationCase:
    defaults = dict(
        name=name,
        description="a toy case",
        reference_uri=f"reference://test/{name}/k-eff",
        build=lambda directory, case: None,
        n_particles=100,
        n_active_cycles=5,
        n_inactive_cycles=2,
    )
    defaults.update(overrides)
    return cases.VerificationCase(**defaults)


def test_a_registered_case_can_be_looked_up(registry):
    case = _case()
    registry.register(case)
    assert registry.get("toy") is case


def test_registering_the_same_name_twice_is_refused(registry):
    """Two cases under one name means one of them silently never runs."""
    registry.register(_case())
    with pytest.raises(ValueError, match="already registered"):
        registry.register(_case())


def test_unknown_case_raises_with_the_names_that_do_exist(registry):
    registry.register(_case("infinite_medium"))
    with pytest.raises(KeyError, match="infinite_medium"):
        registry.get("no_such_case")


def test_cases_are_listed_in_registration_order(registry):
    """The ladder is ordered — simplest first — and that order is meaningful."""
    for name in ("infinite_medium", "pincell", "assembly"):
        registry.register(_case(name))
    assert [c.name for c in registry.all()] == [
        "infinite_medium",
        "pincell",
        "assembly",
    ]


def test_a_case_declares_the_reference_it_should_be_graded_against(registry):
    case = _case()
    registry.register(case)
    assert registry.get("toy").reference_uri.startswith("reference://")


def test_build_receives_the_directory_and_the_case(tmp_path: Path):
    """Cases must not write beside their source file — the runner owns the
    directory so runs cannot collide. The builder is also handed the case, so
    the statistics it writes into settings.xml are the ones the case declares
    rather than a second copy that can drift."""
    seen: list[tuple] = []
    case = _case(build=lambda directory, case: seen.append((directory, case)))

    case.build(tmp_path, case)

    assert seen == [(tmp_path, case)]


def test_settings_are_positive(registry):
    """A case with zero particles reports a k-eff and means nothing."""
    with pytest.raises(ValueError, match="n_particles"):
        _case(n_particles=0)


def test_builtin_ladder_is_registered_and_ordered():
    """The shipped ladder is importable without OpenMC installed."""
    from axiom_ext_openmc.verification import builtin_cases  # noqa: F401

    names = [c.name for c in cases.default_registry().all()]
    assert names, "no built-in verification cases are registered"
    assert names[0] == "infinite_medium_uo2", (
        "the ladder must start at its simplest rung"
    )


def test_builtin_cases_declare_references():
    from axiom_ext_openmc.verification import builtin_cases  # noqa: F401

    for case in cases.default_registry().all():
        assert case.reference_uri.startswith("reference://"), case.name
        assert case.description, case.name
