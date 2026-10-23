# Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""The library grades honestly and does not import the adapter until asked."""

from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from axiom_ext_openmc.library import grade, list_cases, parse_summary, runner_status
from axiom_ext_openmc.references.nrc_ml2327 import OPENMC_NRC_ML2327_REFERENCES
from axiom_ext_openmc.references.ornl_tm_0728 import OPENMC_ORNL_TM_0728_REFERENCES


def test_runner_status_keeps_the_two_checks_apart(monkeypatch):
    monkeypatch.setattr(
        "axiom_ext_openmc.verification.availability.openmc_available",
        lambda: False,
    )
    status = runner_status()
    assert status["python_package"] is False
    assert status["can_run_openmc"] is False
    assert status["reason"]
    assert "openmc_binary" in status
    assert "docker" in status


def test_list_cases_is_the_ladder_in_order():
    cases = list_cases()
    assert [case["name"] for case in cases] == [
        "infinite_medium_uo2",
        "pincell_uo2",
        "assembly_17x17",
    ]
    assert all(case["reference_uri"].startswith("reference://") for case in cases)
    assert all(case["n_particles"] > 0 for case in cases)


def test_every_shipped_reference_grades_as_provisional_not_agreement():
    """Placeholder numbers must not come back as agreement, or at all."""
    specs = [*OPENMC_NRC_ML2327_REFERENCES, *OPENMC_ORNL_TM_0728_REFERENCES]
    assert specs, "the extension shipped no references to refuse"
    for spec in specs:
        assert spec.provisional is True
        result = grade(spec.uri, k_eff=1.5, k_eff_std=0.0)
        assert result["status"] == "provisional"
        assert result["agrees"] is None
        assert result["k_eff"] == 1.5
        blob = json.dumps(result)
        assert str(spec.value) not in blob
        assert "reference_value" not in result


def test_missing_reference_is_not_agreement():
    result = grade("reference://does-not-exist/k-eff", k_eff=1.0)
    assert result["status"] == "no_reference"
    assert result["agrees"] is None


def test_a_cleared_reference_is_a_magnitude_check(monkeypatch):
    @dataclass(frozen=True)
    class _Real:
        uri: str = "reference://reviewed/k-eff"
        value: float = 1.0
        uncertainty: float = 0.001
        unit: str = "1"
        source: str = "reviewed"
        citation: str = "reviewed"
        provisional: bool = False

    monkeypatch.setattr("axiom_ext_openmc.library._specs", lambda: [_Real()])
    inside = grade("reference://reviewed/k-eff", k_eff=1.0005, k_eff_std=0.0004)
    outside = grade("reference://reviewed/k-eff", k_eff=1.01, k_eff_std=0.0)
    assert inside["status"] == "compared"
    assert inside["agrees"] is True
    assert outside["agrees"] is False
    assert outside["reference_value"] == 1.0


def test_parse_summary_reads_result_json_and_rejects_a_non_hdf5_file(tmp_path):
    """result.json stays the container summary.

    A file named statepoint.*.h5 that is not HDF5 used to raise
    NotImplementedError, which locked in the missing reader. The adapter now
    calls the shared reader, so the same file is an unreadable statepoint.
    """
    deck = tmp_path / "deck"
    deck.mkdir()
    (deck / "result.json").write_text(json.dumps({"k_eff": 1.02, "k_eff_std": 0.001}))
    assert parse_summary(deck)["k_eff"] == 1.02

    bare = tmp_path / "bare"
    bare.mkdir()
    (bare / "statepoint.10.h5").write_bytes(b"not really hdf5")
    with pytest.raises(ValueError, match="not a readable HDF5"):
        parse_summary(bare)


def test_parse_summary_rejects_a_missing_directory(tmp_path):
    with pytest.raises(FileNotFoundError):
        parse_summary(tmp_path / "missing")
