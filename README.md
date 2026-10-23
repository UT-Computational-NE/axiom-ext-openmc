# axiom-ext-openmc

This is the OpenMC extension for [Axiom](https://github.com/b-tree-labs/axiom-os). It is a standalone [AEOS](https://github.com/b-tree-labs/axiom-os/blob/main/docs/specs/spec-aeos-0.1.md) package: one manifest, one Python library, and a small toolkit of skills that call that library.

Install OpenMC itself separately (`conda` or the `openmc/openmc` image). This package does not redistribute OpenMC, and importing it does not replace `import openmc`.

Apache-2.0. Python 3.11+. The manifest declares AEOS 0.1.0, the governing spec. Chain level A is claimed. The 0.2 chain-readiness text is a draft amendment inside that spec; claiming chain level C would require `aeos_version >= 0.2`, so this package does not claim it. `axi ext lint` notes that the shipped recipe would score C (AEOS103). Package version 0.2.0 is this extension's semver, not the AEOS version. AEOS 1.0 is a draft and is not claimed here.

## What you can do with it

Three things, all aimed at an input directory that already contains an OpenMC deck:

1. **Run it through Axiom.** `axiom.compute.dispatch` loads `OpenMCKernelAdapter` from the `axiom.compute.adapters` entry point when `kernel` is `"openmc"`. The adapter runs `openmc` in that directory, or `docker run openmc/openmc` when you ask for Docker. It returns a `KernelResult` whose `value_summary` carries `k_eff` and `k_eff_std`.
2. **Call the library.** `runner_status`, `list_cases`, `validate_model`, `summarize_model`, `read_statepoint`, `compare_statepoints`, `check_cross_sections`, `plan_run`, `parse_summary`, `run_input`, and `grade` are plain functions. `run_input`, `parse_summary`, and `plan_run` import the adapter when called. `read_statepoint` imports h5py when called.
3. **Call the toolkit.** The same functions are skills (`openmc.check_runner`, `openmc.list_cases`, `openmc.parse_summary`, `openmc.run_input`, `openmc.grade`, `openmc.validate`, `openmc.show`, `openmc.stat`, `openmc.diff`, `openmc.check`, `openmc.review`) and the `axiom-openmc` verbs `validate`, `show`, `stat`, `diff`, `check`, and `review`. Skills with `surfaces` including `mcp` are the MCP tools; the platform projector names them. This package does not keep a second tool schema. `skills.bind(registry)` registers them on Axiom's `SkillRegistry`. The recipe `grade-a-run` is the order an agent follows: check the machine, list the ladder, run one directory, grade k-eff.

The verification ladder builds three decks (infinite UO2 medium, a pin cell, a 17×17 assembly) so a real OpenMC run can be told apart from a mock. Reference values shipped today are provisional placeholders. `grade` reports `provisional` and does not report agreement until a reviewer replaces the number and clears the flag. A URI with no reference reports `no_reference`.

## Components

```mermaid
flowchart TB
  manifest["axiom-extension.toml"]

  subgraph declared["Capabilities the manifest declares"]
    direction TB
    capAdapter["adapter · integration openmc"]
    capSkills["skills · openmc.* verbs, including inspect"]
    capCmd["cmd · axiom-openmc"]
    capRecipe["recipe · grade-a-run"]
  end

  subgraph code["Code those capabilities call"]
    direction TB
    skills["skills.bind · SkillSpec per verb"]
    cli["axiom-openmc · validate show stat diff check review"]
    library["library.py"]
    reader["statepoint.py · one HDF5 reader"]
    adapter["OpenMCKernelAdapter"]
    ladder["verification · three cases"]
    refs["references · provisional until reviewed"]
  end

  manifest --> capAdapter
  manifest --> capSkills
  manifest --> capCmd
  manifest --> capRecipe
  capAdapter --> adapter
  capSkills --> skills
  capCmd --> cli
  capRecipe --> skills
  skills --> library
  cli --> library
  library --> adapter
  library --> reader
  adapter --> reader
  library --> ladder
  library --> refs

  classDef paper fill:#e3f2fd,stroke:#1565c0,color:#333
  classDef decl fill:#fff8e1,stroke:#f9a825,color:#333
  classDef impl fill:#e8f5e9,stroke:#2e7d32,color:#333
  class manifest paper
  class capAdapter,capSkills,capCmd,capRecipe decl
  class skills,cli,library,reader,adapter,ladder,refs impl
```

`library.grade` reads the reference modules and applies the provisional rule. `library.list_cases` reads the ladder and does not import OpenMC. `library.runner_status` reports the OpenMC Python package, `OPENMC_CROSS_SECTIONS`, the `openmc` binary, and `docker` as separate facts. `library.run_input` calls `OpenMCKernelAdapter.execute`. `library.parse_summary` calls the adapter's statepoint parser. A `result.json` is that summary. Otherwise the adapter calls `statepoint.read_statepoint`, which is also what `read_statepoint`, `axiom-openmc stat`, and `openmc.stat` call. k-eff is the file's `k_combined` dataset. Tally tables reduce the stored sum and sum of squares. h5py is optional; without it the reader names the `statepoint` extra and does not invent a summary.

The adapter selects a runner from `kernel_options["runner"]`, or from what is on `PATH` (`openmc`, then `docker`). `ssh:<peer>` is recognized and raises `NotImplementedError`. It does not open a session. `connect` reports that.

## Where it sits in Axiom and AEOS

```mermaid
flowchart TB
  subgraph aeos["AEOS 0.1.0, chain level A claimed"]
    direction TB
    spec["spec-aeos-0.1.md · chain section 4.11"]
    lint["axi ext lint · axi ext validate"]
    man["axiom-extension.toml · aeos_version 0.1.0 · chain A claimed"]
  end

  subgraph runtime["Axiom runtime"]
    direction TB
    dispatch["axiom.compute.dispatch · kernel openmc"]
    entry["entry point axiom.compute.adapters"]
    aeosEntry["entry point axiom.adapters"]
    registry["SkillRegistry"]
    project["projector · mcp, and cli where declared"]
  end

  subgraph pkg["axiom_ext_openmc"]
    direction TB
    ad["OpenMCKernelAdapter.execute"]
    sk["skills · run, grade, and inspect"]
    cmd["axiom-openmc"]
    lb["library"]
  end

  subgraph engine["OpenMC, installed separately"]
    direction TB
    native["subprocess · openmc in the input directory"]
    image["docker run openmc/openmc"]
  end

  spec --> man
  lint --> man
  man --> ad
  man --> sk
  man --> cmd
  dispatch --> entry --> ad
  man --> aeosEntry --> ad
  registry --> sk --> lb --> ad
  cmd --> lb
  sk --> project
  ad --> native
  ad --> image

  classDef std fill:#ede7f6,stroke:#4527a0,color:#333
  classDef run fill:#e3f2fd,stroke:#1565c0,color:#333
  classDef box fill:#e8f5e9,stroke:#2e7d32,color:#333
  classDef eng fill:#fff3e0,stroke:#ef6c00,color:#333
  class spec,lint,man std
  class dispatch,entry,aeosEntry,registry,project run
  class ad,sk,cmd,lb box
  class native,image eng
```

AEOS is the manifest, the layout, and the conformance tests (`tests/unit_tests/test_standard.py` inherits `axiom_tests`). The runtime loads `axiom.compute.adapters` for `get_adapter("openmc")` and dispatch, `axiom.adapters` for `axi ext validate`, and `axiom.commands` for the `openmc` noun (`build_parser`). `bind` registers skills when `axiom.infra.skills` imports. Run and grade skills declare `surfaces = ["mcp", "skill_md"]`. The inspect skills also declare `cli`. The platform projector turns that declaration into an MCP tool (and a CLI verb where `cli` is listed). `axiom-openmc` is the same verbs calling the library. This package does not hand-write a second MCP schema.

Dispatch signs the completed result. This package returns the `KernelResult` dispatch signs. A `lost_particles` fault is in dispatch's always-auto-stop set. A non-zero OpenMC exit is a `subprocess_failure` fault on that result.

The extension declares `federation.shareable = false`. It does not implement attestation or quarantine. The publish workflow does not yet Sigstore-sign the wheel. The manifest says a published release requires that signature.

## Install

```bash
pip install axiom-ext-openmc
```

That installs this package and its dependency on `axiom-os-lm`. OpenMC is separate:

| How you run | What you install |
|---|---|
| Native binary | `conda install -c conda-forge openmc`, and set `OPENMC_CROSS_SECTIONS` to a data library from [openmc.org/data](https://openmc.org/data/) |
| Container | Docker, and the image `openmc/openmc:latest` (`docker run` pulls it when it is absent). On Apple Silicon the adapter passes `--platform linux/amd64` |

`kernel_options["runner"]` is `"subprocess"` or `"docker"`. Omit it and the adapter uses `openmc` on `PATH` when it finds it, otherwise `docker`.

## Use

### Library

```python
from axiom_ext_openmc import grade, list_cases, runner_status

print(runner_status())
for case in list_cases():
    print(case["name"], case["reference_uri"], case["n_particles"])

result = grade("reference://verification/infinite-medium-uo2/k-eff", k_eff=1.02)
# result["status"] == "provisional" and result["agrees"] is None
```

`run_input` needs the counts the case declares. Pass those counts. The function has no second default.

```python
from axiom_ext_openmc import list_cases, run_input

case = next(c for c in list_cases() if c["name"] == "infinite_medium_uo2")
outcome = run_input(
    "/path/to/prepared-deck",
    n_particles=case["n_particles"],
    n_active_cycles=case["n_active_cycles"],
    n_inactive_cycles=case["n_inactive_cycles"],
    rng_seed=case["rng_seed"],
    kernel_options={"runner": "subprocess"},
)
print(outcome.value_summary["k_eff"])
```

The verification builders write a deck when OpenMC's Python API is importable. `verification.runner.run_case` builds one case into a directory and then calls the same adapter.

### Toolkit

```python
from axiom.infra.skills import SkillRegistry
from axiom_ext_openmc.skills import bind

registry = SkillRegistry()
bind(registry)  # run/grade skills, plus validate, show, stat, diff, check, review
```

`grade-a-run` (`axiom_ext_openmc/recipes/grade-a-run.toml`) is data. An agent runs each step through the registry. The recipe does not execute OpenMC by itself.

### Command line

`axiom-openmc` calls the library. It does not start a solve. `review` is the dry run (`executed` is false). `stat` and `diff` need the optional `statepoint` extra (`pip install 'axiom-ext-openmc[statepoint]'`), which is h5py and not OpenMC.

```bash
axiom-openmc validate ./deck
axiom-openmc show ./deck
axiom-openmc check --model ./deck
axiom-openmc review ./deck
axiom-openmc stat ./statepoint.10.h5
axiom-openmc diff ./a/statepoint.10.h5 ./b/statepoint.10.h5
```

`stat` prints the k-eff stored in `k_combined` and a tally table reduced from the file's sum and sum of squares. `diff` subtracts those reported values. Neither result is a published reference, and `grade` is still the only function that consults `references/`.

### Dispatch

```python
from axiom.compute import dispatch, DispatchSpec

result = dispatch(DispatchSpec(
    model_id="my-model",
    composition_hash="sha256:...",
    kernel="openmc",
    peer_id="laptop",
    determinism_class="D-bit",
    determinism_state={
        "input_dir": "/path/to/openmc-input/",
        "n_particles": 1000,
        "n_active_cycles": 10,
        "n_inactive_cycles": 5,
        "rng_seed": 1,
    },
    kernel_options={"runner": "subprocess"},
))
print(result.value_summary["k_eff"])
```

`axi model run my-model --on local:openmc` is the CLI onto that same kernel name.

A traditional OpenMC process is unchanged: run `openmc` in a directory that holds `geometry.xml`, `materials.xml`, and `settings.xml`.

## Layout

```
axiom-extension.toml          AEOS manifest
axiom_ext_openmc/
  library.py                  public functions
  inputs.py                   XML checks and cross-section index
  statepoint.py               the one HDF5 statepoint reader
  adapter.py                  OpenMCKernelAdapter
  adapters/openmc.py          AEOS entry, same class
  commands/openmc/            axiom-openmc verbs
  skills/                     toolkit and SKILL.md files
  recipes/grade-a-run.toml
  verification/               ladder, availability, runner
  references/                 provisional reference specs
tests/unit_tests/test_standard.py
```

## Development

```bash
git clone https://github.com/UT-Computational-NE/axiom-ext-openmc.git
cd axiom-ext-openmc
pip install -e ".[test]"    # includes h5py for statepoint fixtures
pytest -q -m "not docker"
pytest -m docker -v    # needs Docker and openmc/openmc
```

`axi ext lint` compares the directory name to the manifest name with no hyphen folding. The manifest name is `axiom_ext_openmc`. A clone of this repository is named `axiom-ext-openmc`, so point lint at a directory with the manifest's name. Details are in [docs/specs/spec.md](docs/specs/spec.md).

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE). Copyright The University of Texas at Austin and B-Tree Labs.

Rungs 2 and 3 of the ladder are adapted from Harrison Reisinger's OpenMC Crash Course, MIT licensed. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## References

- [ADR-018](https://github.com/b-tree-labs/axiom-os/blob/main/docs/adrs/adr-018-physics-code-extensions.md) — a physics code is its own AEOS extension.
- [ADR-040](https://github.com/b-tree-labs/axiom-os/blob/main/docs/adrs/adr-040-compute-decomposition.md) — compute decomposition. This adapter is one kernel.
- [ADR-044](https://github.com/b-tree-labs/axiom-os/blob/main/docs/adrs/adr-044-extension-distribution-model.md) — this package is the standalone distribution.
- [OpenMC](https://github.com/openmc-dev/openmc) — the code this extension runs.
- [NeutronOS](https://github.com/UT-Computational-NE/neutron-os-core) — a nuclear-domain consumer of this package.
