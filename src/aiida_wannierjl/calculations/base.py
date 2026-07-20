"""Abstract base :class:`~aiida.engine.CalcJob` for the Wannier.jl operations.

Every Wannier.jl CalcJob renders a small Julia *driver script* (``driver.jl``)
that is executed against a persistent Wannier.jl project environment. The driver
writes a machine-readable ``results.json`` that the matching parser turns into
AiiDA output nodes.

The concrete subclasses (:mod:`~aiida_wannierjl.calculations.check_neighbors`,
:mod:`~aiida_wannierjl.calculations.generate_neighbors`,
:mod:`~aiida_wannierjl.calculations.split`) only have to declare which Wannier90
files they need (``_REQUIRED_W90_FILES``) and how to render their driver script
(``_render_driver_script``); everything else (file staging, command line,
retrieval, exit codes) lives here.
"""

import os

from aiida import orm
from aiida.common.datastructures import CalcInfo, CodeInfo
from aiida.engine import CalcJob

# Pinned Wannier.jl provenance. The single source of truth lives in ``helpers``
# (it is what the environment-setup scripts use); re-exported here for convenience.
from ..helpers import WANNIER_JL_REV, WANNIER_JL_UUID  # noqa: F401

#: Name of the rendered Julia driver script.
DRIVER_SCRIPT = "driver.jl"
#: Name of the machine-readable results file written by every driver.
RESULTS_FILE = "results.json"
#: Name of the combined stdout/stderr file (Julia prints ``ERROR:``/``LoadError``
#: to stderr, which is joined into this file).
STDOUT_FILE = "julia.out"


class WannierJLCalcJob(CalcJob):
    """Abstract base class for the Wannier.jl CalcJobs.

    Subclasses must set :attr:`_REQUIRED_W90_FILES` and implement
    :meth:`_render_driver_script`.
    """

    _DRIVER_SCRIPT = DRIVER_SCRIPT
    _RESULTS_FILE = RESULTS_FILE
    _STDOUT = STDOUT_FILE

    #: Wannier90 file extensions required by this CalcJob (subclass overrides).
    _REQUIRED_W90_FILES = ()

    #: Map of logical Wannier90 file extension -> explicit ``SinglefileData`` port.
    _FILE_PORTS = {
        "win": "win_file",
        "chk": "chk_file",
        "amn": "amn_file",
        "mmn": "mmn_file",
        "eig": "eig_file",
    }
    #: Map of logical extension -> ``parent_folders`` sub-port that can provide it
    #: as a ``RemoteData``. ``win`` has no remote source (always from ``win_file``).
    _PARENT_FOR_EXT = {
        "chk": "wannier90",
        "amn": "pw2wannier90",
        "mmn": "pw2wannier90",
        "eig": "pw2wannier90",
    }

    @classmethod
    def define(cls, spec):
        """Define the shared input/output spec, options and exit codes."""
        super().define(spec)

        # -- options -------------------------------------------------------
        spec.input(
            "metadata.options.seedname",
            valid_type=str,
            default="aiida",
            help="Seedname of the Wannier90 files (``<seedname>.win`` etc.).",
        )
        spec.input(
            "metadata.options.julia_project",
            valid_type=str,
            required=False,
            help="Path to the Wannier.jl Julia project (``--project=<path>``). "
            "If unset the driver relies on ``JULIA_PROJECT`` from the code's prepend_text.",
        )
        spec.input(
            "metadata.options.julia_sysimage",
            valid_type=str,
            required=False,
            help="Path to a pre-built Julia sysimage (``--sysimage=<path>``). Overrides the "
            "``sysimage_path`` extra carried on the code node.",
        )
        spec.inputs["metadata"]["options"]["resources"].default = {
            "num_machines": 1,
            "num_mpiprocs_per_machine": 1,
        }
        spec.inputs["metadata"]["options"]["withmpi"].default = False

        # -- shared inputs -------------------------------------------------
        spec.input(
            "win_file",
            valid_type=orm.SinglefileData,
            required=True,
            help="The Wannier90 ``.win`` input file (always provided explicitly).",
        )
        for ext, port in cls._FILE_PORTS.items():
            if ext == "win":
                continue
            spec.input(
                port,
                valid_type=orm.SinglefileData,
                required=False,
                help=f"The Wannier90 ``.{ext}`` file (alternative to a ``parent_folders`` source).",
            )
        spec.input_namespace(
            "parent_folders",
            required=False,
            help="Remote folders of preceding calculations from which Wannier90 files are symlinked.",
        )
        spec.input(
            "parent_folders.wannier90",
            valid_type=orm.RemoteData,
            required=False,
            help="Remote working directory of a wannier90.x run (source of ``<seedname>.chk``).",
        )
        spec.input(
            "parent_folders.pw2wannier90",
            valid_type=orm.RemoteData,
            required=False,
            help="Remote working directory of a pw2wannier90.x run " "(source of ``<seedname>.{amn,mmn,eig}``).",
        )

        spec.inputs.validator = cls._validate_inputs

        # -- exit codes ----------------------------------------------------
        spec.exit_code(
            300,
            "ERROR_MISSING_OUTPUT_FILES",
            message="One or more expected output files are missing from the retrieved folder.",
        )
        spec.exit_code(
            301,
            "ERROR_MISSING_RESULTS_FILE",
            message="The driver did not produce the results file `results.json`.",
        )
        spec.exit_code(
            310,
            "ERROR_JULIA_FAILURE",
            message="The Julia driver script failed (see `julia.out`).",
        )
        spec.exit_code(
            320,
            "ERROR_INVALID_RESULTS",
            message="The results file `results.json` is not valid or is missing expected keys.",
        )

    # ------------------------------------------------------------------ #
    # Input validation
    # ------------------------------------------------------------------ #
    @classmethod
    def _validate_inputs(cls, value, port_namespace):  # pylint: disable=unused-argument
        """Ensure every required Wannier90 file is resolvable from exactly one source."""
        parents = value.get("parent_folders", None) or {}
        code = value.get("code", None)
        code_computer = code.computer if code is not None else None

        for ext in cls._REQUIRED_W90_FILES:
            port = cls._FILE_PORTS[ext]
            has_file = value.get(port, None) is not None

            if ext == "win":
                if not has_file:
                    return f"the `{port}` input is required to provide the `.{ext}` file"
                continue

            parent_key = cls._PARENT_FOR_EXT.get(ext)
            remote = parents.get(parent_key) if parent_key else None
            has_remote = remote is not None

            if has_file and has_remote:
                return (
                    f"the `.{ext}` file is provided by both `{port}` and "
                    f"`parent_folders.{parent_key}`; provide exactly one"
                )
            if not has_file and not has_remote:
                return f"the `.{ext}` file must be provided via `{port}` or " f"`parent_folders.{parent_key}`"
            if has_remote and code_computer is not None and remote.computer.uuid != code_computer.uuid:
                return (
                    f"`parent_folders.{parent_key}` is on computer `{remote.computer.label}` but the "
                    f"code runs on `{code_computer.label}`; a RemoteData can only be symlinked on the "
                    f"same computer, so provide the `.{ext}` file via `{port}` instead"
                )
        return None

    # ------------------------------------------------------------------ #
    # Hooks for subclasses
    # ------------------------------------------------------------------ #
    def _render_driver_script(self):
        """Return the contents of the Julia driver script. Implemented by subclasses."""
        raise NotImplementedError

    def _retrieve_extra(self):
        """Return extra ``retrieve_list`` entries specific to the subclass."""
        return []

    def _extra_copy_lists(self):
        """Return extra ``(local_copy_list, remote_symlink_list)`` entries.

        Used by subclasses that stage files beyond the standard Wannier90 set
        (e.g. the cubic ``.mmn`` for :class:`~aiida_wannierjl.calculations.split.SplitCalculation`).
        """
        return [], []

    # ------------------------------------------------------------------ #
    # File staging
    # ------------------------------------------------------------------ #
    def _resolve_w90_files(self):
        """Build the copy/symlink lists for the required Wannier90 files.

        Returns a ``(local_copy_list, remote_symlink_list)`` tuple. Each required
        extension is staged as ``<seedname>.<ext>`` in the working directory,
        either by copying a local ``SinglefileData`` or by symlinking it out of a
        ``parent_folders`` RemoteData.
        """
        seedname = self.node.get_option("seedname")
        code_computer = self.inputs.code.computer
        parents = self.inputs.get("parent_folders", None) or {}

        local_copy_list = []
        remote_symlink_list = []

        for ext in self._REQUIRED_W90_FILES:
            target = f"{seedname}.{ext}"
            node = self.inputs.get(self._FILE_PORTS[ext], None)
            if node is not None:
                local_copy_list.append((node.uuid, node.filename, target))
                continue

            parent_key = self._PARENT_FOR_EXT.get(ext)
            remote = parents.get(parent_key) if parent_key else None
            if remote is not None:
                remote_path = os.path.join(remote.get_remote_path(), target)
                # Same-computer requirement is enforced by the input validator.
                remote_symlink_list.append((code_computer.uuid, remote_path, target))
                continue

            # Unreachable when the input validator has run, but fail loudly otherwise.
            raise ValueError(f"could not resolve the `.{ext}` file for {self.__class__.__name__}")

        return local_copy_list, remote_symlink_list

    # ------------------------------------------------------------------ #
    # Command line
    # ------------------------------------------------------------------ #
    def _cmdline_params(self):
        """Assemble the Julia command line (before the driver script name)."""
        params = ["--startup-file=no", "--color=no"]

        project = self.node.get_option("julia_project")
        if project:
            params.append(f"--project={project}")

        sysimage = self.node.get_option("julia_sysimage")
        if sysimage is None:
            sysimage = self.inputs.code.base.extras.get("sysimage_path", None)
        if sysimage:
            params.append(f"--sysimage={sysimage}")

        params.append(self._DRIVER_SCRIPT)
        return params

    # ------------------------------------------------------------------ #
    # prepare_for_submission
    # ------------------------------------------------------------------ #
    def prepare_for_submission(self, folder):
        """Write the driver script and assemble the :class:`CalcInfo`."""
        with folder.open(self._DRIVER_SCRIPT, "w", encoding="utf8") as handle:
            handle.write(self._render_driver_script())

        local_copy_list, remote_symlink_list = self._resolve_w90_files()
        extra_local, extra_symlink = self._extra_copy_lists()
        local_copy_list += extra_local
        remote_symlink_list += extra_symlink

        codeinfo = CodeInfo()
        codeinfo.code_uuid = self.inputs.code.uuid
        codeinfo.cmdline_params = self._cmdline_params()
        codeinfo.stdout_name = self._STDOUT
        codeinfo.join_files = True

        calcinfo = CalcInfo()
        calcinfo.codes_info = [codeinfo]
        calcinfo.local_copy_list = local_copy_list
        calcinfo.remote_symlink_list = remote_symlink_list
        calcinfo.retrieve_list = [self._RESULTS_FILE, self._STDOUT] + self._retrieve_extra()

        return calcinfo
