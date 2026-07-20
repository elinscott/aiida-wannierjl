"""``SplitCalculation`` -- split a Wannier manifold into blocks via ``mrwf``."""

import os
import re
import textwrap

from aiida import orm

from .base import WannierJLCalcJob

_OUTDIR_RE = re.compile(r"^\w+$")


def validate_indices(value, _):
    """Validate the ``indices`` list: non-empty groups of disjoint 1-based ints."""
    groups = value.get_list()
    if not groups:
        return "`indices` must be a non-empty list of groups"
    seen = set()
    for group in groups:
        if not isinstance(group, list) or not group:
            return "each group in `indices` must be a non-empty list of integers"
        for index in group:
            # bool is a subclass of int; reject it explicitly.
            if not isinstance(index, int) or isinstance(index, bool) or index < 1:
                return "all entries in `indices` must be integers >= 1 (1-based)"
            if index in seen:
                return f"index {index} appears in more than one group; groups must be disjoint"
            seen.add(index)
    return None


def validate_outdirs(value, _):
    """Validate the ``outdirs`` list: simple relative names (valid link labels)."""
    for name in value.get_list():
        if not isinstance(name, str) or not _OUTDIR_RE.match(name):
            return f"outdir {name!r} must be a simple name matching [A-Za-z0-9_]+ (no '/', '..')"
    return None


class SplitCalculation(WannierJLCalcJob):
    """Split a Wannier manifold into blocks using ``Wannier.Tools.mrwf``.

    Requires the full Wannier90 set (as
    :class:`~aiida_wannierjl.calculations.check_neighbors.CheckNeighborsCalculation`) plus a
    list of 1-based index ``groups``. An optional cubic ``.mmn`` (from
    ``cubic_mmn_file`` or the ``pw2wannier90_cubic`` parent folder) is passed to
    ``mrwf`` when the default b-vectors lack cubic neighbours.
    """

    _REQUIRED_W90_FILES = ("win", "chk", "amn", "mmn", "eig")

    @classmethod
    def define(cls, spec):
        """Define the spec: indices/outdirs, cubic source, dynamic block outputs."""
        super().define(spec)
        spec.inputs["metadata"]["options"]["parser_name"].default = "wannierjl.split"

        spec.input(
            "indices",
            valid_type=orm.List,
            required=True,
            validator=validate_indices,
            help="Groups of 1-based Wannier function indices, e.g. ``[[1, 2], [3, 4]]``.",
        )
        spec.input(
            "outdirs",
            valid_type=orm.List,
            required=False,
            validator=validate_outdirs,
            help="Output sub-directory names, one per group. Defaults to ``block_0 .. block_N``.",
        )
        spec.input(
            "cubic_mmn_file",
            valid_type=orm.SinglefileData,
            required=False,
            help="A cubic ``.mmn`` file (staged as ``cubic.mmn``). Mutually exclusive with "
            "``parent_folders.pw2wannier90_cubic``.",
        )
        spec.input(
            "parent_folders.pw2wannier90_cubic",
            valid_type=orm.RemoteData,
            required=False,
            help="Remote working directory of a cubic pw2wannier90.x run "
            "(``<seedname>.mmn`` symlinked as ``cubic.mmn``).",
        )

        spec.output_namespace(
            "blocks",
            valid_type=orm.FolderData,
            dynamic=True,
            help="Per-block folder with ``<seedname>.{amn,eig,mmn}`` (the ``.win`` is excluded so "
            "the folder can be fed straight to wannier90's ``local_input_folder``).",
        )
        spec.output_namespace(
            "win_files",
            valid_type=orm.SinglefileData,
            dynamic=True,
            help="Per-block ``<seedname>.win`` written by ``mrwf``.",
        )
        spec.output_namespace(
            "u_matrices",
            valid_type=orm.SinglefileData,
            dynamic=True,
            help="Per-block ``<seedname>_split.amn`` (the split rotation matrix).",
        )

    # ------------------------------------------------------------------ #
    # Validation
    # ------------------------------------------------------------------ #
    @classmethod
    def _validate_inputs(cls, value, port_namespace):
        """Validate the shared inputs plus the split-specific cross-checks."""
        error = super()._validate_inputs(value, port_namespace)
        if error is not None:
            return error

        indices = value["indices"].get_list()
        outdirs_node = value.get("outdirs", None)
        if outdirs_node is not None and len(outdirs_node.get_list()) != len(indices):
            return "`outdirs` must have the same length as `indices` (one output dir per group)"

        parents = value.get("parent_folders", None) or {}
        cubic_remote = parents.get("pw2wannier90_cubic", None)
        has_cubic_file = value.get("cubic_mmn_file", None) is not None
        if has_cubic_file and cubic_remote is not None:
            return "provide at most one of `cubic_mmn_file` and `parent_folders.pw2wannier90_cubic`"

        code = value.get("code", None)
        code_computer = code.computer if code is not None else None
        if cubic_remote is not None and code_computer is not None:
            if cubic_remote.computer.uuid != code_computer.uuid:
                return (
                    "`parent_folders.pw2wannier90_cubic` must be on the same computer as the code; "
                    "provide the cubic mmn via `cubic_mmn_file` instead"
                )
        return None

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_outdirs(self):
        """Return the output directory names (explicit input or the default block_i)."""
        outdirs_node = self.inputs.get("outdirs", None)
        if outdirs_node is not None:
            return outdirs_node.get_list()
        num_groups = len(self.inputs.indices.get_list())
        return [f"block_{i}" for i in range(num_groups)]

    def _has_cubic_source(self):
        """Return whether a cubic ``.mmn`` is supplied via either route."""
        if self.inputs.get("cubic_mmn_file", None) is not None:
            return True
        parents = self.inputs.get("parent_folders", None) or {}
        return parents.get("pw2wannier90_cubic", None) is not None

    # ------------------------------------------------------------------ #
    # Driver
    # ------------------------------------------------------------------ #
    @staticmethod
    def render_driver(seedname, indices, outdirs, cubic_mmn):
        """Return the Julia driver script.

        ``indices`` is a list of lists of ints, ``outdirs`` a list of names and
        ``cubic_mmn`` either the ``cubic.mmn`` filename or ``None``.
        """
        indices_literal = str(indices)
        outdirs_literal = "[" + ", ".join(f'"{name}"' for name in outdirs) + "]"
        cubic_literal = f'"{cubic_mmn}"' if cubic_mmn else "nothing"
        return textwrap.dedent(
            f"""\
            using Wannier
            using JSON

            seedname = "{seedname}"
            indices = {indices_literal}
            outdirs = {outdirs_literal}
            cubic_mmn = {cubic_literal}

            Wannier.Tools.mrwf(seedname, indices, outdirs, cubic_mmn)

            open("results.json", "w") do io
                JSON.print(io, Dict("outdirs" => outdirs))
            end
            """
        )

    def _render_driver_script(self):
        cubic = "cubic.mmn" if self._has_cubic_source() else None
        return self.render_driver(
            self.node.get_option("seedname"),
            self.inputs.indices.get_list(),
            self._get_outdirs(),
            cubic,
        )

    # ------------------------------------------------------------------ #
    # File staging / retrieval
    # ------------------------------------------------------------------ #
    def _extra_copy_lists(self):
        seedname = self.node.get_option("seedname")
        local_copy_list = []
        remote_symlink_list = []

        cubic_file = self.inputs.get("cubic_mmn_file", None)
        if cubic_file is not None:
            local_copy_list.append((cubic_file.uuid, cubic_file.filename, "cubic.mmn"))
        else:
            parents = self.inputs.get("parent_folders", None) or {}
            remote = parents.get("pw2wannier90_cubic", None)
            if remote is not None:
                remote_path = os.path.join(remote.get_remote_path(), f"{seedname}.mmn")
                remote_symlink_list.append((self.inputs.code.computer.uuid, remote_path, "cubic.mmn"))

        return local_copy_list, remote_symlink_list

    def _retrieve_extra(self):
        # ``(source, target, depth)``: copy each outdir directory tree into
        # ``retrieved/<outdir>/`` (depth 1 keeps the trailing dir component).
        return [(outdir, ".", 1) for outdir in self._get_outdirs()]
