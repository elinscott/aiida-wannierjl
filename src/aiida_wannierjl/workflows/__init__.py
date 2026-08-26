"""High-level orchestration of the Wannier.jl CalcJobs.

Requires the ``workflows`` extra (aiida-workgraph + aiida-quantumespresso);
importing this subpackage without it raises an informative ``ImportError``
from :mod:`aiida_wannierjl.workflows.split`.
"""

from .split import split_wannierization

__all__ = ("split_wannierization",)
