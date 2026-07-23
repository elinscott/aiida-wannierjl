"""``GenerateNeighborsCalculation`` -- generate a cubic ``.nnkp`` file."""

import textwrap

from aiida import orm

from .base import WannierJLCalcJob


class GenerateNeighborsCalculation(WannierJLCalcJob):
    """Generate a ``cubic.nnkp`` file with the six cubic nearest-neighbour b-vectors.

    Wraps ``Wannier.write_nnkp_cubic``. Only the ``.win`` file is required.
    """

    _REQUIRED_W90_FILES = ("win",)

    @classmethod
    def define(cls, spec):
        """Define the spec: only ``win_file`` is used; add the nnkp exit code."""
        super().define(spec)
        spec.inputs["metadata"]["options"]["parser_name"].default = "wannierjl.generate_neighbors"
        spec.output(
            "nnkp_file",
            valid_type=orm.SinglefileData,
            help="The generated ``cubic.nnkp`` file.",
        )
        spec.exit_code(
            303,
            "ERROR_MISSING_NNKP",
            message="The driver did not produce the expected `cubic.nnkp` file.",
        )

    @staticmethod
    def render_driver(seedname):
        """Return the Julia driver script for the given seedname."""
        return textwrap.dedent(
            f"""\
            using Wannier
            using JSON

            seedname = "{seedname}"

            Wannier.write_nnkp_cubic("cubic.nnkp", seedname * ".win")

            open("results.json", "w") do io
                JSON.print(io, Dict("success" => true))
            end
            """
        )

    def _render_driver_script(self):
        return self.render_driver(self.node.get_option("seedname"))

    def _retrieve_extra(self):
        return ["cubic.nnkp"]
