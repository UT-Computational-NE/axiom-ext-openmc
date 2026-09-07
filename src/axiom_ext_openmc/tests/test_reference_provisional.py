# Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""Provisional references must never reach a verification registry.

Verification axis A3 asks "does the computed value agree with the published
reference?". Both reference modules seed placeholder values so consumers can
wire against canonical URIs before domain reviewers extract the real numbers.
Installed silently, those placeholders make A3 report agreement against a value
nobody published — a green result manufactured out of a `# placeholder`
comment. A missing reference is visible; a fabricated agreement is not.

These tests pin the fail-closed behaviour: by default, nothing provisional is
installed, and the caller has to ask for it in so many words.
"""

from __future__ import annotations

import logging

import pytest

from axiom_ext_openmc.references import install_specs
from axiom_ext_openmc.references.nrc_ml2327 import (
    OPENMC_NRC_ML2327_REFERENCES,
)
from axiom_ext_openmc.references.nrc_ml2327 import (
    install_references as install_nrc,
)
from axiom_ext_openmc.references.ornl_tm_0728 import (
    OPENMC_ORNL_TM_0728_REFERENCES,
)
from axiom_ext_openmc.references.ornl_tm_0728 import (
    install_references as install_ornl,
)


class CapturingRegistry:
    """Duck-typed stand-in for any ReferenceRegistry."""

    def __init__(self) -> None:
        self.registered: list = []

    def register(self, reference) -> None:
        self.registered.append(reference)


ALL_SEEDED = [
    pytest.param(install_nrc, OPENMC_NRC_ML2327_REFERENCES, id="nrc-ml2327"),
    pytest.param(install_ornl, OPENMC_ORNL_TM_0728_REFERENCES, id="ornl-tm-0728"),
]


@pytest.mark.parametrize("installer,specs", ALL_SEEDED)
def test_every_seeded_value_is_declared_provisional(installer, specs):
    """A seeded placeholder that forgets the flag is the bug this guards."""
    assert specs, "reference module declares no specs"
    unflagged = [s.uri for s in specs if not s.provisional]
    assert not unflagged, (
        "these references carry placeholder values but are not marked "
        f"provisional, so they would install silently: {unflagged}"
    )


@pytest.mark.parametrize("installer,specs", ALL_SEEDED)
def test_install_refuses_provisional_by_default(installer, specs):
    """The default path installs nothing while every value is a placeholder."""
    registry = CapturingRegistry()
    installed = installer(registry)
    assert installed == 0
    assert registry.registered == []


@pytest.mark.parametrize("installer,specs", ALL_SEEDED)
def test_install_provisional_requires_explicit_opt_in(installer, specs):
    """Structural tests may opt in; nothing else should."""
    registry = CapturingRegistry()
    installed = installer(registry, include_provisional=True)
    assert installed == len(specs)
    assert len(registry.registered) == len(specs)


@pytest.mark.parametrize("installer,specs", ALL_SEEDED)
def test_skipping_is_logged_by_uri(installer, specs, caplog):
    """An operator must be able to see which cases cannot be verified."""
    with caplog.at_level(logging.WARNING, logger="axiom_ext_openmc.references"):
        installer(CapturingRegistry())

    assert caplog.records, "skipping provisional references logged nothing"
    message = caplog.text
    for spec in specs:
        assert spec.uri in message


def test_non_provisional_specs_still_install():
    """Once a reviewer replaces a value, it flows through with no other change."""

    class Reviewed:
        uri = "reference://nrc-ml2327/triga-netl-P1A/k-eff"
        value = 1.00000
        uncertainty = 0.00050
        unit = "pcm"
        source = "NRC ML2327"
        citation = "NETL TRIGA Safety Analysis Report, NRC ML2327, August 2023"
        provisional = False

    registry = CapturingRegistry()
    assert install_specs([Reviewed()], registry) == 1
    assert len(registry.registered) == 1


def test_a_spec_without_the_attribute_is_treated_as_reviewed():
    """Foreign specs predating the flag install normally rather than vanishing."""

    class Foreign:
        uri = "reference://elsewhere/case/k-eff"
        value = 1.0
        uncertainty = 0.001
        unit = "pcm"
        source = "Elsewhere"
        citation = "A reference module written before the flag existed"

    registry = CapturingRegistry()
    assert install_specs([Foreign()], registry) == 1
