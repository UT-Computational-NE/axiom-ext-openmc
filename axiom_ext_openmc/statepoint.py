# Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""Read an OpenMC statepoint file. One reader, shared with the adapter.

k-effective is the two-value ``k_combined`` dataset OpenMC writes
(mean, standard deviation). The per-generation ``k_generation`` series is
returned as stored and is not reduced into another k-effective. Tally means
and standard deviations use the sum and sum-of-squares OpenMC stores and the
same reduction as ``openmc.Tally`` and ``StatePoint.global_tallies``:

- mean = sum / n_realizations
- sample standard deviation = sqrt((sum_sq / n - mean^2) / (n - 1)) for n > 1
- tally standard deviation is 0 when the mean is 0, and null for a single
  realization with a non-zero mean (OpenMC reports NaN there; null keeps the
  result JSON-safe and does not replace it with 0)
- a negative variance from rounding is clamped to 0, as OpenMC's tally
  standard deviation does

``h5py`` is optional. Without it the reader says how to install the
``statepoint`` extra and does not invent a summary. Comparing two files
subtracts the numbers those files reported. It is not a published reference
and it does not report agreement.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

__all__ = [
    "compare_statepoints",
    "read_statepoint",
]

_GLOBAL_NAMES = ("k-collision", "k-absorption", "k-tracklength", "leakage")
_TALLY_COLUMNS = (
    "tally_id",
    "tally_name",
    "estimator",
    "nuclide",
    "score",
    "filter_bin",
    "mean",
    "std_dev",
)
_COMPARE_NOTE = (
    "delta is the left value minus the right value. tolerance is the "
    "root-sum-square of the two reported standard deviations when both are "
    "finite. within_reported_uncertainty is that magnitude check. It is not "
    "agreement with a published reference."
)


def read_statepoint(path: str | Path) -> dict[str, Any]:
    """Read one statepoint file, or the highest-numbered ``statepoint.*.h5`` in a directory.

    A directory that only contains ``result.json`` is not a statepoint.
    ``parse_summary`` is the adapter path that still prefers that file.
    """
    target = _locate(Path(path))
    h5py = _require_h5py()
    try:
        handle = h5py.File(target, "r")
    except OSError as exc:
        raise ValueError(f"{target} is not a readable HDF5 statepoint: {exc}") from exc
    with handle:
        return _read_open(handle, target)


def compare_statepoints(left: str | Path, right: str | Path) -> dict[str, Any]:
    """Subtract two statepoints' reported k-effective values and tally means."""
    a = read_statepoint(left)
    b = read_statepoint(right)
    return {
        "left": _brief(a),
        "right": _brief(b),
        "k_eff": _magnitude(a.get("k_eff"), a.get("k_eff_std"), b.get("k_eff"), b.get("k_eff_std")),
        "global_tallies": _compare_named(a.get("global_tallies") or [], b.get("global_tallies") or []),
        "tally_table": _compare_tally_table(a.get("tally_records") or [], b.get("tally_records") or []),
        "note": _COMPARE_NOTE,
    }


def _locate(path: Path) -> Path:
    if path.is_file():
        return path
    if not path.is_dir():
        raise FileNotFoundError(f"statepoint path does not exist: {path}")
    found = list(path.glob("statepoint.*.h5"))
    if not found:
        hint = ""
        if (path / "result.json").is_file():
            hint = " result.json is present; parse_summary reads that file, this function does not."
        raise FileNotFoundError(f"no statepoint.*.h5 in {path}.{hint}")
    return max(found, key=_batch_key)


def _batch_key(path: Path) -> tuple[int, str]:
    stem = path.name.removeprefix("statepoint.").removesuffix(".h5")
    try:
        return (int(stem), path.name)
    except ValueError:
        return (-1, path.name)


def _require_h5py() -> Any:
    try:
        import h5py
    except ImportError as exc:
        raise ImportError(
            "Reading an OpenMC statepoint needs the optional h5py package. "
            "Install it with: pip install 'axiom-ext-openmc[statepoint]'. "
            "The OpenMC solver is not required to read a statepoint that "
            "already exists."
        ) from exc
    return h5py


def _read_open(handle: Any, path: Path) -> dict[str, Any]:
    filetype = _attr_str(handle, "filetype")
    if filetype is not None and filetype != "statepoint":
        raise ValueError(
            f"{path} is HDF5 but its filetype is {filetype!r}, not 'statepoint'"
        )
    run_mode = _dataset_str(handle, "run_mode")
    k_eff, k_eff_std, k_note = _k_combined(handle)
    entropy = _float_list(handle, "entropy")
    records, filters = _tally_records(handle)
    return {
        "path": str(path),
        "filetype": filetype,
        "openmc_version": _attr_str(handle, "openmc_version"),
        "run_mode": run_mode,
        "n_particles": _dataset_int(handle, "n_particles"),
        "n_batches": _dataset_int(handle, "n_batches"),
        "current_batch": _dataset_int(handle, "current_batch"),
        "n_inactive": _dataset_int(handle, "n_inactive"),
        "generations_per_batch": _dataset_int(handle, "generations_per_batch"),
        "n_realizations": _dataset_int(handle, "n_realizations"),
        "n_cycles": _dataset_int(handle, "current_batch"),
        "k_eff": k_eff,
        "k_eff_std": k_eff_std,
        "k_eff_source": "k_combined" if "k_combined" in handle else None,
        "k_eff_note": k_note,
        "k_generation": _float_list(handle, "k_generation"),
        "entropy": entropy,
        "shannon_entropy": entropy[-1] if entropy else None,
        "global_tallies": _global_tallies(handle),
        "tally_records": records,
        "tallies": _as_table(records, _TALLY_COLUMNS),
        "filters": filters,
    }


def _k_combined(handle: Any) -> tuple[float | None, float | None, str | None]:
    if "k_combined" not in handle:
        return None, None, "no k_combined dataset; k_generation is not reduced into k_eff"
    values = _dataset_floats(handle["k_combined"])
    if len(values) != 2:
        raise ValueError(
            f"k_combined has {len(values)} values; OpenMC writes a mean and a standard deviation"
        )
    mean = _finite(values[0])
    std = _finite(values[1])
    note = None
    if mean is None or std is None:
        note = "k_combined contains a non-finite value, which is reported as null"
    return mean, std, note


def _global_tallies(handle: Any) -> list[dict[str, Any]]:
    if "global_tallies" not in handle:
        return []
    data = handle["global_tallies"][()]
    shape = getattr(data, "shape", None)
    if not shape or len(shape) != 2 or shape[1] < 3:
        raise ValueError(
            "global_tallies does not have the (row, value/sum/sum_sq) layout OpenMC writes"
        )
    n = _dataset_int(handle, "n_realizations")
    rows = []
    for index in range(shape[0]):
        name = _GLOBAL_NAMES[index] if index < len(_GLOBAL_NAMES) else f"global-{index}"
        total = float(data[index, 1])
        total_sq = float(data[index, 2])
        mean, std = _global_mean_std(total, total_sq, n)
        rows.append(
            {
                "name": name,
                "sum": total,
                "sum_sq": total_sq,
                "mean": mean,
                "std_dev": std,
            }
        )
    return rows


def _global_mean_std(
    total: float,
    total_sq: float,
    n: int | None,
) -> tuple[float | None, float | None]:
    if n is None or n <= 0:
        return None, None
    mean = total / n
    if n < 2:
        return _finite(mean), None
    variance = (total_sq / n - mean * mean) / (n - 1)
    if variance < 0:
        variance = 0.0
    return _finite(mean), _finite(math.sqrt(variance))


def _tally_records(handle: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if "tallies" not in handle:
        return [], []
    group = handle["tallies"]
    present = handle.attrs.get("tallies_present", 0)
    try:
        present_flag = int(present) > 0
    except (TypeError, ValueError):
        present_flag = False
    filters = _filters(group)
    if not present_flag:
        return [], filters
    ids = _attr_ints(group, "ids")
    records: list[dict[str, Any]] = []
    for ident in ids:
        key = f"tally {ident}"
        if key not in group:
            continue
        tally = group[key]
        internal = tally.attrs.get("internal", 0)
        try:
            if int(internal) == 1:
                continue
        except (TypeError, ValueError):
            pass
        name = _dataset_str(tally, "name") or ""
        estimator = _dataset_str(tally, "estimator")
        n = _dataset_int(tally, "n_realizations")
        scores = _dataset_strings(tally, "score_bins")
        nuclides = _dataset_strings(tally, "nuclides") or ["total"]
        if "results" not in tally or n is None:
            continue
        data = tally["results"][()]
        shape = getattr(data, "shape", None)
        if not shape or len(shape) != 3 or shape[2] < 2:
            raise ValueError(f"tally {ident} results do not have sum and sum_sq columns")
        n_filter, n_flat, _moments = shape
        if not scores or len(nuclides) * len(scores) != n_flat:
            raise ValueError(
                f"tally {ident} results shape {tuple(shape)} does not match "
                f"{len(nuclides)} nuclides and {len(scores)} scores"
            )
        n_scores = len(scores)
        for filter_bin in range(n_filter):
            for nuc_i, nuclide in enumerate(nuclides):
                for score_i, score in enumerate(scores):
                    flat = nuc_i * n_scores + score_i
                    total = float(data[filter_bin, flat, 0])
                    total_sq = float(data[filter_bin, flat, 1])
                    mean, std = _tally_mean_std(total, total_sq, n)
                    records.append(
                        {
                            "tally_id": int(ident),
                            "tally_name": name,
                            "estimator": estimator,
                            "nuclide": nuclide,
                            "score": score,
                            "filter_bin": filter_bin,
                            "sum": total,
                            "sum_sq": total_sq,
                            "mean": mean,
                            "std_dev": std,
                        }
                    )
    return records, filters


def _tally_mean_std(total: float, total_sq: float, n: int) -> tuple[float | None, float | None]:
    if n <= 0:
        return None, None
    mean = total / n
    finite_mean = _finite(mean)
    if finite_mean is None:
        return None, None
    if finite_mean == 0.0:
        return 0.0, 0.0
    if n == 1:
        return finite_mean, None
    variance = (total_sq / n - finite_mean * finite_mean) / (n - 1)
    if variance < 0:
        variance = 0.0
    return finite_mean, _finite(math.sqrt(variance))


def _filters(group: Any) -> list[dict[str, Any]]:
    if "filters" not in group:
        return []
    filters = group["filters"]
    found = []
    for name in filters:
        if not str(name).startswith("filter "):
            continue
        node = filters[name]
        bins = _dataset_strings(node, "bins")
        if not bins and "bins" in node:
            bins = [str(item) for item in _dataset_floats(node["bins"])]
        found.append(
            {
                "id": str(name).split(" ", 1)[1],
                "type": _dataset_str(node, "type") or _attr_str(node, "type"),
                "bins": bins or None,
            }
        )
    return found


def _compare_tally_table(
    left: list[dict[str, Any]],
    right: list[dict[str, Any]],
) -> dict[str, Any]:
    def key(row: dict[str, Any]) -> tuple[Any, ...]:
        return (row.get("tally_id"), row.get("nuclide"), row.get("score"), row.get("filter_bin"))

    right_by = {key(row): row for row in right}
    seen = set()
    records = []
    for row in left:
        ident = key(row)
        seen.add(ident)
        other = right_by.get(ident)
        records.append(_tally_delta(row, other))
    for row in right:
        ident = key(row)
        if ident not in seen:
            records.append(_tally_delta(None, row))
    columns = (
        "tally_id",
        "nuclide",
        "score",
        "filter_bin",
        "left_mean",
        "right_mean",
        "delta",
        "left_std",
        "right_std",
        "status",
    )
    return _as_table(records, columns)


def _tally_delta(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    source = left or right or {}
    if left is None:
        status = "right_only"
    elif right is None:
        status = "left_only"
    else:
        status = "both"
    left_mean = None if left is None else left.get("mean")
    right_mean = None if right is None else right.get("mean")
    delta = None
    if left_mean is not None and right_mean is not None:
        delta = left_mean - right_mean
    return {
        "tally_id": source.get("tally_id"),
        "nuclide": source.get("nuclide"),
        "score": source.get("score"),
        "filter_bin": source.get("filter_bin"),
        "left_mean": left_mean,
        "right_mean": right_mean,
        "delta": delta,
        "left_std": None if left is None else left.get("std_dev"),
        "right_std": None if right is None else right.get("std_dev"),
        "status": status,
    }


def _compare_named(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> list[dict[str, Any]]:
    right_by = {row["name"]: row for row in right}
    seen = set()
    rows = []
    for row in left:
        seen.add(row["name"])
        other = right_by.get(row["name"])
        rows.append(
            {
                "name": row["name"],
                "status": "both" if other else "left_only",
                **_magnitude(
                    row.get("mean"),
                    row.get("std_dev"),
                    None if other is None else other.get("mean"),
                    None if other is None else other.get("std_dev"),
                ),
            }
        )
    for row in right:
        if row["name"] not in seen:
            rows.append(
                {
                    "name": row["name"],
                    "status": "right_only",
                    **_magnitude(None, None, row.get("mean"), row.get("std_dev")),
                }
            )
    return rows


def _magnitude(
    left: float | None,
    left_std: float | None,
    right: float | None,
    right_std: float | None,
) -> dict[str, Any]:
    delta = None if left is None or right is None else left - right
    tolerance = None
    if left_std is not None and right_std is not None:
        tolerance = math.sqrt(left_std**2 + right_std**2)
    within = None if delta is None or tolerance is None else abs(delta) <= tolerance
    return {
        "left": left,
        "right": right,
        "left_std": left_std,
        "right_std": right_std,
        "delta": delta,
        "tolerance": tolerance,
        "within_reported_uncertainty": within,
    }


def _brief(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": summary.get("path"),
        "k_eff": summary.get("k_eff"),
        "k_eff_std": summary.get("k_eff_std"),
        "n_realizations": summary.get("n_realizations"),
        "n_particles": summary.get("n_particles"),
        "n_batches": summary.get("n_batches"),
        "current_batch": summary.get("current_batch"),
    }


def _as_table(records: list[dict[str, Any]], columns: tuple[str, ...]) -> dict[str, Any]:
    return {
        "columns": list(columns),
        "rows": [[row.get(column) for column in columns] for row in records],
    }


def _finite(value: float) -> float | None:
    if math.isfinite(value):
        return float(value)
    return None


def _attr_str(node: Any, name: str) -> str | None:
    if name not in getattr(node, "attrs", {}):
        return None
    return _text(node.attrs[name])


def _attr_ints(node: Any, name: str) -> list[int]:
    if name not in node.attrs:
        return []
    value = node.attrs[name]
    if getattr(value, "shape", None) == ():
        return [int(value)]
    try:
        return [int(item) for item in value]
    except TypeError:
        return [int(value)]


def _dataset_str(node: Any, name: str) -> str | None:
    if name not in node:
        return None
    value = node[name][()]
    if getattr(value, "shape", None) not in (None, ()):
        try:
            value = next(iter(value))
        except TypeError:
            return _text(value)
    return _text(value)


def _dataset_strings(node: Any, name: str) -> list[str]:
    if name not in node:
        return []
    value = node[name][()]
    if isinstance(value, (bytes, str)):
        return [_text(value)]
    if getattr(value, "shape", None) == ():
        return [_text(value)]
    return [_text(item) for item in value]


def _dataset_int(node: Any, name: str) -> int | None:
    if name not in node:
        return None
    return int(node[name][()])


def _dataset_floats(node: Any) -> list[float]:
    value = node[()]
    if getattr(value, "shape", None) == ():
        return [float(value)]
    flat = value.reshape(-1) if hasattr(value, "reshape") else value
    return [float(item) for item in flat]


def _float_list(node: Any, name: str) -> list[float] | None:
    if name not in node:
        return None
    return _dataset_floats(node[name])


def _text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace").strip("\x00").strip()
    if isinstance(value, str):
        return value.strip("\x00").strip()
    item = value.item() if hasattr(value, "item") else value
    if isinstance(item, bytes):
        return item.decode("utf-8", "replace").strip("\x00").strip()
    return str(item).strip("\x00").strip()
