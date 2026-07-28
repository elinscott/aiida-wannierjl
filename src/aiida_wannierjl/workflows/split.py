"""The ``split_wannierization`` orchestration graph.

This is an `aiida-workgraph <https://aiida-workgraph.readthedocs.io>`_
``@task.graph`` (a plain-Python API -- there is no ``aiida.workflows`` entry
point). It chains the Wannier.jl CalcJobs and, when the wannierisation lacks the
six cubic nearest-neighbour b-vectors, the cubic ``pw2wannier90.x`` ``.mmn``
regeneration that lies within the same logical flow:

    check_neighbors
        -> (if not cubic) generate_neighbors -> pw2wannier90 (cubic .mmn)
        -> split

It starts from a completed wannierisation (``.win``/``.chk``/``.amn``/``.mmn``/
``.eig`` available, either as explicit :class:`~aiida.orm.SinglefileData` or via
``RemoteData`` parent folders). The downstream wannier90 re-wannierisation and
U-matrix merging are deliberately out of scope -- they stay in the consumer.

Requires the ``workflows`` extra (aiida-workgraph + aiida-quantumespresso)::

    pip install aiida-wannierjl[workflows]

Implementation note -- runtime branching
----------------------------------------
A ``@task.graph`` body is a *graph builder*: a task's ``.outputs`` accessed
inside the body is an unresolved socket, not a value, so a plain
``if not check.outputs.has_cubic_neighbors`` cannot branch on the *result* of
the check. aiida-workgraph resolves a graph task's own inputs to concrete values
before its body runs (see the ``sum_to_n`` example in the aiida-workgraph test
suite, ``tests/test_while.py``), so the data-dependent branch is delegated to a
nested graph task (:func:`~aiida_wannierjl.workflows.split.split_after_check`) that *receives*
``has_cubic_neighbors`` as an input. When that nested task executes -- after the
check has finished -- the value is concrete and ordinary Python ``if`` works.

(``split_after_check`` is a module-private helper -- it is not re-exported from
the package -- but it must not be named with a leading underscore: a
``@task.graph`` function name becomes an AiiDA ``CALL_WORK`` link label, and
AiiDA rejects link labels that start with ``_``.)
"""

try:
    from aiida_workgraph import spec, task
except ImportError as exc:  # pragma: no cover - exercised only without the extra
    raise ImportError(
        "aiida-workgraph is required for `aiida_wannierjl.workflows`; "
        "install it with `pip install aiida-wannierjl[workflows]`"
    ) from exc

from aiida import orm
from aiida.common.exceptions import MissingEntryPointError
from aiida.plugins import CalculationFactory

try:
    Pw2wannier90Calculation = CalculationFactory("quantumespresso.pw2wannier90")
except MissingEntryPointError as exc:  # pragma: no cover - exercised only without the extra
    raise ImportError(
        "aiida-quantumespresso is required for `aiida_wannierjl.workflows`; "
        "install it with `pip install aiida-wannierjl[workflows]`"
    ) from exc

from aiida_wannierjl.calculations.check_neighbors import CheckNeighborsCalculation
from aiida_wannierjl.calculations.generate_neighbors import GenerateNeighborsCalculation
from aiida_wannierjl.calculations.split import SplitCalculation

__all__ = ("split_wannierization",)

# Wrap each CalcJob as a workgraph task so it can be composed inside a graph body.
CheckNeighborsTask = task()(CheckNeighborsCalculation)
GenerateNeighborsTask = task()(GenerateNeighborsCalculation)
SplitTask = task()(SplitCalculation)
Pw2wannier90Task = task()(Pw2wannier90Calculation)

#: Forced ``pw2wannier90.x`` parameters for the cubic ``.mmn`` regeneration:
#: write only the overlap matrix, never the projections/UNK, and no SCDM.
_CUBIC_PW2WANNIER90_PARAMETERS = {"INPUTPP": {"write_mmn": True, "write_amn": False, "write_unk": False}}

# Output shapes, declared from the underlying CalcJob output specs so the
# per-block dynamic namespaces (``block_0 .. block_N``) propagate unchanged.
_BRANCH_OUTPUTS = spec.namespace(
    blocks=SplitTask.outputs["blocks"],
    win_files=SplitTask.outputs["win_files"],
    u_matrices=SplitTask.outputs["u_matrices"],
)
_GRAPH_OUTPUTS = spec.namespace(
    has_cubic_neighbors=CheckNeighborsTask.outputs["has_cubic_neighbors"],
    blocks=SplitTask.outputs["blocks"],
    win_files=SplitTask.outputs["win_files"],
    u_matrices=SplitTask.outputs["u_matrices"],
)


def _w90_file_inputs(chk_file, amn_file, mmn_file, eig_file):
    """Collect the explicitly-provided Wannier90 file ports (skipping ``None``).

    Every logical file must reach the CalcJob from exactly one source (explicit
    ``*_file`` port or ``parent_folders`` RemoteData); the CalcJob validator
    enforces that, so here we only forward the explicit files that were given.
    """
    files = {
        "chk_file": chk_file,
        "amn_file": amn_file,
        "mmn_file": mmn_file,
        "eig_file": eig_file,
    }
    return {port: node for port, node in files.items() if node is not None}


def _parent_folders(wannier90_parent, pw2wannier90_parent, cubic_parent=None):
    """Collect the ``parent_folders`` namespace (skipping ``None`` entries)."""
    parents = {
        "wannier90": wannier90_parent,
        "pw2wannier90": pw2wannier90_parent,
        "pw2wannier90_cubic": cubic_parent,
    }
    return {key: node for key, node in parents.items() if node is not None}


def _plain_dict(mapping):
    """Rebuild ``mapping`` (and any nested mappings) into plain ``dict``s.

    A dict-valued graph input reaches a deferred ``@task.graph`` body as a
    wrapt ``TaggedValue`` proxy, which namespace sockets such as
    ``metadata.options`` reject on assignment; rebuilding with plain ``dict``s
    keeps the options ports usable from inside a graph.
    """
    return {key: _plain_dict(value) if isinstance(value, dict) else value for key, value in mapping.items()}


def _options_metadata(options):
    """Wrap an options dict as CalcJob ``metadata`` (empty when unset)."""
    return {"options": _plain_dict(options)} if options else {}


@task.graph(outputs=_BRANCH_OUTPUTS)
def split_after_check(
    has_cubic_neighbors,
    wjl_code,
    win_file,
    groups,
    wannier90_parent=None,
    pw2wannier90_parent=None,
    nscf_parent=None,
    pw2wannier90_code=None,
    pw2wannier90_parameters=None,
    chk_file=None,
    mmn_file=None,
    amn_file=None,
    eig_file=None,
    outdirs=None,
    wjl_options=None,
    pw2wannier90_options=None,
):
    """Regenerate the cubic ``.mmn`` if needed, then run the split.

    ``has_cubic_neighbors`` is wired from
    :class:`~aiida_wannierjl.calculations.check_neighbors.CheckNeighborsCalculation`'s
    output; because this is a nested graph task, it is a concrete value by the
    time this body runs, so the ``if`` below is a genuine runtime branch. When
    the cubic branch triggers, ``nscf_parent`` and ``pw2wannier90_code`` are
    required and validated here (they are only meaningful on that path).
    """
    cubic_parent = None
    if not bool(has_cubic_neighbors):
        if nscf_parent is None or pw2wannier90_code is None:
            raise ValueError(
                "the wannierisation lacks cubic nearest-neighbour b-vectors, so the "
                "cubic pw2wannier90 regeneration branch must run, but `nscf_parent` "
                "and/or `pw2wannier90_code` were not provided"
            )
        nnkp = GenerateNeighborsTask(
            code=wjl_code,
            win_file=win_file,
            metadata=_options_metadata(wjl_options),
        )
        parameters = (
            pw2wannier90_parameters
            if pw2wannier90_parameters is not None
            else orm.Dict(dict=_CUBIC_PW2WANNIER90_PARAMETERS)
        )
        cubic = Pw2wannier90Task(
            code=pw2wannier90_code,
            parent_folder=nscf_parent,
            nnkp_file=nnkp.nnkp_file,
            parameters=parameters,
            metadata=_options_metadata(pw2wannier90_options),
        )
        # The cubic `.mmn` stays in the pw2wannier90 remote workdir; SplitCalculation
        # symlinks `<seedname>.mmn` from it via `parent_folders.pw2wannier90_cubic`.
        cubic_parent = cubic.remote_folder

    split_inputs = {
        "code": wjl_code,
        "win_file": win_file,
        "indices": groups,
        "parent_folders": _parent_folders(wannier90_parent, pw2wannier90_parent, cubic_parent),
        **_w90_file_inputs(chk_file, amn_file, mmn_file, eig_file),
    }
    if outdirs is not None:
        split_inputs["outdirs"] = outdirs

    split = SplitTask(metadata=_options_metadata(wjl_options), **split_inputs)
    return {
        "blocks": split.blocks,
        "win_files": split.win_files,
        "u_matrices": split.u_matrices,
    }


@task.graph(outputs=_GRAPH_OUTPUTS)
def split_wannierization(
    wjl_code,
    win_file,
    groups,
    wannier90_parent=None,
    pw2wannier90_parent=None,
    nscf_parent=None,
    pw2wannier90_code=None,
    pw2wannier90_parameters=None,
    chk_file=None,
    mmn_file=None,
    amn_file=None,
    eig_file=None,
    outdirs=None,
    wjl_options=None,
    pw2wannier90_options=None,
):
    """Check cubic neighbours, optionally regenerate the cubic ``.mmn``, then split.

    :param wjl_code: the Wannier.jl ``InstalledCode`` (julia binary).
    :param win_file: the Wannier90 ``.win`` file (:class:`~aiida.orm.SinglefileData`).
    :param groups: 1-based Wannier-function index groups, e.g. ``[[1, 2], [3, 4]]``
        (a plain list or :class:`~aiida.orm.List`), one group per output block.
    :param wannier90_parent: ``RemoteData`` of the wannier90.x run (source of ``.chk``).
    :param pw2wannier90_parent: ``RemoteData`` of the pw2wannier90.x run
        (source of ``.amn``/``.mmn``/``.eig``).
    :param nscf_parent: ``RemoteData`` of the nscf pw.x run; required only if the
        cubic branch triggers (input to the cubic pw2wannier90.x).
    :param pw2wannier90_code: the ``pw2wannier90.x`` code; required only if the
        cubic branch triggers.
    :param pw2wannier90_parameters: optional override ``Dict`` for the cubic
        pw2wannier90.x; defaults to writing only the ``.mmn``.
    :param chk_file, mmn_file, amn_file, eig_file: optional explicit
        :class:`~aiida.orm.SinglefileData` alternatives to the parent folders.
    :param outdirs: optional list of per-block output directory names
        (default ``block_0 .. block_N``).
    :param wjl_options: optional ``metadata.options`` dict for the Wannier.jl CalcJobs.
    :param pw2wannier90_options: optional ``metadata.options`` dict for pw2wannier90.x.
    :returns: a namespace with ``has_cubic_neighbors`` (Bool) and the dynamic
        ``blocks``/``win_files``/``u_matrices`` namespaces from the split.
    """
    check = CheckNeighborsTask(
        code=wjl_code,
        win_file=win_file,
        parent_folders=_parent_folders(wannier90_parent, pw2wannier90_parent),
        metadata=_options_metadata(wjl_options),
        **_w90_file_inputs(chk_file, amn_file, mmn_file, eig_file),
    )

    branch = split_after_check(
        has_cubic_neighbors=check.has_cubic_neighbors,
        wjl_code=wjl_code,
        win_file=win_file,
        groups=groups,
        wannier90_parent=wannier90_parent,
        pw2wannier90_parent=pw2wannier90_parent,
        nscf_parent=nscf_parent,
        pw2wannier90_code=pw2wannier90_code,
        pw2wannier90_parameters=pw2wannier90_parameters,
        chk_file=chk_file,
        mmn_file=mmn_file,
        amn_file=amn_file,
        eig_file=eig_file,
        outdirs=outdirs,
        wjl_options=wjl_options,
        pw2wannier90_options=pw2wannier90_options,
    )

    return {
        "has_cubic_neighbors": check.has_cubic_neighbors,
        "blocks": branch.blocks,
        "win_files": branch.win_files,
        "u_matrices": branch.u_matrices,
    }
