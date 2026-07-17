"""Parser plugins for the Wannier.jl CalcJobs.

Each parser reads the machine-readable ``results.json`` emitted by its
driver script and turns it into AiiDA output nodes.
"""

from .base import WannierJLBaseParser
from .check_neighbors import CheckNeighborsParser
from .generate_neighbors import GenerateNeighborsParser
from .split import SplitParser

__all__ = (
    "WannierJLBaseParser",
    "CheckNeighborsParser",
    "GenerateNeighborsParser",
    "SplitParser",
)
