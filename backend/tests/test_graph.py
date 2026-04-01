"""Tests for graph operations: build_graph, topological_sort, algebraic loop detection.

Covers spec scenarios:
- topo-order: A→B→C sorts to [A, B, C]
- loop-detect: A→B→A raises AlgebraicLoopError
- delay-break: A→B→Delay→A breaks cycle and sorts successfully
"""

from __future__ import annotations

import numpy as np
import pytest

from blocksim.core.block import Block, Connection, InputPort, OutputPort
from blocksim.core.graph import (
    AlgebraicLoopError,
    build_graph,
    detect_algebraic_loops,
    topological_sort,
)


# ---------------------------------------------------------------------------
# Test block helpers
# ---------------------------------------------------------------------------


class PassthroughBlock(Block):
    """Simple block: copies input to output."""

    _input_port_defs = [InputPort("in")]
    _output_port_defs = [OutputPort("out")]

    def compute(self, t: float) -> None:
        self.set_output("out", self.get_input("in"))


class SourceBlock(Block):
    """Source block: no inputs, one output."""

    _output_port_defs = [OutputPort("out")]

    def compute(self, t: float) -> None:
        self.set_output("out", 1.0)


class DelayBlock(Block):
    """Delay block: acts as a loop breaker. Name contains 'Delay'."""

    _input_port_defs = [InputPort("in")]
    _output_port_defs = [OutputPort("out")]

    def compute(self, t: float) -> None:
        self.set_output("out", self.get_input("in"))


# ---------------------------------------------------------------------------
# build_graph tests
# ---------------------------------------------------------------------------


class TestBuildGraph:
    """Tests for build_graph."""

    def test_empty_graph(self):
        graph = build_graph({}, [])
        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0

    def test_single_block_no_connections(self):
        a = SourceBlock(block_id="A")
        blocks = {"A": a}
        graph = build_graph(blocks, [])
        assert "A" in graph.nodes
        assert len(graph.edges) == 0

    def test_two_blocks_one_connection(self):
        a = SourceBlock(block_id="A")
        b = PassthroughBlock(block_id="B")
        blocks = {"A": a, "B": b}
        conns = [Connection("A", "out", "B", "in")]
        graph = build_graph(blocks, conns)
        assert graph.has_edge("A", "B")
        assert not graph.has_edge("B", "A")

    def test_graph_preserves_block_references(self):
        a = SourceBlock(block_id="A")
        blocks = {"A": a}
        graph = build_graph(blocks, [])
        assert graph.nodes["A"]["block"] is a

    def test_chain_three_blocks(self):
        a = SourceBlock(block_id="A")
        b = PassthroughBlock(block_id="B")
        c = PassthroughBlock(block_id="C")
        blocks = {"A": a, "B": b, "C": c}
        conns = [
            Connection("A", "out", "B", "in"),
            Connection("B", "out", "C", "in"),
        ]
        graph = build_graph(blocks, conns)
        assert len(graph.edges) == 2
        assert graph.has_edge("A", "B")
        assert graph.has_edge("B", "C")


# ---------------------------------------------------------------------------
# topological_sort tests
# ---------------------------------------------------------------------------


class TestTopologicalSort:
    """Tests for topological_sort (spec: topo-order scenario)."""

    def test_chain_abc_sorted_in_order(self):
        """GIVEN blocks A→B→C connected in series
        WHEN DynamicSystem resolves execution order
        THEN blocks execute in order [A, B, C]
        """
        a = SourceBlock(block_id="A")
        b = PassthroughBlock(block_id="B")
        c = PassthroughBlock(block_id="C")
        blocks = {"A": a, "B": b, "C": c}
        conns = [
            Connection("A", "out", "B", "in"),
            Connection("B", "out", "C", "in"),
        ]
        graph = build_graph(blocks, conns)
        sorted_blocks = topological_sort(graph, blocks)
        assert [blk.id for blk in sorted_blocks] == ["A", "B", "C"]

    def test_single_block(self):
        a = SourceBlock(block_id="A")
        blocks = {"A": a}
        graph = build_graph(blocks, [])
        sorted_blocks = topological_sort(graph, blocks)
        assert [blk.id for blk in sorted_blocks] == ["A"]

    def test_diamond_dependency(self):
        """A → B, A → C, B → D, C → D: both B and C after A, D last."""
        a = SourceBlock(block_id="A")
        b = PassthroughBlock(block_id="B")
        c = PassthroughBlock(block_id="C")
        d = PassthroughBlock(block_id="D")
        blocks = {"A": a, "B": b, "C": c, "D": d}
        conns = [
            Connection("A", "out", "B", "in"),
            Connection("A", "out", "C", "in"),
            Connection("B", "out", "D", "in"),
            Connection("C", "out", "D", "in"),
        ]
        graph = build_graph(blocks, conns)
        sorted_blocks = topological_sort(graph, blocks)
        ids = [blk.id for blk in sorted_blocks]
        # A must be first, D must be last.
        assert ids[0] == "A"
        assert ids[-1] == "D"
        # B and C must both be before D.
        assert ids.index("B") < ids.index("D")
        assert ids.index("C") < ids.index("D")

    def test_independent_blocks(self):
        """Unconnected blocks should all appear (order doesn't matter)."""
        a = SourceBlock(block_id="A")
        b = SourceBlock(block_id="B")
        blocks = {"A": a, "B": b}
        graph = build_graph(blocks, [])
        sorted_blocks = topological_sort(graph, blocks)
        assert set(blk.id for blk in sorted_blocks) == {"A", "B"}


# ---------------------------------------------------------------------------
# Algebraic loop detection tests
# ---------------------------------------------------------------------------


class TestAlgebraicLoopDetection:
    """Tests for algebraic loop detection (spec: loop-detect scenario)."""

    def test_simple_cycle_raises(self):
        """GIVEN blocks A→B→A forming a cycle with no Delay block
        WHEN DynamicSystem validates the graph
        THEN AlgebraicLoopError is raised listing the cycle path
        """
        a = PassthroughBlock(block_id="A")
        b = PassthroughBlock(block_id="B")
        blocks = {"A": a, "B": b}
        conns = [
            Connection("A", "out", "B", "in"),
            Connection("B", "out", "A", "in"),
        ]
        graph = build_graph(blocks, conns)
        with pytest.raises(AlgebraicLoopError) as exc_info:
            detect_algebraic_loops(graph, blocks)
        # The cycle path should include both A and B.
        assert set(exc_info.value.cycle) == {"A", "B"}

    def test_self_loop_raises(self):
        """A block connected to itself creates an algebraic loop."""
        a = PassthroughBlock(block_id="A")
        blocks = {"A": a}
        conns = [Connection("A", "out", "A", "in")]
        graph = build_graph(blocks, conns)
        with pytest.raises(AlgebraicLoopError):
            detect_algebraic_loops(graph, blocks)

    def test_three_block_cycle_raises(self):
        """A→B→C→A forms a 3-block cycle."""
        a = PassthroughBlock(block_id="A")
        b = PassthroughBlock(block_id="B")
        c = PassthroughBlock(block_id="C")
        blocks = {"A": a, "B": b, "C": c}
        conns = [
            Connection("A", "out", "B", "in"),
            Connection("B", "out", "C", "in"),
            Connection("C", "out", "A", "in"),
        ]
        graph = build_graph(blocks, conns)
        with pytest.raises(AlgebraicLoopError):
            detect_algebraic_loops(graph, blocks)

    def test_no_cycle_passes(self):
        """A→B→C has no cycle, should not raise."""
        a = SourceBlock(block_id="A")
        b = PassthroughBlock(block_id="B")
        c = PassthroughBlock(block_id="C")
        blocks = {"A": a, "B": b, "C": c}
        conns = [
            Connection("A", "out", "B", "in"),
            Connection("B", "out", "C", "in"),
        ]
        graph = build_graph(blocks, conns)
        # Should not raise.
        detect_algebraic_loops(graph, blocks)

    def test_topological_sort_raises_on_cycle(self):
        """topological_sort should also raise AlgebraicLoopError on cycles."""
        a = PassthroughBlock(block_id="A")
        b = PassthroughBlock(block_id="B")
        blocks = {"A": a, "B": b}
        conns = [
            Connection("A", "out", "B", "in"),
            Connection("B", "out", "A", "in"),
        ]
        graph = build_graph(blocks, conns)
        with pytest.raises(AlgebraicLoopError):
            topological_sort(graph, blocks)


# ---------------------------------------------------------------------------
# Delay block cycle-breaking tests
# ---------------------------------------------------------------------------


class TestDelayCycleBreaking:
    """Tests for Delay block cycle-breaking (spec: delay-break scenario)."""

    def test_delay_breaks_simple_cycle(self):
        """GIVEN blocks A→B→Delay→A forming a cycle
        WHEN DynamicSystem resolves execution order
        THEN the cycle is broken at the Delay block and execution proceeds
        """
        a = PassthroughBlock(block_id="A")
        b = PassthroughBlock(block_id="B")
        d = DelayBlock(block_id="Delay1")
        blocks = {"A": a, "B": b, "Delay1": d}
        conns = [
            Connection("A", "out", "B", "in"),
            Connection("B", "out", "Delay1", "in"),
            Connection("Delay1", "out", "A", "in"),
        ]
        graph = build_graph(blocks, conns)
        # Should NOT raise — Delay breaks the loop.
        sorted_blocks = topological_sort(graph, blocks)
        ids = [blk.id for blk in sorted_blocks]
        # All three blocks should appear.
        assert set(ids) == {"A", "B", "Delay1"}

    def test_delay_in_cycle_does_not_raise(self):
        """detect_algebraic_loops should pass when Delay is in the cycle."""
        a = PassthroughBlock(block_id="A")
        d = DelayBlock(block_id="Delay1")
        blocks = {"A": a, "Delay1": d}
        conns = [
            Connection("A", "out", "Delay1", "in"),
            Connection("Delay1", "out", "A", "in"),
        ]
        graph = build_graph(blocks, conns)
        # Should not raise.
        detect_algebraic_loops(graph, blocks)

    def test_cycle_without_delay_still_raises_despite_delay_elsewhere(self):
        """A cycle A→B→A without Delay should still raise even if Delay exists elsewhere."""
        a = PassthroughBlock(block_id="A")
        b = PassthroughBlock(block_id="B")
        d = DelayBlock(block_id="Delay1")
        c = PassthroughBlock(block_id="C")
        blocks = {"A": a, "B": b, "C": c, "Delay1": d}
        # Cycle: A→B→A (no Delay).  Delay is elsewhere: C→Delay1.
        conns = [
            Connection("A", "out", "B", "in"),
            Connection("B", "out", "A", "in"),
            Connection("C", "out", "Delay1", "in"),
        ]
        graph = build_graph(blocks, conns)
        with pytest.raises(AlgebraicLoopError):
            detect_algebraic_loops(graph, blocks)


# ---------------------------------------------------------------------------
# AlgebraicLoopError tests
# ---------------------------------------------------------------------------


class TestAlgebraicLoopError:
    """Tests for AlgebraicLoopError attributes."""

    def test_error_contains_cycle_path(self):
        err = AlgebraicLoopError(["A", "B", "C"])
        assert err.cycle == ["A", "B", "C"]
        assert "A → B → C → A" in str(err)

    def test_error_suggests_delay(self):
        err = AlgebraicLoopError(["X", "Y"])
        assert "Delay" in str(err)
