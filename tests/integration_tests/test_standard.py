# Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""Integration-level AEOS checks: the package imports and manifest entries resolve."""

from __future__ import annotations

from pathlib import Path

import pytest

from axiom_tests.integration_tests import ExtensionIntegrationTests

_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.integration
class TestOpenMCExtensionIntegration(ExtensionIntegrationTests):
    @pytest.fixture
    def extension_manifest_path(self) -> Path:
        return _ROOT / "axiom-extension.toml"

    @property
    def require_docs_dir(self) -> bool:
        return True
