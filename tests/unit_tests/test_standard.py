# Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""AEOS standard tests for the OpenMC extension.

Inherits the published base classes. This file's path is the one
``axi ext lint`` looks for (AEOS §8.2).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axiom_tests.unit_tests import AdapterTests, ExtensionStandardTests, SkillTests

_ROOT = Path(__file__).resolve().parents[2]
_SKILLS = _ROOT / "axiom_ext_openmc" / "skills"


class TestOpenMCExtension(ExtensionStandardTests):
    """Layout, manifest schema, required files, public API."""

    @pytest.fixture
    def extension_manifest_path(self) -> Path:
        return _ROOT / "axiom-extension.toml"

    @property
    def require_docs_dir(self) -> bool:
        # Adapter plus skills is more than one capability kind (AEOS §5.3).
        return True


class TestOpenMCAdapter(AdapterTests):
    @pytest.fixture
    def adapter_class(self):
        from axiom_ext_openmc.adapters.openmc import OpenMCKernelAdapter

        return OpenMCKernelAdapter

    @pytest.fixture
    def adapter_manifest_block(self) -> dict:
        import tomllib

        manifest = tomllib.loads((_ROOT / "axiom-extension.toml").read_text())
        for block in manifest["extension"]["provides"]:
            if block.get("kind") == "adapter":
                return block
        raise AssertionError("manifest has no adapter block")

    @property
    def auth_methods(self) -> tuple[str, ...]:
        return ("none",)

    @property
    def capabilities(self) -> tuple[str, ...]:
        return ("execute", "subprocess", "docker")


class _OpenMCSkill(SkillTests):
    skill_dir = ""

    @pytest.fixture
    def skill_path(self) -> Path:
        return _SKILLS / self.skill_dir


class TestCheckRunnerSkill(_OpenMCSkill):
    skill_dir = "check_runner"


class TestListCasesSkill(_OpenMCSkill):
    skill_dir = "list_cases"


class TestParseSummarySkill(_OpenMCSkill):
    skill_dir = "parse_summary"


class TestRunInputSkill(_OpenMCSkill):
    skill_dir = "run_input"


class TestGradeSkill(_OpenMCSkill):
    skill_dir = "grade"


class TestValidateSkill(_OpenMCSkill):
    skill_dir = "validate"


class TestShowSkill(_OpenMCSkill):
    skill_dir = "show"


class TestStatSkill(_OpenMCSkill):
    skill_dir = "stat"


class TestDiffSkill(_OpenMCSkill):
    skill_dir = "diff"


class TestCheckSkill(_OpenMCSkill):
    skill_dir = "check"


class TestReviewSkill(_OpenMCSkill):
    skill_dir = "review"
