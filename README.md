[![Build Status][ci-badge]][ci-link]
[![Coverage Status][cov-badge]][cov-link]
[![Docs status][docs-badge]][docs-link]
[![PyPI version][pypi-badge]][pypi-link]

# aiida-wannierjl

An [AiiDA](https://www.aiida.net) plugin that wraps [Wannier.jl](https://github.com/qiaojunfeng/Wannier.jl) (pinned to rev `65245c59` of the `qiaojunfeng/Wannier.jl` fork, requires Julia >= 1.11) to manipulate Wannier functions from within AiiDA workflows.

Each calculation renders a small Julia driver script (`driver.jl`) and runs it against a persistent, pinned Wannier.jl project environment. The AiiDA `Code` is the Julia binary itself, so the calculations are remote-capable and provenance is tracked like any other AiiDA CalcJob. Results come back through a machine-readable `results.json` that the parsers turn into AiiDA output nodes.

## Features

The plugin provides three CalcJobs, one per Wannier.jl operation:

* **`wannierjl.check_neighbors`** (`CheckNeighborsCalculation`) — reads a wannier90 run (`.win`, `.chk`, `.mmn`, `.amn`, `.eig`) with `read_w90_with_chk` and reports whether the k-point stencil contains the six cubic nearest-neighbour b-vectors (`Wannier.has_cubic_neighbors`). Output: a `Bool` node `has_cubic_neighbors`.
* **`wannierjl.generate_neighbors`** (`GenerateNeighborsCalculation`) — writes a `cubic.nnkp` file with the six cubic b-vectors via `Wannier.write_nnkp_cubic`, so that a `.mmn` with cubic neighbours can be regenerated. Output: a `SinglefileData` node `nnkp_file`.
* **`wannierjl.split`** (`SplitCalculation`) — splits a Wannier manifold into blocks with `Wannier.Tools.mrwf`, given 1-based index groups. Outputs, under dynamic namespaces: per-block `FolderData` (`blocks.block_i`, containing `amn`/`eig`/`mmn`), the per-block `.win` files (`win_files.block_i`), and the per-block split U matrices (`u_matrices.block_i`, the `<seedname>_split.amn` files).

Input files for each CalcJob can be supplied either explicitly as `SinglefileData` ports or picked up from a parent calculation's remote working directory (`parent_folders.*` `RemoteData`), which is how the `.chk` file — not normally retrieved by upstream wannier90 plugins — is symlinked in from a wannier90 run on the same computer.

### `workflows` extra

Installing the optional `workflows` extra pulls in [aiida-workgraph](https://github.com/aiidateam/aiida-workgraph) and [aiida-quantumespresso](https://github.com/aiidateam/aiida-quantumespresso) and exposes `split_wannierization`, an `aiida-workgraph` `@task.graph` that orchestrates the full split:

```python
from aiida_wannierjl.workflows import split_wannierization
```

Set up an AiiDA profile before this import (see Installation) — an optional
dependency of the `workflows` extra loads AiiDA configuration at import time
and raises a confusing error when no profile exists yet.

It runs `check_neighbors` and, only when the cubic neighbours are missing, generates the `cubic.nnkp`, regenerates the cubic `.mmn` with a `Pw2wannier90Calculation` (forcing `write_mmn=.true.`, `write_amn=.false.`, SCDM off), and then runs `split` — all in a single invocation, with the cubic branch decided at runtime. Re-wannierization and U-matrix merging are deliberately out of scope and stay in the downstream consumer (koopmans).

## Julia environment

The Wannier.jl project environment is created once per machine, never per calculation. A helper builds the pinned project (`Pkg.add` of Wannier.jl at rev `65245c59` plus `JSON`) and, by default, a [PackageCompiler.jl](https://github.com/JuliaLang/PackageCompiler.jl) sysimage so that each calculation loads in ~0.1 s instead of paying the multi-second `using Wannier` cost on every fresh process. The sysimage path travels on the `Code` node, and the CalcJobs pick it up automatically (falling back to a plain `--project` load when no sysimage is known).

See the [get started guide](https://aiida-wannierjl.readthedocs.io/en/latest/user_guide/get_started.html) for the full setup procedure (`setup_julia_environment` and `get_wannierjl_code` in `aiida_wannierjl.helpers`).

## Installation

You need `git`, `curl` and `ps` (the `procps` package on Debian/Ubuntu) on the
machine running the code — `ps` is what the `direct` scheduler uses to tell
whether a submitted job has finished; without it AiiDA can retrieve a Julia
calculation's results before Julia has finished writing them.

```shell
pip install aiida-wannierjl[workflows]   # drop [workflows] if you don't need the workgraph
verdi presto                             # set up a new profile (SQLite, no broker)
verdi plugin list aiida.calculations     # should list the three wannierjl.* plugins
```

The `workflows` extra currently pins `aiida-workgraph`, which caps
`aiida-core` below the newest release (`aiida-core~=2.7.1` as of
aiida-workgraph 0.8.1) — expect an older `aiida-core` than a bare
`pip install aiida-core` would give you.

You also need a Julia >= 1.11 installation and the one-time environment setup
described above; [juliaup](https://github.com/JuliaLang/juliaup) is the
recommended way to install it: `curl -fsSL https://install.julialang.org | sh`.

## Usage

Once you have registered a Julia code (labelled e.g. `wannierjl@localhost`), a minimal `generate_neighbors` run looks like:

```shell
verdi daemon start     # make sure the daemon is running
cd examples
./example_01.py        # generate a cubic.nnkp from a small .win
verdi process list -a  # check the record of the calculation
```

See [`examples/example_01.py`](examples/example_01.py) for the corresponding Python.

## Development

```shell
git clone https://github.com/elinscott/aiida-wannierjl .
cd aiida-wannierjl
pip install --upgrade pip
pip install -e .[pre-commit,workflows]  # install extra dependencies
pre-commit install                      # install pre-commit hooks
pytest -v                               # discover and run all tests
```

The test suite mocks the Julia code, so it runs in CI without a real Julia installation. See the [developer guide](https://aiida-wannierjl.readthedocs.io/en/latest/developer_guide/index.html) for more information.

## Citing

If you use this plugin for your research, please cite the following work:

* J. Qiao, G. Pizzi, and N. Marzari, *Automated mixing of maximally localized Wannier functions into target manifolds*, npj Comput. Mater. **9**, 206 (2023), https://doi.org/10.1038/s41524-023-01147-9.
* J. Qiao, G. Pizzi, and N. Marzari, *Projectability disentanglement for accurate and automated electronic-structure Hamiltonians*, npj Comput. Mater. **9**, 208 (2023), https://doi.org/10.1038/s41524-023-01146-w.

See [`CITATION.cff`](CITATION.cff) (or the GitHub "Cite this repository" button) for how to cite this plugin itself.

## License

MIT

## Contact

edwardlinscott@gmail.com


[ci-badge]: https://github.com/elinscott/aiida-wannierjl/actions/workflows/ci.yml/badge.svg?branch=main
[ci-link]: https://github.com/elinscott/aiida-wannierjl/actions/workflows/ci.yml
[cov-badge]: https://codecov.io/gh/elinscott/aiida-wannierjl/branch/main/graph/badge.svg
[cov-link]: https://codecov.io/gh/elinscott/aiida-wannierjl
[docs-badge]: https://readthedocs.org/projects/aiida-wannierjl/badge
[docs-link]: http://aiida-wannierjl.readthedocs.io/
[pypi-badge]: https://badge.fury.io/py/aiida-wannierjl.svg
[pypi-link]: https://badge.fury.io/py/aiida-wannierjl
