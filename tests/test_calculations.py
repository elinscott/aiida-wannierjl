"""End-to-end tests for the Wannier.jl CalcJobs against the mock julia code.

Each CalcJob is run to completion with :func:`aiida.engine.run_get_node`; the
mock ``julia`` (see ``conftest.py``) fakes the outputs a real driver would leave
behind, so no Julia install is required.
"""

import pathlib

import pytest
from aiida import orm
from aiida.engine import run_get_node

from aiida_wannierjl.calculations import (
    CheckNeighborsCalculation,
    GenerateNeighborsCalculation,
    SplitCalculation,
)

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def _singlefile(name):
    """Return a ``SinglefileData`` wrapping a fixture file."""
    return orm.SinglefileData(file=str(FIXTURES / name))


def _w90_file_inputs():
    """The full explicit Wannier90 file set used by check/split."""
    return {
        "win_file": _singlefile("aiida.win"),
        "chk_file": _singlefile("aiida.chk"),
        "amn_file": _singlefile("aiida.amn"),
        "mmn_file": _singlefile("aiida.mmn"),
        "eig_file": _singlefile("aiida.eig"),
    }


# --------------------------------------------------------------------------- #
# GenerateNeighbors
# --------------------------------------------------------------------------- #
def test_generate_neighbors(mock_julia_code):
    builder = GenerateNeighborsCalculation.get_builder()
    builder.code = mock_julia_code
    builder.win_file = _singlefile("aiida.win")

    _, node = run_get_node(builder)

    assert node.is_finished_ok, node.exit_status
    assert "nnkp_file" in node.outputs
    assert node.outputs.nnkp_file.filename == "cubic.nnkp"


# --------------------------------------------------------------------------- #
# CheckNeighbors
# --------------------------------------------------------------------------- #
def test_check_neighbors(mock_julia_code):
    builder = CheckNeighborsCalculation.get_builder()
    builder.code = mock_julia_code
    for key, value in _w90_file_inputs().items():
        builder[key] = value

    _, node = run_get_node(builder)

    assert node.is_finished_ok, node.exit_status
    assert node.outputs.has_cubic_neighbors.value is True


def test_check_neighbors_missing_required_file_fails_validation(mock_julia_code):
    """Omitting a required file (``chk``) should be rejected before submission."""
    builder = CheckNeighborsCalculation.get_builder()
    builder.code = mock_julia_code
    builder.win_file = _singlefile("aiida.win")
    builder.amn_file = _singlefile("aiida.amn")
    builder.mmn_file = _singlefile("aiida.mmn")
    builder.eig_file = _singlefile("aiida.eig")

    with pytest.raises(ValueError):
        run_get_node(builder)


# --------------------------------------------------------------------------- #
# Split
# --------------------------------------------------------------------------- #
def test_split_default_outdirs(mock_julia_code):
    builder = SplitCalculation.get_builder()
    builder.code = mock_julia_code
    for key, value in _w90_file_inputs().items():
        builder[key] = value
    builder.indices = orm.List(list=[[1, 2], [3, 4]])

    results, node = run_get_node(builder)

    assert node.is_finished_ok, node.exit_status
    assert set(results["blocks"]) == {"block_0", "block_1"}
    assert set(results["win_files"]) == {"block_0", "block_1"}
    assert set(results["u_matrices"]) == {"block_0", "block_1"}

    # The block FolderData carries amn/eig/mmn but deliberately NOT the .win.
    block = results["blocks"]["block_0"]
    assert set(block.base.repository.list_object_names()) == {"aiida.amn", "aiida.eig", "aiida.mmn"}
    assert results["win_files"]["block_0"].filename == "aiida.win"
    assert results["u_matrices"]["block_0"].filename == "aiida_split.amn"


def test_split_explicit_outdirs(mock_julia_code):
    builder = SplitCalculation.get_builder()
    builder.code = mock_julia_code
    for key, value in _w90_file_inputs().items():
        builder[key] = value
    builder.indices = orm.List(list=[[1], [2]])
    builder.outdirs = orm.List(list=["groupA", "groupB"])

    results, node = run_get_node(builder)

    assert node.is_finished_ok, node.exit_status
    assert set(results["blocks"]) == {"groupA", "groupB"}


def test_split_seedname_override(mock_julia_code):
    builder = SplitCalculation.get_builder()
    builder.code = mock_julia_code
    for key, value in _w90_file_inputs().items():
        builder[key] = value
    builder.indices = orm.List(list=[[1, 2]])
    builder.metadata.options.seedname = "wann"

    results, node = run_get_node(builder)

    assert node.is_finished_ok, node.exit_status
    block = results["blocks"]["block_0"]
    assert set(block.base.repository.list_object_names()) == {"wann.amn", "wann.eig", "wann.mmn"}
    assert results["win_files"]["block_0"].filename == "wann.win"


# --------------------------------------------------------------------------- #
# Failure paths
# --------------------------------------------------------------------------- #
def test_missing_results_file(mock_julia_code_no_results):
    builder = GenerateNeighborsCalculation.get_builder()
    builder.code = mock_julia_code_no_results
    builder.win_file = _singlefile("aiida.win")

    _, node = run_get_node(builder)

    expected = GenerateNeighborsCalculation.spec().exit_codes.ERROR_MISSING_RESULTS_FILE.status
    assert node.exit_status == expected


def test_julia_failure(mock_julia_code_broken):
    builder = GenerateNeighborsCalculation.get_builder()
    builder.code = mock_julia_code_broken
    builder.win_file = _singlefile("aiida.win")

    _, node = run_get_node(builder)

    expected = GenerateNeighborsCalculation.spec().exit_codes.ERROR_JULIA_FAILURE.status
    assert node.exit_status == expected
