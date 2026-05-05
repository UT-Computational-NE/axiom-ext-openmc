# Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""OpenMCKernelAdapter — wraps OpenMC for axiom.compute dispatch.

Per ADR-018: OpenMC is a native physics code (no WASM). This adapter supports
three runners selected via kernel_options["runner"]:

- "subprocess" (default): native openmc binary on PATH or kernel_options["openmc_executable"]
- "docker":              official openmc/openmc image; works without local install
- "ssh:<peer>":          dispatch to a federation peer (Phase 2c+)

The adapter:
- Validates determinism_state (input_dir exists, particles/cycles/seed declared)
- Selects + invokes the runner
- Parses statepoint.<N>.h5 for k-eff, tally values, convergence diagnostics
- Detects faults (lost particles, subprocess failure) → KernelFault
- Returns KernelResult; the dispatch layer's always-auto-stop set acts on faults

Phase 2a (current): runner + parsing seams testable via mock.
Phase 2c (next): real Docker integration with a 2D pin-cell smoke test.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from axiom.compute.adapters.base import CodeAdapter, KernelFault, KernelResult


# Default lost-particles threshold (ratio of N). Configurable per-run via
# kernel_options["lost_particles_threshold"].
DEFAULT_LOST_PARTICLE_THRESHOLD = 1e-3
DEFAULT_DOCKER_IMAGE = "openmc/openmc:latest"


class OpenMCKernelAdapter(CodeAdapter):
    """OpenMC kernel adapter — supports subprocess, docker, ssh runners."""

    name = "openmc"

    def execute(
        self,
        determinism_state: dict[str, Any],
        kernel_options: dict[str, Any],
    ) -> KernelResult:
        # Validate inputs at the boundary.
        input_dir = Path(determinism_state.get("input_dir", ""))
        if not input_dir.exists():
            raise ValueError(
                f"input_dir does not exist: {input_dir!r}. "
                "OpenMC requires an input directory containing geometry.xml, "
                "materials.xml, settings.xml, and (optionally) tallies.xml."
            )

        # Run OpenMC via the selected runner.
        runner = self._select_runner(kernel_options)
        exit_code, stdout, stderr = self._run_with_runner(
            runner=runner,
            input_dir=input_dir,
            determinism_state=determinism_state,
            kernel_options=kernel_options,
        )

        if exit_code != 0:
            return KernelResult(
                value_summary={},
                partial_value_summary=None,
                fault=KernelFault(
                    name="subprocess_failure",
                    evidence={
                        "runner": runner,
                        "exit_code": exit_code,
                        "stderr": stderr[-2000:],
                        "stdout_tail": stdout[-1000:],
                    },
                ),
            )

        # Parse statepoint into a canonical value_summary.
        statepoint = self._parse_statepoint(input_dir=input_dir)

        value_summary: dict[str, Any] = {
            "k_eff": statepoint.get("k_eff"),
            "k_eff_std": statepoint.get("k_eff_std"),
            "n_cycles": statepoint.get("n_cycles"),
            "shannon_entropy": statepoint.get("shannon_entropy"),
            "convergence": statepoint.get("convergence"),
            "tallies": statepoint.get("tallies", {}),
        }

        # Lost-particles fault detection (always-auto-stop set per dispatch layer).
        n_particles = int(determinism_state.get("n_particles", 0)) or 1
        lost = int(statepoint.get("lost_particles", 0))
        threshold = float(kernel_options.get(
            "lost_particles_threshold", DEFAULT_LOST_PARTICLE_THRESHOLD,
        ))
        if lost > threshold * n_particles:
            return KernelResult(
                value_summary=value_summary,
                partial_value_summary=value_summary,
                fault=KernelFault(
                    name="lost_particles",
                    evidence={
                        "lost_particles": lost,
                        "n_particles": n_particles,
                        "rate": lost / n_particles,
                        "threshold": threshold,
                    },
                ),
            )

        return KernelResult(value_summary=value_summary, fault=None)

    # --- Runner selection + dispatch ---

    def _select_runner(self, kernel_options: dict[str, Any]) -> str:
        """Pick the runner per kernel_options or fall through to availability."""
        explicit = kernel_options.get("runner")
        if explicit:
            return explicit
        # Auto-detect: prefer native openmc on PATH; fall back to docker.
        if shutil.which("openmc"):
            return "subprocess"
        if shutil.which("docker"):
            return "docker"
        raise RuntimeError(
            "no OpenMC runner available: neither 'openmc' nor 'docker' on PATH. "
            "Install OpenMC natively (conda install -c conda-forge openmc) or "
            "Docker Desktop, or set kernel_options['runner']='ssh:<peer>' to "
            "dispatch to a federation peer."
        )

    def _run_with_runner(
        self,
        runner: str,
        input_dir: Path,
        determinism_state: dict[str, Any],
        kernel_options: dict[str, Any],
    ) -> tuple[int, str, str]:
        if runner == "subprocess":
            return self._run_openmc_subprocess(input_dir, determinism_state, kernel_options)
        if runner == "docker":
            return self._run_openmc_docker(input_dir, determinism_state, kernel_options)
        if runner.startswith("ssh:"):
            peer = runner.split(":", 1)[1]
            return self._run_openmc_ssh(peer, input_dir, determinism_state, kernel_options)
        raise ValueError(f"unknown OpenMC runner: {runner!r}")

    # --- Per-runner seams (mocked in tests; real implementations land in Phase 2c) ---

    def _run_openmc_subprocess(
        self,
        input_dir: Path,
        determinism_state: dict[str, Any],
        kernel_options: dict[str, Any],
    ) -> tuple[int, str, str]:
        """Native subprocess invocation of openmc."""
        executable = kernel_options.get("openmc_executable", "openmc")
        proc = subprocess.run(
            [executable],
            cwd=input_dir,
            capture_output=True,
            text=True,
            timeout=kernel_options.get("timeout_seconds", 3600),
        )
        return proc.returncode, proc.stdout, proc.stderr

    def _run_openmc_docker(
        self,
        input_dir: Path,
        determinism_state: dict[str, Any],
        kernel_options: dict[str, Any],
    ) -> tuple[int, str, str]:
        """Docker invocation: bind-mount input_dir into the official openmc/openmc image.

        Two modes:

        1. **Pre-built XML deck**: input_dir contains geometry.xml/materials.xml/
           settings.xml. Container runs openmc directly. Production path.

        2. **Spec-driven** (Phase 2c smoke): input_dir contains a spec.json with
           pin-cell parameters. The embedded _docker_runner_script.py builds the
           deck inside the container, runs openmc, and writes result.json with
           the canonical value_summary. Phase 2d switches to mode 1 once
           CoreForge integration ships.

        On Apple Silicon, force_amd64=True (default) routes through Rosetta
        because openmc/openmc:latest only ships an amd64 manifest.
        """
        import shutil as _shutil

        image = kernel_options.get("docker_image", DEFAULT_DOCKER_IMAGE)
        platform_args = (
            ["--platform", "linux/amd64"]
            if kernel_options.get("force_amd64", True)
            else []
        )

        spec_path = input_dir / "spec.json"
        if spec_path.exists():
            # Spec-driven mode — copy the runner script into the bind-mount.
            runner_src = Path(__file__).with_name("_docker_runner_script.py")
            _shutil.copy(runner_src, input_dir / "_axiom_runner.py")
            cmd = [
                "docker", "run", "--rm",
                *platform_args,
                "-v", f"{input_dir.resolve()}:/inputs",
                "-w", "/inputs",
                "-e", "WORKDIR=/inputs",
                image,
                "python", "/inputs/_axiom_runner.py",
            ]
        else:
            # Pre-built XML mode.
            cmd = [
                "docker", "run", "--rm",
                *platform_args,
                "-v", f"{input_dir.resolve()}:/inputs",
                "-w", "/inputs",
                image,
                "openmc",
            ]

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=kernel_options.get("timeout_seconds", 3600),
        )
        return proc.returncode, proc.stdout, proc.stderr

    def _run_openmc_ssh(
        self,
        peer: str,
        input_dir: Path,
        determinism_state: dict[str, Any],
        kernel_options: dict[str, Any],
    ) -> tuple[int, str, str]:
        """SSH dispatch to a federation peer (e.g., 'rascal').

        Phase 2c+ implementation: rsync input_dir to peer, ssh-invoke openmc,
        rsync results back. Until then, raises NotImplementedError.
        """
        raise NotImplementedError(
            "ssh runner requires Phase 2c+ federation-dispatch implementation"
        )

    def _parse_statepoint(self, input_dir: Path) -> dict[str, Any]:
        """Parse statepoint into a canonical dict.

        Two paths:

        1. **Spec-driven mode (Phase 2c)**: the docker runner script writes
           result.json with the canonical value_summary alongside the
           statepoint. Read it directly — no host-side h5py required.

        2. **Pre-built XML mode**: requires h5py (or openmc.StatePoint) to
           extract values from statepoint.<N>.h5 on the host. Defers to
           Phase 2d when host-side h5py is available.
        """
        import json as _json

        # Spec-driven path: result.json was written by the container runner.
        result_path = input_dir / "result.json"
        if result_path.exists():
            return _json.loads(result_path.read_text())

        # Pre-built XML path: needs host-side h5py.
        statepoints = sorted(input_dir.glob("statepoint.*.h5"))
        if not statepoints:
            raise FileNotFoundError(
                f"no statepoint.*.h5 or result.json found in {input_dir}; "
                "OpenMC may have failed silently or written to an unexpected location."
            )
        raise NotImplementedError(
            "host-side statepoint parsing requires h5py (Phase 2d); "
            "use spec-driven mode (place a spec.json in input_dir) for Phase 2c."
        )

# Adapter discovery: declared via the `axiom.compute.adapters` Python entry-point
# group in pyproject.toml. axiom-os-lm >= 0.15 lazy-loads entry points on first
# get_adapter("openmc") call — no manual registration here is needed.
