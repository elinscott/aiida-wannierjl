"""Unit tests for the rendered Julia driver scripts.

These exercise the ``render_driver`` static helpers directly, so they need no
AiiDA engine, database or Julia install.
"""

from aiida_wannierjl.calculations import (
    CheckNeighborsCalculation,
    GenerateNeighborsCalculation,
    SplitCalculation,
)


def test_generate_driver_seedname():
    script = GenerateNeighborsCalculation.render_driver("wann")
    assert 'seedname = "wann"' in script
    assert 'Wannier.write_nnkp_cubic("cubic.nnkp", seedname * ".win")' in script
    assert '"success" => true' in script


def test_check_driver_seedname():
    script = CheckNeighborsCalculation.render_driver("foo")
    assert 'seedname = "foo"' in script
    assert 'read_w90_with_chk(seedname, seedname * ".chk")' in script
    assert "Wannier.has_cubic_neighbors(model.kstencil)" in script
    assert '"has_cubic_neighbors" => has_cubic' in script


def test_split_driver_indices_and_outdirs_literals():
    script = SplitCalculation.render_driver("aiida", [[1, 2], [3]], ["block_0", "block_1"], None)
    assert 'seedname = "aiida"' in script
    # Python ``str`` of a list of lists is valid Julia ``Vector{Vector{Int}}``.
    assert "indices = [[1, 2], [3]]" in script
    assert 'outdirs = ["block_0", "block_1"]' in script
    assert "cubic_mmn = nothing" in script
    assert "Wannier.Tools.mrwf(seedname, indices, outdirs, cubic_mmn)" in script
    assert '"outdirs" => outdirs' in script


def test_split_driver_with_cubic_mmn():
    script = SplitCalculation.render_driver("aiida", [[1]], ["only"], "cubic.mmn")
    assert 'cubic_mmn = "cubic.mmn"' in script
