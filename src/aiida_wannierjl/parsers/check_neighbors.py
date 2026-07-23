"""Parser for :class:`~aiida_wannierjl.calculations.check_neighbors.CheckNeighborsCalculation`."""

from aiida import orm
from aiida.engine import ExitCode

from .base import WannierJLBaseParser


class CheckNeighborsParser(WannierJLBaseParser):
    """Emit the ``has_cubic_neighbors`` boolean output."""

    def _parse_results(self, results):
        if "has_cubic_neighbors" not in results:
            return self.exit_codes.ERROR_INVALID_RESULTS

        self.out("has_cubic_neighbors", orm.Bool(bool(results["has_cubic_neighbors"])))
        return ExitCode(0)
