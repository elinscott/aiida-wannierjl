===============
Getting started
===============

``aiida-wannierjl`` wraps a small set of `Wannier.jl
<https://github.com/qiaojunfeng/Wannier.jl>`_ operations as AiiDA CalcJobs:

* ``wannierjl.check_neighbors`` — test whether a wannierisation has cubic
  b-vector neighbours;
* ``wannierjl.generate_neighbors`` — write a cubic ``.nnkp`` file;
* ``wannierjl.split`` — split a wannierisation into blocks (``mrwf``).

Each CalcJob renders a Julia driver script and runs it against a persistent,
pinned Wannier.jl project environment. The AiiDA ``Code`` is the ``julia``
binary itself; the project is selected through the ``JULIA_PROJECT`` environment
variable.

Installation
++++++++++++

Install the plugin (add the ``workflows`` extra for the aiida-workgraph split
orchestration and the aiida-quantumespresso dependency it needs)::

    git clone https://github.com/elinscott/aiida-wannierjl .
    cd aiida-wannierjl
    pip install -e .            # core plugin
    pip install -e .[workflows] # + aiida-workgraph, aiida-quantumespresso
    verdi plugin list aiida.calculations  # should list the three wannierjl entries

One-time Julia environment setup
++++++++++++++++++++++++++++++++

The Wannier.jl project is created **once per machine**, never per calculation.
It requires **julia >= 1.11**.

On a machine where you can run Python, use the helper::

    from aiida_wannierjl.helpers import setup_julia_environment

    sysimage_path = setup_julia_environment(
        julia_exe="/usr/local/bin/julia",
        project_dir="/home/me/.julia-wannierjl",
    )

This installs the pinned Wannier.jl + JSON stack and, by default, builds a
PackageCompiler sysimage (``<project_dir>/wannierjl.so``). The sysimage cuts the
per-calculation ``using Wannier`` cost from several seconds to about 0.1 s.
Pass ``sysimage=False`` to skip it (e.g. for debugging or unsupported
platforms); CalcJobs then fall back to a plain ``--project`` load.

On a **remote** machine, copy the two packaged scripts
(``src/aiida_wannierjl/julia/install_wannierjl.jl`` and ``build_sysimage.jl``)
to the machine and run the same commands by hand::

    julia --startup-file=no --project=<project_dir> install_wannierjl.jl
    julia --startup-file=no --project=<project_dir> \
        -e 'using Pkg; Pkg.add("PackageCompiler")'
    julia --startup-file=no --project=<project_dir> \
        build_sysimage.jl <project_dir>/wannierjl.so

.. note::

   The sysimage bakes in the exact package versions present when it was built.
   After upgrading Wannier.jl (rerun ``install_wannierjl.jl``) you **must**
   rebuild the sysimage, otherwise calculations keep loading the stale
   baked-in code.

Registering the Code
++++++++++++++++++++

The easiest route is the helper, which stores the sysimage path on the Code so
the CalcJobs pick it up automatically::

    from aiida.orm import load_computer
    from aiida_wannierjl.helpers import get_wannierjl_code

    code = get_wannierjl_code(
        label="wannierjl",
        computer=load_computer("localhost"),
        julia_exe="/usr/local/bin/julia",
        project_dir="/home/me/.julia-wannierjl",
        sysimage_path=sysimage_path,
    )

Equivalently, create an installed Code from the command line and point
``JULIA_PROJECT`` at the environment in the prepend text::

    verdi code create core.code.installed \
        --label wannierjl \
        --computer localhost \
        --filepath-executable /usr/local/bin/julia \
        --default-calc-job-plugin wannierjl.check_neighbors \
        --prepend-text 'export JULIA_PROJECT=/home/me/.julia-wannierjl'

If you register the Code this way, set the sysimage path yourself so the base
CalcJob can add ``--sysimage``::

    code.base.extras.set("sysimage_path", "/home/me/.julia-wannierjl/wannierjl.so")

Minimal usage
+++++++++++++

Generate a cubic ``.nnkp`` from a ``.win`` file::

    from aiida.engine import run
    from aiida.orm import SinglefileData, load_code
    from aiida_wannierjl.calculations.generate_neighbors import (
        GenerateNeighborsCalculation,
    )

    builder = GenerateNeighborsCalculation.get_builder()
    builder.code = load_code("wannierjl@localhost")
    builder.win_file = SinglefileData("/path/to/aiida.win")

    results = run(builder)
    nnkp = results["nnkp_file"]  # SinglefileData holding cubic.nnkp

For the full check → (generate + cubic pw2wannier90) → split flow, see
``aiida_wannierjl.workflows.split_wannierization`` (requires the ``workflows``
extra).
