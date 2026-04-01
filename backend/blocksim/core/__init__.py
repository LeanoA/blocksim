"""Core simulation engine: Block ABC, graph operations, solvers, system container."""

from blocksim.core.block import (
    Block,
    Connection,
    InputPort,
    OutputPort,
    Port,
    PortAlreadyConnectedError,
    PortDirection,
)
from blocksim.core.graph import (
    AlgebraicLoopError,
    build_graph,
    detect_algebraic_loops,
    topological_sort,
)
from blocksim.core.solver import (
    EulerSolver,
    RK4Solver,
    ScipySolver,
    SimulationResult,
    Solver,
    get_solver,
)
from blocksim.core.system import (
    DuplicateBlockIdError,
    DynamicSystem,
    InvalidConnectionError,
    SimulationDivergenceError,
    SystemNotCompiledError,
)

__all__ = [
    # block.py
    "Block",
    "Connection",
    "InputPort",
    "OutputPort",
    "Port",
    "PortAlreadyConnectedError",
    "PortDirection",
    # graph.py
    "AlgebraicLoopError",
    "build_graph",
    "detect_algebraic_loops",
    "topological_sort",
    # solver.py
    "EulerSolver",
    "RK4Solver",
    "ScipySolver",
    "SimulationResult",
    "Solver",
    "get_solver",
    # system.py
    "DuplicateBlockIdError",
    "DynamicSystem",
    "InvalidConnectionError",
    "SimulationDivergenceError",
    "SystemNotCompiledError",
]
