"""``CheckNeighborsCalculation`` -- test for cubic nearest-neighbour b-vectors."""

import textwrap

from aiida import orm

from .base import WannierJLCalcJob


class CheckNeighborsCalculation(WannierJLCalcJob):
    """Check whether the default b-vectors contain the six cubic nearest neighbours.

    Wraps ``read_w90_with_chk`` + ``Wannier.has_cubic_neighbors``. Requires the
    full Wannier90 set: ``.win`` (explicit), ``.chk`` (via ``chk_file`` or the
    ``wannier90`` parent folder) and ``.amn``/``.mmn``/``.eig`` (via the matching
    ``*_file`` port or the ``pw2wannier90`` parent folder).
    """

    _REQUIRED_W90_FILES = ("win", "chk", "amn", "mmn", "eig")

    @classmethod
    def define(cls, spec):
        """Define the spec: full Wannier90 file set and the boolean output."""
        super().define(spec)
        spec.inputs["metadata"]["options"]["parser_name"].default = "wannierjl.check_neighbors"
        spec.output(
            "has_cubic_neighbors",
            valid_type=orm.Bool,
            help="Whether the default b-vectors contain the six cubic nearest neighbours.",
        )

    @staticmethod
    def render_driver(seedname):
        """Return the Julia driver script for the given seedname."""
        return textwrap.dedent(
            f"""\
            using Wannier
            using JSON

            seedname = "{seedname}"

            model = read_w90_with_chk(seedname, seedname * ".chk")
            has_cubic = Wannier.has_cubic_neighbors(model.kstencil)

            open("results.json", "w") do io
                JSON.print(io, Dict("has_cubic_neighbors" => has_cubic))
            end
            """
        )

    def _render_driver_script(self):
        return self.render_driver(self.node.get_option("seedname"))
