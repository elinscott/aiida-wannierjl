"""Tests for the ``split_wannierization`` workgraph.

These require the ``workflows`` extra (aiida-workgraph + aiida-quantumespresso)
and are skipped otherwise. No Julia is needed: the ``mock_julia_code`` fixture
from ``conftest.py`` fakes the Wannier.jl driver outputs, and a tiny in-test mock
CalcJob stands in for the cubic ``pw2wannier90.x`` run (every CalcJob
automatically produces a ``remote_folder`` output, which is all the split step
needs from it).
"""

import pathlib
import stat

import pytest

pytest.importorskip("aiida_workgraph")
pytest.importorskip("aiida_quantumespresso")

from aiida import orm  # noqa: E402
from aiida.common.datastructures import CalcInfo, CodeInfo  # noqa: E402
from aiida.engine import CalcJob  # noqa: E402
from aiida.orm import QueryBuilder  # noqa: E402
from aiida.plugins import CalculationFactory  # noqa: E402
from aiida_wannierjl.calculations.split import SplitCalculation  # noqa: E402
from aiida_wannierjl.workflows import split_wannierization  # noqa: E402
from aiida_workgraph import WorkGraph, task  # noqa: E402

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
# A no-cubic variant of conftest's mock julia code: identical, except that the
# ``has_cubic_neighbors`` check reports ``false`` so the cubic branch triggers.
_MOCK_SCRIPT_NO_CUBIC = r"""#!/usr/bin/env bash
set -e

for driver in "$@"; do :; done

fixtures="__FIXTURES__"
seedname=$(grep '^seedname = ' "$driver" | head -1 | grep -oE '"[^"]*"' | tr -d '"')

if grep -q 'write_nnkp_cubic' "$driver"; then
    cp "$fixtures/cubic.nnkp" cubic.nnkp
    echo '{"success": true}' > results.json
elif grep -q 'has_cubic_neighbors' "$driver"; then
    echo '{"has_cubic_neighbors": false}' > results.json
elif grep -q 'mrwf' "$driver"; then
    outdirs=$(grep '^outdirs = ' "$driver" | head -1 | grep -oE '"[^"]*"' | tr -d '"')
    json_items=""
    for d in $outdirs; do
        mkdir -p "$d"
        cp "$fixtures/aiida.amn" "$d/${seedname}.amn"
        cp "$fixtures/aiida.eig" "$d/${seedname}.eig"
        cp "$fixtures/aiida.mmn" "$d/${seedname}.mmn"
        cp "$fixtures/aiida.win" "$d/${seedname}.win"
        cp "$fixtures/aiida_split.amn" "$d/${seedname}_split.amn"
        if [ -z "$json_items" ]; then
            json_items="\"$d\""
        else
            json_items="$json_items, \"$d\""
        fi
    done
    echo "{\"outdirs\": [$json_items]}" > results.json
else
    echo "ERROR: mock julia code did not recognise the driver script" >&2
    exit 1
fi
"""

# A bash "pw2wannier90.x" that leaves the cubic ``aiida.mmn`` in its workdir.
_MOCK_PW2WANNIER90_SCRIPT = "#!/usr/bin/env bash\necho 'mock cubic mmn' > aiida.mmn\n"


def _write_executable(directory, name, body):
    script = directory / name
    script.write_text(body.replace("__FIXTURES__", str(FIXTURES_DIR)))
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return script


@pytest.fixture
def mock_julia_code_no_cubic(aiida_code_installed, tmp_path_factory):
    """Mock julia whose neighbour check reports no cubic neighbours."""
    script = _write_executable(tmp_path_factory.mktemp("mock_julia_no_cubic"), "julia.sh", _MOCK_SCRIPT_NO_CUBIC)
    return aiida_code_installed(
        label="mock.julia.no_cubic",
        default_calc_job_plugin="wannierjl.check_neighbors",
        filepath_executable=str(script),
    )


@pytest.fixture
def mock_pw2wannier90_code(aiida_code_installed, tmp_path_factory):
    """A bash stand-in for ``pw2wannier90.x`` that writes a cubic ``aiida.mmn``."""
    script = _write_executable(tmp_path_factory.mktemp("mock_pw2w"), "pw2wannier90.sh", _MOCK_PW2WANNIER90_SCRIPT)
    # The entry point only labels the code; the mock CalcJob class is what runs.
    return aiida_code_installed(
        label="mock.pw2wannier90",
        default_calc_job_plugin="quantumespresso.pw2wannier90",
        filepath_executable=str(script),
    )


class MockPw2wannier90Calculation(CalcJob):
    """Minimal stand-in for ``Pw2wannier90Calculation``.

    Accepts the same inputs the workflow passes (``code``, ``parent_folder``,
    ``nnkp_file``, ``parameters``) and runs its code, which leaves ``aiida.mmn``
    in the working directory. The automatically-created ``remote_folder`` output
    is what the split step symlinks the cubic ``.mmn`` from.
    """

    @classmethod
    def define(cls, spec):
        super().define(spec)
        spec.input("parent_folder", valid_type=orm.RemoteData)
        spec.input("nnkp_file", valid_type=orm.SinglefileData)
        spec.input("parameters", valid_type=orm.Dict)
        spec.inputs["metadata"]["options"]["resources"].default = {
            "num_machines": 1,
            "num_mpiprocs_per_machine": 1,
        }
        spec.inputs["metadata"]["options"]["withmpi"].default = False

    def prepare_for_submission(self, folder):
        codeinfo = CodeInfo()
        codeinfo.code_uuid = self.inputs.code.uuid
        calcinfo = CalcInfo()
        calcinfo.codes_info = [codeinfo]
        calcinfo.retrieve_list = []
        return calcinfo


def _singlefile(name):
    return orm.SinglefileData(file=str(FIXTURES_DIR / name))


def _w90_file_inputs():
    """The full Wannier90 set as explicit SinglefileData inputs."""
    return {
        "win_file": _singlefile("aiida.win"),
        "chk_file": _singlefile("aiida.chk"),
        "amn_file": _singlefile("aiida.amn"),
        "mmn_file": _singlefile("aiida.mmn"),
        "eig_file": _singlefile("aiida.eig"),
    }


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
def test_import():
    """The public builder imports without the workflow being invoked."""
    assert callable(split_wannierization)


def test_cubic_present_skips_pw2wannier90(mock_julia_code):
    """When cubic neighbours are present, the split runs directly (no pw2wannier90)."""
    with WorkGraph() as wg:
        outputs = split_wannierization(
            wjl_code=mock_julia_code,
            groups=orm.List(list=[[1, 2], [3, 4]]),
            **_w90_file_inputs(),
        )
    wg.run()

    assert bool(outputs.has_cubic_neighbors.value) is True

    # No cubic branch => no pw2wannier90 calculation was created.
    pw2wannier90 = CalculationFactory("quantumespresso.pw2wannier90")
    assert QueryBuilder().append(pw2wannier90).count() == 0

    split_nodes = QueryBuilder().append(SplitCalculation).all(flat=True)
    assert len(split_nodes) == 1
    assert split_nodes[0].exit_status == 0
    assert set(split_nodes[0].outputs.blocks) == {"block_0", "block_1"}


def test_cubic_absent_without_nscf_fails(mock_julia_code_no_cubic):
    """The cubic branch needs nscf_parent + pw2wannier90_code; missing => graph fails."""
    with WorkGraph() as wg:
        split_wannierization(
            wjl_code=mock_julia_code_no_cubic,
            groups=orm.List(list=[[1, 2]]),
            **_w90_file_inputs(),
        )
    # The nested graph task raises ValueError at runtime; the graph must not finish OK.
    # Depending on the runner, that surfaces either as an exception from ``run`` or
    # as a non-FINISHED graph state -- tolerate both.
    try:
        wg.run()
    except Exception:
        pass
    assert wg.state != "FINISHED"


def test_cubic_absent_runs_pw2wannier90(
    mock_julia_code_no_cubic, mock_pw2wannier90_code, aiida_localhost, tmp_path, monkeypatch
):
    """When cubic neighbours are absent, the pw2wannier90 branch runs then the split."""
    from aiida_wannierjl.workflows import split as split_module

    # Swap the real Pw2wannier90 task for the lightweight mock CalcJob task.
    monkeypatch.setattr(split_module, "Pw2wannier90Task", task()(MockPw2wannier90Calculation))

    nscf_parent = orm.RemoteData(remote_path=str(tmp_path), computer=aiida_localhost).store()

    with WorkGraph() as wg:
        outputs = split_wannierization(
            wjl_code=mock_julia_code_no_cubic,
            groups=orm.List(list=[[1, 2]]),
            nscf_parent=nscf_parent,
            pw2wannier90_code=mock_pw2wannier90_code,
            **_w90_file_inputs(),
        )
    wg.run()

    assert bool(outputs.has_cubic_neighbors.value) is False

    # The cubic pw2wannier90 branch ran exactly once.
    assert QueryBuilder().append(MockPw2wannier90Calculation).count() == 1

    split_nodes = QueryBuilder().append(SplitCalculation).all(flat=True)
    assert len(split_nodes) == 1
    assert split_nodes[0].exit_status == 0
    assert set(split_nodes[0].outputs.blocks) == {"block_0"}
