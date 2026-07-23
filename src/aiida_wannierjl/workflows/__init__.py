"""High-level orchestration of the Wannier.jl CalcJobs.

The split workflow is an aiida-workgraph ``@task.graph`` (plain Python API, no
``aiida.workflows`` entry point). It requires the ``workflows`` extra
(aiida-workgraph + aiida-quantumespresso); importing this subpackage without it
raises an informative ``ImportError`` from :mod:`aiida_wannierjl.workflows.split`.
"""

from .split import split_wannierization

__all__ = ("split_wannierization",)
