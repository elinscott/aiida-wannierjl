========
Tutorial
========

This tutorial leads with :func:`~aiida_wannierjl.workflows.split.split_wannierization`,
the workgraph that turns a completed wannier90 run into per-block Wannier
manifolds, then shows the bare ``wannierjl.split`` CalcJob it wraps, for users
who want to drive that one step themselves. It assumes you have already set up
a Julia code (see :doc:`get_started`) and have a completed wannier90 run to
work from. The examples load each calculation through its entry point, so
nothing here depends on the package layout.

The split_wannierization workgraph
+++++++++++++++++++++++++++++++++++

With the ``workflows`` extra installed (``pip install aiida-wannierjl[workflows]``),
:func:`~aiida_wannierjl.workflows.split.split_wannierization` chains everything needed to
go from a completed wannier90 run to per-block outputs in a single call. It
checks whether the wannierisation already has cubic nearest-neighbour
b-vectors and, only if it does not, regenerates the ``.mmn`` with the cubic
stencil before splitting -- the branch is decided at runtime, so you do not
need to check this yourself:

.. code-block:: python

    from aiida_workgraph import WorkGraph
    from aiida.orm import SinglefileData, load_code
    from aiida_wannierjl.workflows import split_wannierization

    with WorkGraph() as wg:
        outputs = split_wannierization(
            wjl_code=load_code("wannierjl@localhost"),
            win_file=SinglefileData("aiida.win"),
            groups=[[1, 2], [3, 4]],
            wannier90_parent=wannier90_remote_folder,
            pw2wannier90_parent=pw2wannier90_remote_folder,
            nscf_parent=nscf_remote_folder,          # only used if the cubic branch triggers
            pw2wannier90_code=load_code("pw2wannier90@localhost"),
        )
    wg.run()

    has_cubic = outputs.has_cubic_neighbors.value  # a Bool node
    blocks = outputs.blocks          # namespace of per-block FolderData (amn/eig/mmn)
    u_matrices = outputs.u_matrices  # namespace of per-block <seedname>_split.amn

``groups`` is a list of 1-based Wannier-function index groups, one per output
block -- ``[[1, 2], [3, 4]]`` splits a four-function manifold into two pairs.
``wannier90_parent`` and ``pw2wannier90_parent`` are the ``RemoteData`` working
directories of the preceding wannier90.x and pw2wannier90.x runs (an explicit
``chk_file``/``amn_file``/``mmn_file``/``eig_file`` works too, in place of
either parent). The downstream re-wannierisation and U-matrix merge of each
block are left to the consumer -- they are out of scope for this workgraph.

The wannierjl.split CalcJob
++++++++++++++++++++++++++++

For direct control over the single split step -- skipping the cubic-neighbour
check and any workgraph orchestration -- call ``wannierjl.split`` on its own.
It runs ``Wannier.Tools.mrwf`` and needs the same Wannier90 file set as
``check_neighbors`` (below), plus ``indices``: the same 1-based index groups
as ``split_wannierization``'s ``groups``. When the wannierisation lacks cubic
neighbours, pass the cubic ``.mmn`` explicitly through ``cubic_mmn_file`` or
``parent_folders.pw2wannier90_cubic``:

.. code-block:: python

    from aiida.engine import run_get_node
    from aiida.orm import List, SinglefileData, load_code
    from aiida.plugins import CalculationFactory

    Split = CalculationFactory("wannierjl.split")

    results, node = run_get_node(
        Split,
        code=load_code("wannierjl@localhost"),
        win_file=SinglefileData("aiida.win"),
        indices=List([[1, 2], [3, 4]]),
        parent_folders={
            "wannier90": wannier90_remote_folder,
            "pw2wannier90": pw2wannier90_remote_folder,
        },
    )

    blocks = results["blocks"]          # namespace of FolderData (amn/eig/mmn per block)
    u_matrices = results["u_matrices"]  # namespace of per-block <seedname>_split.amn

.. note::

    ``results["win_files"]`` also holds a per-block ``.win`` file, but do not
    treat it as the source of truth for a block's parameters: WannierIO.jl
    substitutes its own convergence values into it, so read those from the
    parent wannier90 run instead.

Fallback: cubic neighbours
+++++++++++++++++++++++++++

``split_wannierization`` drives these two CalcJobs itself; call them directly
only if you need to check or supply the cubic stencil outside that workflow.

``wannierjl.check_neighbors`` reads a completed wannier90 run and reports
whether its k-point stencil already contains the cubic b-vectors, via
``read_w90_with_chk`` and ``Wannier.has_cubic_neighbors``. The ``.win`` can be
passed explicitly, while the remaining files are usually picked up from the
working directories of the wannier90 and pw2wannier90 runs via
``parent_folders`` ``RemoteData`` inputs (this is how the ``.chk`` file -- not
normally retrieved by upstream plugins -- is symlinked in from a run on the
same computer):

.. code-block:: python

    CheckNeighbors = CalculationFactory("wannierjl.check_neighbors")

    results, node = run_get_node(
        CheckNeighbors,
        code=load_code("wannierjl@localhost"),
        win_file=SinglefileData("aiida.win"),
        parent_folders={
            "wannier90": wannier90_remote_folder,      # provides .chk
            "pw2wannier90": pw2wannier90_remote_folder,  # provides .amn/.mmn/.eig
        },
    )

    has_cubic = results["has_cubic_neighbors"].value  # a Bool node

``wannierjl.generate_neighbors`` writes a ``cubic.nnkp`` file containing the
six cubic nearest-neighbour b-vectors, from a wannier90 input file. It only
needs the ``win_file`` input:

.. code-block:: python

    GenerateNeighbors = CalculationFactory("wannierjl.generate_neighbors")

    results, node = run_get_node(
        GenerateNeighbors,
        code=load_code("wannierjl@localhost"),
        win_file=SinglefileData("aiida.win"),
    )

    nnkp = results["nnkp_file"]  # SinglefileData holding cubic.nnkp

See :doc:`get_started` for the one-time Julia environment setup that these
calculations rely on.
