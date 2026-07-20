========
Tutorial
========

This tutorial walks through the three ``aiida-wannierjl`` CalcJobs and the
:func:`~aiida_wannierjl.workflows.split.split_wannierization` workgraph that ties them
together. It assumes you have already set up a Julia code (see
:doc:`get_started`) and have a completed wannier90 run to work from. The examples
load each calculation through its entry point, so nothing here depends on the
package layout.

Generating cubic neighbours
+++++++++++++++++++++++++++

``wannierjl.generate_neighbors`` writes a ``cubic.nnkp`` file containing the six
cubic nearest-neighbour b-vectors, from a wannier90 input file. It only needs the
``win_file`` input:

.. code-block:: python

    from aiida.engine import run_get_node
    from aiida.orm import SinglefileData, load_code
    from aiida.plugins import CalculationFactory

    GenerateNeighbors = CalculationFactory("wannierjl.generate_neighbors")

    results, node = run_get_node(
        GenerateNeighbors,
        code=load_code("wannierjl@localhost"),
        win_file=SinglefileData("aiida.win"),
    )

    nnkp = results["nnkp_file"]  # SinglefileData holding cubic.nnkp

Checking for cubic neighbours
+++++++++++++++++++++++++++++

``wannierjl.check_neighbors`` reads a completed wannier90 run and reports whether
its k-point stencil already contains the cubic b-vectors. The ``.win`` can be
passed explicitly, while the remaining files are usually picked up from the
working directories of the wannier90 and pw2wannier90 runs via ``parent_folders``
``RemoteData`` inputs (this is how the ``.chk`` file — not normally retrieved by
upstream plugins — is symlinked in from a run on the same computer):

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

Splitting the manifold
++++++++++++++++++++++

``wannierjl.split`` runs ``Wannier.Tools.mrwf`` to split the Wannier manifold into
blocks. The ``indices`` input is a list of 1-based index groups (disjoint,
non-empty). It takes the same file / ``parent_folders`` inputs as
``check_neighbors``, plus an optional cubic ``.mmn`` source when the original run
lacked cubic neighbours:

.. code-block:: python

    from aiida.orm import List

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

    blocks = results["blocks"]        # namespace of FolderData (amn/eig/mmn per block)
    win_files = results["win_files"]  # namespace of per-block .win SinglefileData
    u_matrices = results["u_matrices"]  # namespace of per-block <seedname>_split.amn

Orchestrating with the workgraph
++++++++++++++++++++++++++++++++

With the ``workflows`` extra installed
(``pip install aiida-wannierjl[workflows]``),
:func:`~aiida_wannierjl.workflows.split.split_wannierization` chains these steps into a
single aiida-workgraph ``@task.graph``. It runs ``check_neighbors`` and, only when
the cubic neighbours are missing, generates the ``cubic.nnkp``, regenerates the
cubic ``.mmn`` with a ``Pw2wannier90Calculation``, and then runs ``split`` — the
cubic branch is decided at runtime:

.. code-block:: python

    from aiida_wannierjl.workflows import split_wannierization

    outputs = split_wannierization(
        wjl_code=load_code("wannierjl@localhost"),
        win_file=SinglefileData("aiida.win"),
        groups=[[1, 2], [3, 4]],
        wannier90_parent=wannier90_remote_folder,
        pw2wannier90_parent=pw2wannier90_remote_folder,
        nscf_parent=nscf_remote_folder,            # only used if the cubic branch triggers
        pw2wannier90_code=load_code("pw2wannier90@localhost"),
    )

See :doc:`get_started` for the one-time Julia environment setup that these
calculations rely on.
