"""Parser for :class:`GenerateNeighborsCalculation`."""

import io

from aiida import orm
from aiida.engine import ExitCode

from .base import WannierJLBaseParser


class GenerateNeighborsParser(WannierJLBaseParser):
    """Emit the generated ``cubic.nnkp`` as a ``SinglefileData`` output."""

    def _parse_results(self, results):
        names = self.retrieved.base.repository.list_object_names()
        if "cubic.nnkp" not in names:
            return self.exit_codes.ERROR_MISSING_NNKP

        content = self._read_bytes("cubic.nnkp")
        self.out("nnkp_file", orm.SinglefileData(io.BytesIO(content), filename="cubic.nnkp"))
        return ExitCode(0)
