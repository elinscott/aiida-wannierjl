"""Helpers for setting up the Julia environment and the Wannier.jl ``Code``.

The Julia environment (the pinned Wannier.jl + JSON project, and optionally a
PackageCompiler sysimage) is created ONCE per machine, never per calculation.
On the machine that runs the calculations you have two options:

* **Local convenience:** call :func:`setup_julia_environment`, which shells out
  to the packaged ``install_wannierjl.jl`` and ``build_sysimage.jl`` scripts.
* **Remote machines:** copy the two ``julia/*.jl`` scripts to the machine and
  run them by hand (see :func:`setup_julia_environment` for the exact commands);
  then register the Code with :func:`get_wannierjl_code`, passing the sysimage
  path you built there.
"""

from __future__ import annotations

import subprocess
from importlib.resources import files
from pathlib import Path

__all__ = (
    "WANNIER_JL_UUID",
    "WANNIER_JL_REV",
    "WANNIER_JL_URL",
    "setup_julia_environment",
    "get_wannierjl_code",
)

# Single source of truth for the pinned Wannier.jl revision. ``calculations``
# code may re-import these from here.
WANNIER_JL_UUID = "2b19380a-1f7e-4d7d-b1b8-8aa60b3321c9"
WANNIER_JL_REV = "65245c59"
WANNIER_JL_URL = "https://github.com/qiaojunfeng/Wannier.jl.git"

#: Default entry point used for Codes registered by :func:`get_wannierjl_code`.
_DEFAULT_CALC_JOB_PLUGIN = "wannierjl.check_neighbors"

#: Name of the sysimage file written inside ``project_dir``.
_SYSIMAGE_FILENAME = "wannierjl.so"


def _packaged_script(name: str) -> Path:
    """Return the on-disk path of a packaged ``julia/<name>`` script."""
    return Path(str(files("aiida_wannierjl") / "julia" / name))


def setup_julia_environment(
    julia_exe: str,
    project_dir: str,
    sysimage: bool = True,
    timeout: int = 3600,
) -> str | None:
    """Create the persistent Wannier.jl project (and optionally a sysimage).

    This is a **local** convenience wrapper. It runs, in order:

    #. ``julia --startup-file=no --project=<project_dir> install_wannierjl.jl``
       (installs the pinned Wannier.jl + JSON and precompiles them);
    #. if ``sysimage`` is true, ``julia --startup-file=no
       --project=<project_dir> -e 'using Pkg; Pkg.add("PackageCompiler")'``
       followed by ``julia --startup-file=no --project=<project_dir>
       build_sysimage.jl <project_dir>/wannierjl.so``.

    On a **remote** machine where you cannot call this function, run exactly
    those commands by hand against the two ``julia/*.jl`` scripts, then pass the
    resulting sysimage path to :func:`get_wannierjl_code`.

    :param julia_exe: path to the ``julia`` binary (julia >= 1.11).
    :param project_dir: directory that will hold the project's
        ``Project.toml``/``Manifest.toml`` (created if missing).
    :param sysimage: whether to also build ``<project_dir>/wannierjl.so``.
    :param timeout: per-subprocess timeout in seconds.
    :returns: the sysimage path if one was built, otherwise ``None``.
    """
    project_path = Path(project_dir).expanduser().resolve()
    project_path.mkdir(parents=True, exist_ok=True)
    project_arg = f"--project={project_path}"

    install_script = _packaged_script("install_wannierjl.jl")
    subprocess.run(
        [julia_exe, "--startup-file=no", project_arg, str(install_script)],
        check=True,
        timeout=timeout,
    )

    if not sysimage:
        return None

    # PackageCompiler is only needed for the sysimage build, so it is added
    # inline rather than baked into install_wannierjl.jl.
    subprocess.run(
        [
            julia_exe,
            "--startup-file=no",
            project_arg,
            "-e",
            'using Pkg; Pkg.add("PackageCompiler")',
        ],
        check=True,
        timeout=timeout,
    )

    sysimage_path = project_path / _SYSIMAGE_FILENAME
    build_script = _packaged_script("build_sysimage.jl")
    subprocess.run(
        [
            julia_exe,
            "--startup-file=no",
            project_arg,
            str(build_script),
            str(sysimage_path),
        ],
        check=True,
        timeout=timeout,
    )

    return str(sysimage_path)


def get_wannierjl_code(
    label: str,
    computer,
    julia_exe: str,
    project_dir: str,
    sysimage_path: str | None = None,
):
    """Create (or load) the ``InstalledCode`` for the Wannier.jl CalcJobs.

    The Code is the ``julia`` binary itself; the pinned Wannier.jl project is
    selected via ``JULIA_PROJECT`` in the Code's ``prepend_text``. If a sysimage
    was built, its path is stored as the ``sysimage_path`` extra, which the base
    CalcJob reads to add ``--sysimage=<path>`` to the julia command line.

    This helper is idempotent: if a Code with ``label@computer`` already exists
    it is loaded and returned unchanged.

    :param label: label for the Code node.
    :param computer: the AiiDA ``Computer`` (node or label) the Code runs on.
    :param julia_exe: absolute path to the ``julia`` binary on that computer.
    :param project_dir: the Wannier.jl project directory on that computer
        (exported as ``JULIA_PROJECT``).
    :param sysimage_path: path to the sysimage on that computer, if any.
    :returns: the ``InstalledCode`` node.
    """
    from aiida.common.exceptions import NotExistent
    from aiida.orm import InstalledCode, load_code

    computer_label = computer.label if hasattr(computer, "label") else computer
    try:
        return load_code(f"{label}@{computer_label}")
    except NotExistent:
        pass

    code = InstalledCode(
        label=label,
        computer=computer,
        filepath_executable=julia_exe,
        default_calc_job_plugin=_DEFAULT_CALC_JOB_PLUGIN,
    )
    code.prepend_text = f"export JULIA_PROJECT={project_dir}"
    code.store()

    if sysimage_path:
        code.base.extras.set("sysimage_path", sysimage_path)

    return code
