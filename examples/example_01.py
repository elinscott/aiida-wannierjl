#!/usr/bin/env python
"""Run a test calculation on localhost.

Usage: ./example_01.py
"""

from os import path

import click
from aiida import cmdline, engine
from aiida.plugins import CalculationFactory, DataFactory
from aiida_wannierjl import helpers

INPUT_DIR = path.join(path.dirname(path.realpath(__file__)), "input_files")


def test_run(wannierjl_code):
    """Run a calculation on the localhost computer.

    Uses test helpers to create AiiDA Code on the fly.
    """
    if not wannierjl_code:
        # get code
        computer = helpers.get_computer()
        wannierjl_code = helpers.get_code(
            entry_point="wannierjl", computer=computer
        )

    # Prepare input parameters
    diff_parameters = DataFactory("wannierjl")
    parameters = diff_parameters({"ignore-case": True})

    singlefile_data = DataFactory("core.singlefile")
    file1 = singlefile_data(file=path.join(INPUT_DIR, "file1.txt"))
    file2 = singlefile_data(file=path.join(INPUT_DIR, "file2.txt"))

    # set up calculation
    inputs = {
        "code": wannierjl_code,
        "parameters": parameters,
        "file1": file1,
        "file2": file2,
        "metadata": {
            "description": "Test job submission with the aiida_wannierjl plugin",
        },
    }

    # Note: in order to submit your calculation to the aiida daemon, do:
    # from aiida.engine import submit
    # future = submit(CalculationFactory('wannierjl'), **inputs)
    result = engine.run(CalculationFactory("wannierjl"), **inputs)

    computed_diff = result["wannierjl"].get_content()
    print(f"Computed diff between files: \n{computed_diff}")


@click.command()
@cmdline.utils.decorators.with_dbenv()
@cmdline.params.options.CODE()
def cli(code):
    """Run example.

    Example usage: $ ./example_01.py --code diff@localhost

    Alternative (creates diff@localhost-test code): $ ./example_01.py

    Help: $ ./example_01.py --help
    """
    test_run(code)


if __name__ == "__main__":
    cli()  # pylint: disable=no-value-for-parameter
