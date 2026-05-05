# Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""Phase 5 — ORNL-TM-0728 MSR reference tests."""

from __future__ import annotations

from axiom_ext_openmc.references.ornl_tm_0728 import (
    OPENMC_ORNL_TM_0728_REFERENCES,
    install_references,
)


def test_msr_references_have_correct_shape():
    """All ORNL-TM-0728 MSR references declare URI, value, uncertainty, unit, source."""
    for ref in OPENMC_ORNL_TM_0728_REFERENCES:
        assert ref.uri.startswith("reference://ornl-tm-0728/msr-N_")
        assert ref.uri.endswith("/k-eff")
        assert ref.value > 0
        assert ref.uncertainty > 0
        assert ref.unit == "pcm"
        assert ref.source == "ORNL-TM-0728"


def test_msr_references_cover_n_1_through_n_5():
    """Phase 5 ships N_1..N_5; every problem in the progression is referenced."""
    uris = {ref.uri for ref in OPENMC_ORNL_TM_0728_REFERENCES}
    for n in (1, 2, 3, 4, 5):
        assert f"reference://ornl-tm-0728/msr-N_{n}/k-eff" in uris


def test_msr_install_references_into_dict_registry():
    """install_references works with a duck-typed dict-backed registry."""
    captured = []
    class DictRegistry:
        def register(self, item):
            captured.append(item)

    count = install_references(DictRegistry())
    assert count == len(OPENMC_ORNL_TM_0728_REFERENCES)
    assert count == 5
