"""Parser for :class:`SplitCalculation`."""

import io
import re

from aiida import orm
from aiida.engine import ExitCode

from .base import WannierJLBaseParser

# Extensions that make up a block folder (the ``.win`` is emitted separately).
_BLOCK_EXTS = ("amn", "eig", "mmn")


def _link_label(outdir):
    """Turn an outdir name into a valid AiiDA link label.

    The ``outdirs`` input validator already restricts names to ``[A-Za-z0-9_]+``,
    so this is the identity for valid inputs; it stays as a defensive guard.
    """
    return re.sub(r"\W", "_", outdir)


class SplitParser(WannierJLBaseParser):
    """Emit per-block ``blocks``/``win_files``/``u_matrices`` outputs."""

    def _parse_results(self, results):
        outdirs = results.get("outdirs")
        if not outdirs:
            return self.exit_codes.ERROR_INVALID_RESULTS

        seedname = self.node.get_option("seedname")
        repository = self.retrieved.base.repository

        for outdir in outdirs:
            names = set(repository.list_object_names(outdir))
            expected = {f"{seedname}.{ext}" for ext in _BLOCK_EXTS}
            expected |= {f"{seedname}.win", f"{seedname}_split.amn"}
            missing = sorted(expected - names)
            if missing:
                self.logger.error(f"block `{outdir}` is missing output files: {missing}")
                return self.exit_codes.ERROR_MISSING_OUTPUT_FILES

            label = _link_label(outdir)

            block = orm.FolderData()
            for ext in _BLOCK_EXTS:
                filename = f"{seedname}.{ext}"
                content = self._read_bytes(f"{outdir}/{filename}")
                block.base.repository.put_object_from_bytes(content, filename)
            self.out(f"blocks.{label}", block)

            win = self._read_bytes(f"{outdir}/{seedname}.win")
            self.out(f"win_files.{label}", orm.SinglefileData(io.BytesIO(win), filename=f"{seedname}.win"))

            u_matrix = self._read_bytes(f"{outdir}/{seedname}_split.amn")
            self.out(
                f"u_matrices.{label}",
                orm.SinglefileData(io.BytesIO(u_matrix), filename=f"{seedname}_split.amn"),
            )

        return ExitCode(0)
