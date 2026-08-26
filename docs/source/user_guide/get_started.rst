===============
Getting started
===============

``aiida-wannierjl`` wraps `Wannier.jl <https://github.com/qiaojunfeng/Wannier.jl>`_'s
manifold splitting as an AiiDA CalcJob, ``wannierjl.split``, which cuts a
Wannier manifold into disjoint blocks (``Wannier.Tools.mrwf``) so each block
can be re-wannierised on its own. With the ``workflows`` extra installed, the
``split_wannierization`` workgraph orchestrates a full run, from a completed
wannier90 calculation to per-block outputs.

The split needs the wannierisation's k-point stencil to hold six cubic
nearest-neighbour b-vectors. Two supporting CalcJobs, ``wannierjl.check_neighbors``
and ``wannierjl.generate_neighbors``, detect and, if needed, supply that
stencil; ``split_wannierization`` drives them automatically, so most users
never call them directly (see the tutorial's fallback section).

Each CalcJob renders a Julia driver script and runs it against a persistent,
pinned Wannier.jl project environment. The AiiDA ``Code`` is the ``julia``
binary itself; the project is selected through the ``JULIA_PROJECT`` environment
variable.

Installation
++++++++++++

You need ``git`` on the machine running the code (for the Julia install
below), and ``ps`` (the ``procps`` package on Debian/Ubuntu): the ``direct``
scheduler polls it to tell whether a submitted job has finished, and without
it AiiDA can retrieve a Julia calculation's results before Julia has finished
writing them.

Install ``aiida-wannierjl`` from PyPI (add the ``workflows`` extra for the
aiida-workgraph split orchestration and the aiida-quantumespresso dependency
it needs)::

    pip install aiida-wannierjl            # core plugin
    pip install aiida-wannierjl[workflows] # + aiida-workgraph, aiida-quantumespresso
    verdi plugin list aiida.calculations   # should list the three wannierjl entries

For development, clone the repository and install it editable instead:
``git clone https://github.com/elinscott/aiida-wannierjl && cd aiida-wannierjl
&& pip install -e .[workflows]``.

Setting up an AiiDA profile
+++++++++++++++++++++++++++

If you don't already have an AiiDA profile, the quickest way to get one is::

    verdi presto

This creates a standalone profile backed by SQLite, with no broker or
PostgreSQL setup required. See the `AiiDA documentation
<https://aiida.readthedocs.io/projects/aiida-core/en/stable/installation/index.html>`_
for other setup routes (a full PostgreSQL/RabbitMQ profile, remote
computers, and so on). Set up a profile before importing
``aiida_wannierjl.workflows``: an optional dependency of the ``workflows``
extra loads AiiDA configuration at import time and raises a confusing error
when no profile exists yet.

One-time Julia environment setup
++++++++++++++++++++++++++++++++

The Wannier.jl project is created **once per machine**, never per calculation.
It requires **julia >= 1.11**. The recommended way to install Julia is
`juliaup <https://github.com/JuliaLang/juliaup>`_::

    curl -fsSL https://install.julialang.org | sh

juliaup installs and manages the current Julia release; see its README for
alternatives (e.g. non-interactive installs, other platforms).

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

Once the code is registered, the quickest way to check the setup end to end
is ``wannierjl.generate_neighbors``: it only needs a ``.win`` file, so it
exercises the Julia driver without a full wannier90 run to hand. See
:doc:`tutorial`'s fallback section for a runnable example, and the rest of
the tutorial for the split workflow this setup is for.
