# axiom-ext-openmc

**OpenMC physics-code extension for the [Axiom](https://github.com/b-tree-labs/axiom-os) platform.**
Apache-2.0 · AEOS-conformant · works with or without Axiom present.

Per ADR-018 ("each physics code is its own AEOS-conformant Axiom extension; physics = native") and ADR-044 ("standalone-or-builtin extension distribution"), this package is the standalone wrapper that lets [OpenMC](https://openmc.org/) participate in Axiom's federated compute primitives — without changing how OpenMC is normally used.

## What this package is, and is not

| It IS | It IS NOT |
|---|---|
| A thin Python wrapper that exposes OpenMC as an Axiom `CodeAdapter` | A redistribution of OpenMC (you install OpenMC separately) |
| Discoverable by `axiom.compute.adapters.get_adapter("openmc")` after `pip install` (no manual import) | A replacement for OpenMC's CLI or Python API |
| A bridge for `axi model run` / federated dispatch + signed-receipt provenance | A required dependency for traditional OpenMC use |
| Apache-2.0 (this wrapper); MIT (OpenMC itself, separately installed) | A change to OpenMC's behavior — the wrapper does not shadow `openmc.*` |

If you've never used Axiom and only want OpenMC, you don't need this package. If you have OpenMC installed and want it to compose with Axiom's federation, dispatch, and signed-receipt primitives, install this package and the rest is automatic.

## Install

```bash
pip install axiom-ext-openmc
```

This installs the **adapter Python code only**. The OpenMC engine itself is a separate install — pick one of:

| Form | Install | Notes |
|---|---|---|
| **Native** (recommended for daily use) | `conda install -c conda-forge openmc` | Fastest; full Python API + CLI |
| **Docker** (no native install required) | `docker pull openmc/openmc:latest` | Adapter pulls automatically when no native binary is found |
| **SSH peer** (Axiom federation) | install OpenMC on a peer; the adapter dispatches via SSH | Laptop-orchestrated, peer-executed |

The adapter auto-detects what's available; force a runner with `kernel_options["runner"] = "subprocess" | "docker" | "ssh:<peer>"`.

## Use

### Traditional OpenMC — completely unchanged

The wrapper is non-shadowing. If you have OpenMC installed natively, this is unaffected:

```python
import openmc
openmc.run()  # works exactly as it always did
```

```bash
openmc -i geometry.xml -i materials.xml -i settings.xml
```

### Axiom-routed dispatch — the bonus path

After `pip install axiom-ext-openmc`, the OpenMC adapter is discoverable from Axiom without any manual import:

```python
from axiom.compute import dispatch, DispatchSpec

result = dispatch(DispatchSpec(
    model_id="my-model",
    composition_hash="sha256:...",
    kernel="openmc",          # discovered via importlib.metadata entry points
    peer_id="laptop",
    determinism_class="D-bit",
    determinism_state={
        "input_dir": "/path/to/openmc-input/",
        "n_particles": 100_000,
        "n_active_cycles": 50,
        "n_inactive_cycles": 20,
        "rng_seed": 42,
        "xs_library": "ENDF/B-VIII.0",
    },
    kernel_options={"runner": "docker"},  # or "subprocess" / "ssh:<peer>"
))
print(result.value_summary["k_eff"])
```

CLI surface (via Axiom or NeutronOS):

```bash
# From any Axiom-enabled CLI:
axi model run my-model --on local:openmc --tail

# Or NeutronOS:
neut model run my-model --on local:openmc --tail
```

## What's in the box

- `axiom_ext_openmc.adapter:OpenMCKernelAdapter` — the `CodeAdapter` implementation, registered via `[project.entry-points."axiom.compute.adapters"]`
- `axiom_ext_openmc.references` — published reference k-eff/tally values (initially: ORNL TM-728 MSR references, Phase 5)
- `axiom_ext_openmc.facility_packs/` — facility-specific OpenMC templates (Phase 2c+)
- `axiom_ext_openmc.skills/` — MCP-callable tools for LLM-mediated input authoring + output parsing (Phase 2c+)
- `axiom_ext_openmc._docker_runner_script` — self-contained script bind-mounted into the openmc/openmc container

## Versioning + compatibility

- Python: 3.11+
- `axiom-os-lm` >= 0.15.0 (entry-point discovery for adapters lands in this version)
- OpenMC: any version compatible with the conda-forge build OR `openmc/openmc:latest` Docker image

This package follows semver. Minor-version bumps may add new runners, references, or facility packs. Major-version bumps would change the `OpenMCKernelAdapter` interface.

## Development

```bash
git clone https://github.com/UT-Computational-NE/axiom-ext-openmc.git
cd axiom-ext-openmc
pip install -e ".[test]"
pytest -q                    # unit tests
pytest -m docker -v          # opt-in Phase 2c smoke (requires Docker + openmc/openmc image)
```

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

This package is jointly copyrighted by The University of Texas at Austin and B-Tree Labs.

## Architecture references

- [ADR-018](https://github.com/b-tree-labs/axiom-os/blob/main/docs/adrs/adr-018-physics-code-extensions.md) — Each physics code is its own AEOS-conformant extension; physics = native.
- [ADR-040](https://github.com/b-tree-labs/axiom-os/blob/main/docs/adrs/adr-040-compute-decomposition.md) — Compute decomposition primitive (this adapter is one consumer).
- [ADR-044](https://github.com/b-tree-labs/axiom-os/blob/main/docs/adrs/adr-044-extension-distribution-model.md) — Standalone-or-builtin extension distribution rule (this package is a standalone case).

## Related projects

- [Axiom](https://github.com/b-tree-labs/axiom-os) — the platform this package extends
- [NeutronOS](https://github.com/UT-Computational-NE/neutron-os-core) — nuclear-domain consumer that includes this package as an optional dependency
- [OpenMC](https://github.com/openmc-dev/openmc) — the physics code wrapped here (separately installed)
