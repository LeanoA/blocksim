"""Graph operations for BlockSim: dependency graph, topological sort, loop detection.

This module builds a directed graph (NetworkX DiGraph) from block connections
and provides:
- ``build_graph``: construct a dependency graph from blocks and connections
- ``topological_sort``: compute execution order via topological sort
- ``detect_algebraic_loops``: find cycles that are NOT broken by Delay blocks
- ``AlgebraicLoopError``: raised when an unbreakable cycle is detected
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import networkx as nx

from blocksim.core.block import Block, Connection


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class AlgebraicLoopError(Exception):
    """Raised when the block graph contains a cycle with no Delay block.

    Parameters
    ----------
    cycle:
        Ordered list of block IDs forming the cycle.
    """

    def __init__(self, cycle: list[str]) -> None:
        self.cycle = cycle
        path = " → ".join(cycle + [cycle[0]])
        super().__init__(
            f"Algebraic loop detected: {path}. "
            "Insert a Delay block to break the loop."
        )


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


def build_graph(
    blocks: Mapping[str, Block],
    connections: Sequence[Connection],
) -> nx.DiGraph:
    """Build a NetworkX directed graph from blocks and connections.

    Each block becomes a node (keyed by ``block.id``).  Each connection
    adds a directed edge ``source_block → target_block``.

    Parameters
    ----------
    blocks:
        Mapping of block ID → Block instance.
    connections:
        Sequence of :class:`Connection` objects linking ports.

    Returns
    -------
    nx.DiGraph
        The dependency graph.
    """
    graph = nx.DiGraph()

    # Add every block as a node (even if unconnected).
    for block_id, block in blocks.items():
        graph.add_node(block_id, block=block)

    # Add edges from connections.
    for conn in connections:
        graph.add_edge(
            conn.source_block_id,
            conn.target_block_id,
            connection=conn,
        )

    return graph


# ---------------------------------------------------------------------------
# Topological sort
# ---------------------------------------------------------------------------


def topological_sort(
    graph: nx.DiGraph,
    blocks: Mapping[str, Block],
) -> list[Block]:
    """Return blocks in topological (execution) order.

    Before sorting, edges entering Delay blocks are temporarily removed so
    that valid feedback loops through Delay blocks don't prevent a DAG sort.

    Parameters
    ----------
    graph:
        The dependency graph (from :func:`build_graph`).
    blocks:
        Mapping of block ID → Block instance.

    Returns
    -------
    list[Block]
        Blocks sorted in execution order.

    Raises
    ------
    AlgebraicLoopError
        If the graph contains a cycle that is NOT broken by a Delay block.
    """
    # First check for unbreakable algebraic loops.
    detect_algebraic_loops(graph, blocks)

    # Create a working copy and remove edges *into* non-feedthrough blocks.
    # Non-feedthrough blocks (Delay, stateful blocks like Integrator/Inductor/Capacitor)
    # don't have direct input-to-output dependency, so their incoming edges
    # don't create algebraic dependencies.
    work = graph.copy()
    for block_id, block in blocks.items():
        if _is_non_feedthrough_block(block):
            # Remove all incoming edges to this block.
            in_edges = list(work.in_edges(block_id))
            work.remove_edges_from(in_edges)

    # The working graph should now be a DAG.
    order = list(nx.topological_sort(work))
    return [blocks[bid] for bid in order]


# ---------------------------------------------------------------------------
# Algebraic loop detection
# ---------------------------------------------------------------------------


def detect_algebraic_loops(
    graph: nx.DiGraph,
    blocks: Mapping[str, Block],
) -> None:
    """Check the graph for algebraic loops (cycles without a Delay block).

    A cycle that passes through at least one Delay block is considered valid
    because the Delay introduces a one-step time lag that breaks the
    algebraic dependency.

    Parameters
    ----------
    graph:
        The dependency graph.
    blocks:
        Mapping of block ID → Block instance.

    Raises
    ------
    AlgebraicLoopError
        If any cycle exists that does NOT contain a Delay block.
    """
    # Build a reduced graph without edges into non-feedthrough blocks.
    # Non-feedthrough blocks (Delay, stateful ODE blocks) break algebraic
    # dependencies because their output depends on state, not current inputs.
    reduced = graph.copy()
    for block_id, block in blocks.items():
        if _is_non_feedthrough_block(block):
            in_edges = list(reduced.in_edges(block_id))
            reduced.remove_edges_from(in_edges)

    # If the reduced graph has cycles, they are algebraic loops.
    try:
        cycle = nx.find_cycle(reduced)
        # cycle is a list of (u, v) edges — extract the node path.
        cycle_path = [edge[0] for edge in cycle]
        raise AlgebraicLoopError(cycle_path)
    except nx.NetworkXNoCycle:
        # No cycles — graph is valid.
        pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_non_feedthrough_block(block: Block) -> bool:
    """Return True if *block* has no direct feedthrough from inputs to outputs.

    A non-feedthrough block's outputs depend only on its internal state,
    not on the current step's inputs.  This means the block can safely
    break algebraic loops because the output is determined by the state
    from the previous integration step.

    Two categories of blocks qualify:
    1. Delay blocks (explicitly named with 'Delay' in class name)
    2. Stateful blocks (``state_size > 0``) — these output their ODE state,
       which is computed by the solver, not by direct input feedthrough.

    This mirrors Simulink's treatment of Integration blocks as non-direct-
    feedthrough, allowing them to break algebraic loops.
    """
    # Delay blocks are always non-feedthrough.
    if "Delay" in type(block).__name__:
        return True
    # Stateful blocks (Integrator, Inductor, Capacitor, etc.) output
    # their state variables, which don't depend on current-step inputs.
    if block.state_size > 0:
        return True
    return False


def _is_delay_block(block: Block) -> bool:
    """Return True if *block* is a Delay-type block (loop breaker).

    Detection is based on the class name containing 'Delay'.  This avoids
    a circular import with the blocks package while remaining reliable for
    all Delay subclasses.

    .. deprecated:: Use :func:`_is_non_feedthrough_block` for cycle-breaking.
    """
    return "Delay" in type(block).__name__
