# Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""Run the platform's own conformance commands against a correctly named directory.

``axi ext lint`` resolves the path and then compares that directory's name to
the manifest name (AEOS030). A GitHub checkout is named ``axiom-ext-openmc``,
which the manifest schema rejects. The extension content is linted here
through a real directory named ``axiom_ext_openmc``.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_IGNORE = shutil.ignore_patterns(
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "*.pyc",
    ".pytest_cache",
    "dist",
    "*.egg-info",
    ".ruff_cache",
)


def _axi(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    bindir = str(Path(sys.executable).parent)
    env["PATH"] = bindir + os.pathsep + env.get("PATH", "")
    return subprocess.run(
        ["axi", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture(scope="module")
def extension_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    dest = tmp_path_factory.mktemp("lint") / "axiom_ext_openmc"
    shutil.copytree(_ROOT, dest, ignore=_IGNORE)
    return dest


def test_ext_lint_has_no_errors(extension_dir: Path):
    proc = _axi("ext", "lint", str(extension_dir), "--json", cwd=extension_dir)
    payload = json.loads(proc.stdout)
    errors = [item for item in payload["findings"] if item["severity"] == "error"]
    assert proc.returncode == 0, json.dumps(errors, indent=2)
    assert errors == []
    # Governing AEOS is 0.1.0. The draft amendment's AEOS101 says a claim
    # above A needs aeos_version >= 0.2, so this manifest claims A. The
    # shipped recipe still scores C; AEOS103 records that conflict and is
    # not an error.
    assert payload["chain"]["claimed"] == "A"
    assert payload["chain"]["achieved"] == "C"
    notes = payload["chain"].get("notes") or []
    assert any(note.get("code") == "AEOS103" for note in notes)


def test_ext_validate_passes(extension_dir: Path):
    proc = _axi("ext", "validate", str(extension_dir), "--json", cwd=extension_dir)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    if proc.stdout.strip().startswith("{") or proc.stdout.strip().startswith("["):
        payload = json.loads(proc.stdout)
        failures = []
        rows = payload if isinstance(payload, list) else payload.get("results", payload.get("checks", []))
        if isinstance(rows, list):
            failures = [row for row in rows if isinstance(row, dict) and row.get("ok") is False]
        assert failures == [], json.dumps(failures, indent=2)
