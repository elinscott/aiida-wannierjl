"""Abstract base :class:`~aiida.parsers.Parser` for the Wannier.jl CalcJobs.

The base parser handles everything common to the three operations: detecting a
Julia failure from ``julia.out``, loading and JSON-decoding ``results.json``, and
mapping problems to the exit codes declared on the CalcJob spec. Subclasses only
implement :meth:`~aiida_wannierjl.parsers.base.WannierJLBaseParser._parse_results`, which
receives the decoded results dict.
"""

import json

from aiida.parsers import Parser

from ..calculations.base import RESULTS_FILE, STDOUT_FILE

# Markers Julia prints to stderr (joined into julia.out) on an uncaught error.
_JULIA_ERROR_MARKERS = ("ERROR:", "LoadError")


class WannierJLBaseParser(Parser):
    """Base parser: check for Julia failure, load ``results.json``, delegate."""

    def parse(self, **kwargs):
        """Common parse flow shared by all Wannier.jl parsers."""
        retrieved = self.retrieved
        names = retrieved.base.repository.list_object_names()

        # 1. Surface a Julia crash first (its markers land in the joined stdout).
        if STDOUT_FILE in names:
            stdout = retrieved.base.repository.get_object_content(STDOUT_FILE)
            if any(marker in stdout for marker in _JULIA_ERROR_MARKERS):
                return self.exit_codes.ERROR_JULIA_FAILURE

        # 2. The driver must have written the machine-readable results file.
        if RESULTS_FILE not in names:
            return self.exit_codes.ERROR_MISSING_RESULTS_FILE

        try:
            results = json.loads(retrieved.base.repository.get_object_content(RESULTS_FILE))
        except (ValueError, UnicodeDecodeError):
            return self.exit_codes.ERROR_INVALID_RESULTS

        return self._parse_results(results)

    def _parse_results(self, results):
        """Turn the decoded ``results.json`` dict into output nodes.

        Return an :class:`~aiida.engine.ExitCode` (``ExitCode(0)`` on success) or a
        named exit code from the CalcJob spec.
        """
        raise NotImplementedError

    def _read_bytes(self, path):
        """Return the bytes of ``path`` inside the retrieved folder."""
        return self.retrieved.base.repository.get_object_content(path, mode="rb")
