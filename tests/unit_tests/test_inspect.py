# Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""Model checks, statepoint tables, and the CLI and skills that call them.

The numbers in the statepoint fixtures are written into the file by the test.
Assertions check that the reader returns those numbers, not a solver result.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import h5py
import numpy as np
import pytest

from axiom_ext_openmc.commands.openmc import main
from axiom_ext_openmc.library import (
    check_cross_sections,
    compare_statepoints,
    plan_run,
    read_statepoint,
    summarize_model,
    validate_model,
)

_DECK_SAB = "c_U_in_UO2"


def _deck(
    root: Path,
    *,
    cell_material: str = "1",
    particles: str = "1000",
    batches: str = "10",
    inactive: str = "2",
    source: bool = True,
    nuclide: str = "U235",
    sab: str | None = None,
    tally: bool = True,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    sab_xml = f'<sab name="{sab}"/>' if sab else ""
    (root / "materials.xml").write_text(
        f"""<?xml version="1.0"?>
<materials>
  <material id="1" name="fuel">
    <density value="10.4" units="g/cm3"/>
    <nuclide name="{nuclide}" ao="1.0"/>
    {sab_xml}
  </material>
</materials>
"""
    )
    (root / "geometry.xml").write_text(
        f"""<?xml version="1.0"?>
<geometry>
  <cell id="1" name="fuel" material="{cell_material}" region="-1" universe="0"/>
  <surface id="1" type="sphere" boundary="vacuum"/>
</geometry>
"""
    )
    source_xml = '<source><space type="point"/></source>' if source else ""
    (root / "settings.xml").write_text(
        f"""<?xml version="1.0"?>
<settings>
  <run_mode>eigenvalue</run_mode>
  <particles>{particles}</particles>
  <batches>{batches}</batches>
  <inactive>{inactive}</inactive>
  {source_xml}
</settings>
"""
    )
    if tally:
        (root / "tallies.xml").write_text(
            """<?xml version="1.0"?>
<tallies>
  <tally id="1" name="flux">
    <filters><filter type="cell" bins="1"/></filters>
    <scores>flux</scores>
    <nuclides>total</nuclides>
  </tally>
</tallies>
"""
        )
    return root


def _xs(directory: Path, entries: dict[str, bool]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    lines = ["<cross_sections>"]
    for name, exists in entries.items():
        filename = f"{name}.h5"
        if exists:
            (directory / filename).write_bytes(b"not-an-evaluation")
        lines.append(
            f'  <library materials="{name}" path="{filename}" type="neutron"/>'
        )
    lines.append("</cross_sections>")
    path = directory / "cross_sections.xml"
    path.write_text("\n".join(lines))
    return path


def _statepoint(
    path: Path,
    *,
    k_eff: float = 1.25,
    k_std: float = 0.05,
    k_generation: list[float] | None = None,
    n_realizations: int = 4,
    tally: dict[str, float | str | int] | None = None,
    global_sum: tuple[float, float] | None = None,
    filetype: str = "statepoint",
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(path, "w") as handle:
        handle.attrs["filetype"] = filetype
        handle.attrs["openmc_version"] = "0.15.0"
        handle.attrs["tallies_present"] = 1 if tally else 0
        handle.create_dataset("run_mode", data=b"eigenvalue")
        handle.create_dataset("n_particles", data=1000)
        handle.create_dataset("n_batches", data=10)
        handle.create_dataset("current_batch", data=10)
        handle.create_dataset("n_inactive", data=2)
        handle.create_dataset("generations_per_batch", data=1)
        handle.create_dataset("n_realizations", data=n_realizations)
        handle.create_dataset("k_combined", data=np.array([k_eff, k_std], dtype="f8"))
        if k_generation is not None:
            handle.create_dataset("k_generation", data=np.array(k_generation, dtype="f8"))
        if global_sum is not None:
            table = np.zeros((4, 3), dtype="f8")
            table[0, 1] = global_sum[0]
            table[0, 2] = global_sum[1]
            handle.create_dataset("global_tallies", data=table)
        tallies = handle.create_group("tallies")
        tallies.create_group("filters")
        if tally:
            tallies.attrs["n_tallies"] = 1
            tallies.attrs["ids"] = np.array([int(tally["id"])], dtype="i4")
            group = tallies.create_group(f"tally {tally['id']}")
            group.attrs["internal"] = 0
            group.create_dataset("name", data=str(tally["name"]).encode())
            group.create_dataset("estimator", data=b"tracklength")
            group.create_dataset("n_realizations", data=n_realizations)
            group.create_dataset("n_filters", data=0)
            group.create_dataset("nuclides", data=np.array([b"total"]))
            group.create_dataset("n_score_bins", data=1)
            group.create_dataset("score_bins", data=np.array([str(tally["score"]).encode()]))
            group.create_dataset(
                "results",
                data=np.array([[[tally["sum"], tally["sum_sq"]]]], dtype="f8"),
            )
        else:
            tallies.attrs["n_tallies"] = 0
    return path


def test_valid_deck_validates_and_summarizes_what_was_written(tmp_path: Path):
    deck = _deck(tmp_path / "model", sab=_DECK_SAB)
    report = validate_model(deck)
    assert report["ok"] is True
    assert report["errors"] == []
    assert report["checkers"] == ["xml"]

    summary = summarize_model(deck)
    assert summary["counts"] == {"materials": 1, "cells": 1, "surfaces": 1, "tallies": 1}
    assert summary["materials"][0]["name"] == "fuel"
    assert summary["materials"][0]["nuclides"] == [{"name": "U235", "ao": 1.0, "wo": None}]
    assert summary["materials"][0]["sab"] == [_DECK_SAB]
    assert summary["cells"][0]["material"] == "1"
    assert summary["settings"]["particles"] == 1000
    assert summary["settings"]["batches"] == 10
    assert summary["settings"]["inactive"] == 2
    assert summary["tallies"][0]["scores"] == ["flux"]
    assert "H1" not in json.dumps(summary["materials"])


def test_structural_errors_name_the_broken_reference(tmp_path: Path):
    deck = _deck(tmp_path / "bad", cell_material="99", particles="0", source=False)
    report = validate_model(deck)
    assert report["ok"] is False
    codes = {item["code"] for item in report["errors"]}
    assert {"unknown_material", "bad_particles", "missing_source"} <= codes


def test_validate_does_not_import_openmc_unless_asked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    deck = _deck(tmp_path / "model")
    real_import = __import__

    def guarded(name, *args, **kwargs):
        if name == "openmc" or name.startswith("openmc."):
            raise AssertionError("validate imported openmc")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", guarded)
    assert validate_model(deck)["ok"] is True


def test_use_openmc_reports_a_missing_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    deck = _deck(tmp_path / "model")
    import builtins

    real_import = builtins.__import__

    def guarded(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "openmc" or name.startswith("openmc."):
            raise ImportError("simulated")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded)
    report = validate_model(deck, use_openmc=True)
    assert report["ok"] is False
    assert any(item["code"] == "openmc_unavailable" for item in report["errors"])


def test_cross_sections_match_names_and_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    deck = _deck(tmp_path / "model", nuclide="U235", sab="c_H_in_H2O")
    index = _xs(tmp_path / "lib", {"U235": True, "O16": False})
    monkeypatch.setenv("OPENMC_CROSS_SECTIONS", str(index))
    report = check_cross_sections(model_dir=deck)
    assert report["selected"]["source"] == "environment"
    assert report["nuclides_missing"] == []
    assert report["sab_missing"] == ["c_H_in_H2O"]
    assert "O16" not in report["nuclides_in_model"]
    assert report["elements_in_model"] == []
    assert any(item["code"] == "library_file_missing" for item in report["errors"])
    assert report["ok"] is False


def test_a_missing_environment_path_is_not_replaced(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    deck = _deck(tmp_path / "model", sab=None)
    real = _xs(tmp_path / "lib", {"U235": True})
    (deck / "materials.xml").write_text(
        (deck / "materials.xml").read_text().replace(
            "<materials>",
            f"<materials><cross_sections>{real}</cross_sections>",
        )
    )
    monkeypatch.setenv("OPENMC_CROSS_SECTIONS", str(tmp_path / "missing.xml"))
    report = check_cross_sections(model_dir=deck)
    assert report["selected"]["source"] == "environment"
    assert report["ok"] is False
    assert any(item["code"] == "cross_sections_missing" for item in report["errors"])


def test_statepoint_k_eff_is_the_stored_combined_value_not_a_new_reduction(tmp_path: Path):
    path = _statepoint(
        tmp_path / "statepoint.10.h5",
        k_eff=1.25,
        k_std=0.05,
        k_generation=[1.0, 1.0, 1.0, 3.0],
        global_sum=(5.0, 9.25),
        tally={"id": 1, "name": "flux", "score": "flux", "sum": 40.0, "sum_sq": 403.0},
    )
    report = read_statepoint(path)
    assert report["k_eff"] == 1.25
    assert report["k_eff_std"] == 0.05
    assert report["k_eff_source"] == "k_combined"
    assert report["k_generation"] == [1.0, 1.0, 1.0, 3.0]
    assert report["k_eff"] != sum(report["k_generation"]) / len(report["k_generation"])
    assert report["global_tallies"][0]["name"] == "k-collision"
    assert report["global_tallies"][0]["mean"] == pytest.approx(1.25)
    assert report["global_tallies"][0]["std_dev"] == pytest.approx(0.5)
    row = report["tally_records"][0]
    assert row["score"] == "flux"
    assert row["mean"] == pytest.approx(10.0)
    assert row["std_dev"] == pytest.approx(0.5)
    assert report["tallies"]["columns"][0] == "tally_id"
    assert report["tallies"]["rows"][0][report["tallies"]["columns"].index("mean")] == pytest.approx(10.0)
    json.dumps(report, allow_nan=False)


def test_one_realization_does_not_invent_a_standard_deviation(tmp_path: Path):
    path = _statepoint(
        tmp_path / "statepoint.1.h5",
        n_realizations=1,
        tally={"id": 1, "name": "flux", "score": "flux", "sum": 4.0, "sum_sq": 16.0},
    )
    row = read_statepoint(path)["tally_records"][0]
    assert row["mean"] == pytest.approx(4.0)
    assert row["std_dev"] is None


def test_directory_read_uses_the_highest_batch_number(tmp_path: Path):
    _statepoint(tmp_path / "statepoint.9.h5", k_eff=1.1, k_std=0.01)
    _statepoint(tmp_path / "statepoint.10.h5", k_eff=1.2, k_std=0.01)
    assert read_statepoint(tmp_path)["k_eff"] == 1.2


def test_non_statepoint_hdf5_and_garbage_are_errors(tmp_path: Path):
    garbage = tmp_path / "statepoint.1.h5"
    garbage.write_bytes(b"not hdf5")
    with pytest.raises(ValueError, match="not a readable HDF5"):
        read_statepoint(garbage)
    summary = _statepoint(tmp_path / "summary.h5", filetype="summary")
    with pytest.raises(ValueError, match="filetype"):
        read_statepoint(summary)


def test_non_finite_k_combined_is_null(tmp_path: Path):
    path = _statepoint(tmp_path / "statepoint.2.h5", k_eff=1.2, k_std=math.inf)
    report = read_statepoint(path)
    assert report["k_eff"] == pytest.approx(1.2)
    assert report["k_eff_std"] is None
    assert "non-finite" in report["k_eff_note"]


def test_compare_subtracts_reported_values(tmp_path: Path):
    left = _statepoint(
        tmp_path / "a" / "statepoint.4.h5",
        k_eff=1.25,
        k_std=0.05,
        tally={"id": 1, "name": "flux", "score": "flux", "sum": 40.0, "sum_sq": 403.0},
    )
    right = _statepoint(
        tmp_path / "b" / "statepoint.4.h5",
        k_eff=1.5,
        k_std=0.05,
        tally={"id": 1, "name": "flux", "score": "flux", "sum": 48.0, "sum_sq": 580.0},
    )
    report = compare_statepoints(left, right)
    assert report["k_eff"]["delta"] == pytest.approx(-0.25)
    assert report["k_eff"]["tolerance"] == pytest.approx(math.sqrt(0.005))
    assert report["k_eff"]["within_reported_uncertainty"] is False
    assert "published reference" in report["note"]
    row = report["tally_table"]["rows"][0]
    columns = report["tally_table"]["columns"]
    assert row[columns.index("delta")] == pytest.approx(10.0 - 12.0)
    assert row[columns.index("status")] == "both"


def test_adapter_and_library_share_the_reader_and_result_json_still_wins(tmp_path: Path):
    _statepoint(tmp_path / "statepoint.3.h5", k_eff=1.25, k_std=0.02)
    from axiom_ext_openmc.adapter import OpenMCKernelAdapter

    parsed = OpenMCKernelAdapter()._parse_statepoint(tmp_path)
    direct = read_statepoint(tmp_path)
    assert parsed["k_eff"] == direct["k_eff"] == 1.25
    assert parsed["tallies"] == direct["tallies"]

    (tmp_path / "result.json").write_text(json.dumps({"k_eff": 9.0, "k_eff_std": 1.0}))
    assert OpenMCKernelAdapter()._parse_statepoint(tmp_path)["k_eff"] == 9.0
    assert read_statepoint(tmp_path)["k_eff"] == 1.25


def test_missing_h5py_names_the_extra(monkeypatch: pytest.MonkeyPatch):
    import builtins
    import sys

    monkeypatch.delitem(sys.modules, "h5py", raising=False)
    real_import = builtins.__import__

    def guarded(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "h5py" or name.startswith("h5py."):
            raise ImportError("simulated")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded)
    from axiom_ext_openmc.statepoint import _require_h5py

    with pytest.raises(ImportError, match=r"axiom-ext-openmc\[statepoint\]"):
        _require_h5py()


def test_plan_does_not_start_openmc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    deck = _deck(tmp_path / "model", sab=None)
    index = _xs(tmp_path / "lib", {"U235": True})
    monkeypatch.setenv("OPENMC_CROSS_SECTIONS", str(index))

    def boom(*args, **kwargs):
        raise AssertionError("OpenMC was started")

    monkeypatch.setattr("axiom_ext_openmc.adapter.subprocess.run", boom)
    monkeypatch.setattr(
        "axiom_ext_openmc.adapter.shutil.which",
        lambda name: "/usr/bin/openmc" if name == "openmc" else None,
    )
    report = plan_run(deck, kernel_options={"runner": "subprocess"})
    assert report["executed"] is False
    assert report["ready"] is True
    assert report["summary"]["settings"]["particles"] == 1000
    assert report["expected_outputs"] == ["summary.h5", "statepoint.10.h5"]
    assert "not started" in report["invocation"]
    assert report["runner"]["connected"] is True


def test_cli_and_skill_return_the_library_report(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    deck = _deck(tmp_path / "model")
    from axiom.infra.skills import SkillRegistry

    from axiom_ext_openmc.skills import bind

    library_report = validate_model(deck)
    assert main(["validate", str(deck)]) == 0
    cli_report = json.loads(capsys.readouterr().out)
    assert cli_report == library_report

    registry = SkillRegistry()
    bind(registry)
    result = registry.invoke("openmc.validate", {"input_dir": str(deck)}, _ctx(registry))
    assert result.ok is True
    assert result.value == library_report

    path = _statepoint(tmp_path / "statepoint.4.h5", k_eff=1.25, k_std=0.05)
    assert main(["stat", str(path)]) == 0
    cli_stat = json.loads(capsys.readouterr().out)
    assert cli_stat["k_eff"] == read_statepoint(path)["k_eff"]
    skill_stat = registry.invoke("openmc.stat", {"path": str(path)}, _ctx(registry))
    assert skill_stat.ok is True
    assert skill_stat.value["k_eff"] == 1.25
    assert skill_stat.value["k_eff_std"] == 0.05


def test_cli_check_and_review_share_the_library(tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch):
    deck = _deck(tmp_path / "model", sab=None)
    index = _xs(tmp_path / "lib", {"U235": True})
    monkeypatch.delenv("OPENMC_CROSS_SECTIONS", raising=False)
    code = main(["check", "--path", str(index), "--model", str(deck)])
    report = json.loads(capsys.readouterr().out)
    assert report == check_cross_sections(index, deck)
    assert code == 0

    def boom(*args, **kwargs):
        raise AssertionError("OpenMC was started")

    monkeypatch.setattr("axiom_ext_openmc.adapter.subprocess.run", boom)
    code = main(["review", str(deck), "--runner", "ssh:peer"])
    plan = json.loads(capsys.readouterr().out)
    direct = plan_run(deck, kernel_options={"runner": "ssh:peer"})
    assert plan["executed"] is False
    assert plan["executed"] == direct["executed"]
    assert plan["runner"]["connected"] is False
    assert code == 1


def test_governing_aeos_version_is_0_1_and_package_version_is_separate():
    import tomllib

    manifest_path = Path(__file__).resolve().parents[2] / "axiom-extension.toml"
    manifest = tomllib.loads(manifest_path.read_text())
    extension = manifest["extension"]
    assert extension["aeos_version"] == "0.1.0"
    assert extension["chain_level"] == "A"
    assert extension["version"] == "0.2.0"
    from axiom_ext_openmc import __version__

    assert __version__ == "0.2.0"


def _ctx(registry):
    from axiom.infra.skills import SkillContext

    class _Silent:
        def exception(self, *args, **kwargs):
            return None

        def info(self, *args, **kwargs):
            return None

        def warning(self, *args, **kwargs):
            return None

        def debug(self, *args, **kwargs):
            return None

    return SkillContext(registry=registry, state_dir=Path("/tmp"), logger=_Silent())
