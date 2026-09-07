# Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""Running OpenMC for real needs two things, and says which one is missing.

A verification case that silently does not run is the same failure class as a
reference value that silently is not real: the suite reports success and nobody
learns anything. So availability is a single, testable predicate with a
human-readable reason, rather than a bare ``pytest.importorskip`` scattered
across test modules.
"""

from __future__ import annotations

from axiom_ext_openmc.verification import availability


def test_reason_names_openmc_when_the_package_is_missing(monkeypatch):
    monkeypatch.setattr(availability, "openmc_available", lambda: False)
    monkeypatch.setattr(availability, "cross_sections_path", lambda: None)

    reason = availability.unavailable_reason()

    assert reason is not None
    assert "openmc" in reason.lower()


def test_reason_names_cross_sections_when_only_data_is_missing(monkeypatch):
    monkeypatch.setattr(availability, "openmc_available", lambda: True)
    monkeypatch.setattr(availability, "cross_sections_path", lambda: None)

    reason = availability.unavailable_reason()

    assert reason is not None
    assert "OPENMC_CROSS_SECTIONS" in reason


def test_no_reason_when_both_are_present(monkeypatch, tmp_path):
    xs = tmp_path / "cross_sections.xml"
    xs.write_text("<cross_sections/>", encoding="utf-8")
    monkeypatch.setattr(availability, "openmc_available", lambda: True)
    monkeypatch.setattr(availability, "cross_sections_path", lambda: xs)

    assert availability.unavailable_reason() is None
    assert availability.can_run_openmc() is True


def test_cross_sections_path_requires_the_file_to_exist(monkeypatch, tmp_path):
    """An exported variable pointing at nothing is worse than an unset one — it
    looks configured."""
    monkeypatch.setenv("OPENMC_CROSS_SECTIONS", str(tmp_path / "absent.xml"))
    assert availability.cross_sections_path() is None


def test_cross_sections_path_returns_the_file_when_it_exists(monkeypatch, tmp_path):
    xs = tmp_path / "cross_sections.xml"
    xs.write_text("<cross_sections/>", encoding="utf-8")
    monkeypatch.setenv("OPENMC_CROSS_SECTIONS", str(xs))

    assert availability.cross_sections_path() == xs


def test_cross_sections_path_is_none_when_unset(monkeypatch):
    monkeypatch.delenv("OPENMC_CROSS_SECTIONS", raising=False)
    assert availability.cross_sections_path() is None


def test_can_run_openmc_is_false_whenever_there_is_a_reason(monkeypatch):
    monkeypatch.setattr(availability, "unavailable_reason", lambda: "nope")
    assert availability.can_run_openmc() is False
