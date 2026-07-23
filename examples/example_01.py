#!/usr/bin/env python
"""Run a ``wannierjl.generate_neighbors`` calculation on localhost.

This example generates a ``cubic.nnkp`` file from a small wannier90 input
(``.win``) using the ``wannierjl.generate_neighbors`` CalcJob.

Assumptions:

* A Julia code node labelled ``wannierjl@localhost`` already exists. Create one
  with :func:`aiida_wannierjl.helpers.get_wannierjl_code` after running
  :func:`aiida_wannierjl.helpers.setup_julia_environment` once on the machine
  (see the get-started guide in the docs).
* An AiiDA profile is loaded (e.g. ``verdi profile setdefault <name>``).

Usage::

    ./example_01.py                       # uses code label wannierjl@localhost
    ./example_01.py wannierjl@othercomputer
"""

import sys
import tempfile
from pathlib import Path

from aiida import load_profile
from aiida.engine import run_get_node
from aiida.orm import SinglefileData, load_code
from aiida.plugins import CalculationFactory

CODE_LABEL = "wannierjl@localhost"

# A minimal wannier90 input file. ``generate_neighbors`` only needs the cell and
# k-point mesh to work out the cubic b-vectors, so this deliberately stays tiny.
WIN_CONTENT = """\
num_wann = 1
num_bands = 1

begin unit_cell_cart
Ang
 3.0  0.0  0.0
 0.0  3.0  0.0
 0.0  0.0  3.0
end unit_cell_cart

begin atoms_frac
H  0.0  0.0  0.0
end atoms_frac

mp_grid = 2 2 2

begin kpoints
 0.00  0.00  0.00
 0.50  0.00  0.00
 0.00  0.50  0.00
 0.50  0.50  0.00
 0.00  0.00  0.50
 0.50  0.00  0.50
 0.00  0.50  0.50
 0.50  0.50  0.50
end kpoints
"""


def main(code_label=CODE_LABEL):
    """Submit a GenerateNeighbors calculation and print the resulting nnkp file."""
    load_profile()

    code = load_code(code_label)

    # Write the .win to a temporary file and wrap it as a SinglefileData node.
    with tempfile.TemporaryDirectory() as tmpdir:
        win_path = Path(tmpdir) / "aiida.win"
        win_path.write_text(WIN_CONTENT)
        win_file = SinglefileData(file=str(win_path))

    inputs = {
        "code": code,
        "win_file": win_file,
        "metadata": {
            "description": "Generate cubic.nnkp with the aiida-wannierjl plugin",
            "options": {"resources": {"num_machines": 1}},
        },
    }

    # Entry-point access only, so the example stays decoupled from the package layout.
    generate_neighbors = CalculationFactory("wannierjl.generate_neighbors")
    results, node = run_get_node(generate_neighbors, **inputs)

    print(f"GenerateNeighbors finished: {node.process_state.value} (exit {node.exit_status})")
    nnkp = results["nnkp_file"]
    print(f"Generated nnkp SinglefileData<{nnkp.pk}>, filename: {nnkp.filename}")
    print("--- cubic.nnkp ---")
    print(nnkp.get_content())


if __name__ == "__main__":
    main(*sys.argv[1:])
