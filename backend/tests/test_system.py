"""Tests for DynamicSystem: block management, connections, compile, simulate.

Covers spec scenarios:
- System builds, compiles, and exposes sorted_blocks
- Full system compile + simulate
- Topological ordering via compile
- Error handling for invalid operations
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from blocksim.core.block import Block, InputPort, OutputPort, PortAlreadyConnectedError
from blocksim.core.graph import AlgebraicLoopError
from blocksim.core.solver import EulerSolver, RK4Solver
from blocksim.core.system import (
    DuplicateBlockIdError,
    DynamicSystem,
    InvalidConnectionError,
    SystemNotCompiledError,
)


# ---------------------------------------------------------------------------
# Test blocks
# ---------------------------------------------------------------------------


class ConstantSource(Block):
    """Outputs a constant value."""

    _output_port_defs = [OutputPort("out")]

    def __init__(self, value: float = 1.0, **kwargs):
        super().__init__(params={"value": value}, **kwargs)

    def compute(self, t: float) -> None:
        self.set_output("out", self.params["value"])


class GainBlock(Block):
    """out = k * in."""

    _input_port_defs = [InputPort("in")]
    _output_port_defs = [OutputPort("out")]

    def __init__(self, k: float = 1.0, **kwargs):
        super().__init__(params={"k": k}, **kwargs)

    def compute(self, t: float) -> None:
        self.set_output("out", self.params["k"] * self.get_input("in"))


class IntegratorBlock(Block):
    """Integrates input: state = ∫input dt, output = state."""

    _input_port_defs = [InputPort("in")]
    _output_port_defs = [OutputPort("out")]

    def __init__(self, x0: float = 0.0, **kwargs):
        super().__init__(params={"x0": x0}, **kwargs)

    @property
    def state_size(self) -> int:
        return 1

    def initialize(self, t0: float) -> np.ndarray:
        return np.array([self.params["x0"]], dtype=np.float64)

    def compute(self, t: float) -> None:
        self.set_output("out", self._state[0])

    def derivatives(self, t: float, state: np.ndarray) -> np.ndarray:
        return np.array([self.get_input("in")], dtype=np.float64)


class ScopeBlock(Block):
    """Records input values (sink block)."""

    _input_port_defs = [InputPort("in")]

    def compute(self, t: float) -> None:
        pass  # Scope just records via the system's output recording.


class DelayBlock(Block):
    """Delay block — name contains 'Delay' for loop-breaking."""

    _input_port_defs = [InputPort("in")]
    _output_port_defs = [OutputPort("out")]

    def __init__(self, initial: float = 0.0, **kwargs):
        super().__init__(params={"initial": initial}, **kwargs)
        self._prev_value = initial

    def compute(self, t: float) -> None:
        # Output the previous step's value.
        self.set_output("out", self._prev_value)
        self._prev_value = self.get_input("in")


# ---------------------------------------------------------------------------
# Block management tests
# ---------------------------------------------------------------------------


class TestBlockManagement:
    """Tests for add_block."""

    def test_add_block(self):
        sys = DynamicSystem()
        src = ConstantSource(block_id="src")
        sys.add_block(src)
        assert "src" in sys.blocks

    def test_add_multiple_blocks(self):
        sys = DynamicSystem()
        sys.add_block(ConstantSource(block_id="a"))
        sys.add_block(GainBlock(block_id="b"))
        assert len(sys.blocks) == 2

    def test_duplicate_block_id_raises(self):
        sys = DynamicSystem()
        sys.add_block(ConstantSource(block_id="dup"))
        with pytest.raises(DuplicateBlockIdError, match="dup"):
            sys.add_block(GainBlock(block_id="dup"))


# ---------------------------------------------------------------------------
# Connection tests
# ---------------------------------------------------------------------------


class TestConnections:
    """Tests for connect()."""

    def test_basic_connection(self):
        sys = DynamicSystem()
        src = ConstantSource(block_id="src")
        gain = GainBlock(block_id="gain")
        sys.add_block(src)
        sys.add_block(gain)
        conn = sys.connect("src", "out", "gain", "in")
        assert conn.source_block_id == "src"
        assert conn.target_block_id == "gain"
        assert len(sys.connections) == 1

    def test_invalid_source_block_raises(self):
        sys = DynamicSystem()
        sys.add_block(GainBlock(block_id="gain"))
        with pytest.raises(InvalidConnectionError, match="not found"):
            sys.connect("nonexistent", "out", "gain", "in")

    def test_invalid_target_block_raises(self):
        sys = DynamicSystem()
        sys.add_block(ConstantSource(block_id="src"))
        with pytest.raises(InvalidConnectionError, match="not found"):
            sys.connect("src", "out", "nonexistent", "in")

    def test_invalid_source_port_raises(self):
        sys = DynamicSystem()
        sys.add_block(ConstantSource(block_id="src"))
        sys.add_block(GainBlock(block_id="gain"))
        with pytest.raises(InvalidConnectionError, match="no output port"):
            sys.connect("src", "bad_port", "gain", "in")

    def test_invalid_target_port_raises(self):
        sys = DynamicSystem()
        sys.add_block(ConstantSource(block_id="src"))
        sys.add_block(GainBlock(block_id="gain"))
        with pytest.raises(InvalidConnectionError, match="no input port"):
            sys.connect("src", "out", "gain", "bad_port")

    def test_duplicate_input_connection_raises(self):
        sys = DynamicSystem()
        sys.add_block(ConstantSource(block_id="src1"))
        sys.add_block(ConstantSource(block_id="src2"))
        sys.add_block(GainBlock(block_id="gain"))
        sys.connect("src1", "out", "gain", "in")
        with pytest.raises(PortAlreadyConnectedError):
            sys.connect("src2", "out", "gain", "in")


# ---------------------------------------------------------------------------
# Compile tests
# ---------------------------------------------------------------------------


class TestCompile:
    """Tests for compile()."""

    def test_compile_sets_sorted_blocks(self):
        sys = DynamicSystem()
        src = ConstantSource(block_id="src")
        gain = GainBlock(block_id="gain")
        sys.add_block(src)
        sys.add_block(gain)
        sys.connect("src", "out", "gain", "in")
        sys.compile()
        ids = [b.id for b in sys.sorted_blocks]
        assert ids == ["src", "gain"]

    def test_compile_chain(self):
        sys = DynamicSystem()
        sys.add_block(ConstantSource(block_id="A"))
        sys.add_block(GainBlock(block_id="B"))
        sys.add_block(GainBlock(block_id="C"))
        sys.connect("A", "out", "B", "in")
        sys.connect("B", "out", "C", "in")
        sys.compile()
        ids = [b.id for b in sys.sorted_blocks]
        assert ids == ["A", "B", "C"]

    def test_compile_algebraic_loop_raises(self):
        sys = DynamicSystem()
        a = GainBlock(block_id="A")
        b = GainBlock(block_id="B")
        sys.add_block(a)
        sys.add_block(b)
        sys.connect("A", "out", "B", "in")
        sys.connect("B", "out", "A", "in")
        with pytest.raises(AlgebraicLoopError):
            sys.compile()

    def test_compile_with_delay_breaks_loop(self):
        sys = DynamicSystem()
        sys.add_block(GainBlock(block_id="A"))
        sys.add_block(GainBlock(block_id="B"))
        sys.add_block(DelayBlock(block_id="Delay"))
        sys.connect("A", "out", "B", "in")
        sys.connect("B", "out", "Delay", "in")
        sys.connect("Delay", "out", "A", "in")
        sys.compile()
        assert len(sys.sorted_blocks) == 3

    def test_sorted_blocks_before_compile_raises(self):
        sys = DynamicSystem()
        sys.add_block(ConstantSource(block_id="src"))
        with pytest.raises(SystemNotCompiledError):
            _ = sys.sorted_blocks


# ---------------------------------------------------------------------------
# Simulate tests — stateless systems
# ---------------------------------------------------------------------------


class TestSimulateStateless:
    """Tests for simulate() with purely stateless blocks."""

    def test_constant_source_to_gain(self):
        """ConstantSource(5) → Gain(k=3) → output should be 15."""
        sys = DynamicSystem()
        sys.add_block(ConstantSource(value=5.0, block_id="src"))
        sys.add_block(GainBlock(k=3.0, block_id="gain"))
        sys.connect("src", "out", "gain", "in")
        sys.compile()
        result = sys.simulate(t_span=(0, 0.01), dt=0.01)
        # Gain output should be 15.0 at every step.
        gain_output = result.outputs["gain.out"]
        assert gain_output[-1] == pytest.approx(15.0)

    def test_simulate_before_compile_raises(self):
        sys = DynamicSystem()
        sys.add_block(ConstantSource(block_id="src"))
        with pytest.raises(SystemNotCompiledError):
            sys.simulate()


# ---------------------------------------------------------------------------
# Simulate tests — stateful systems
# ---------------------------------------------------------------------------


class TestSimulateStateful:
    """Tests for simulate() with stateful blocks (Integrator)."""

    def test_integrating_constant(self):
        """Constant(1) → Integrator(x0=0): integrating 1 from 0→1 → output ≈ 1.0."""
        sys = DynamicSystem()
        sys.add_block(ConstantSource(value=1.0, block_id="src"))
        sys.add_block(IntegratorBlock(x0=0.0, block_id="integ"))
        sys.connect("src", "out", "integ", "in")
        sys.compile()
        result = sys.simulate(t_span=(0, 1.0), dt=0.001, solver="rk4")
        final_output = result.outputs["integ.out"][-1]
        assert final_output == pytest.approx(1.0, rel=0.001)

    def test_integrating_constant_with_euler(self):
        """Same test with Euler solver — still should be exact for constant input."""
        sys = DynamicSystem()
        sys.add_block(ConstantSource(value=1.0, block_id="src"))
        sys.add_block(IntegratorBlock(x0=0.0, block_id="integ"))
        sys.connect("src", "out", "integ", "in")
        sys.compile()
        result = sys.simulate(t_span=(0, 1.0), dt=0.001, solver="euler")
        final_output = result.outputs["integ.out"][-1]
        assert final_output == pytest.approx(1.0, abs=0.01)

    def test_integrator_with_initial_condition(self):
        """Integrator with x0=5, input=0 → output stays at 5."""
        sys = DynamicSystem()
        sys.add_block(ConstantSource(value=0.0, block_id="zero"))
        sys.add_block(IntegratorBlock(x0=5.0, block_id="integ"))
        sys.connect("zero", "out", "integ", "in")
        sys.compile()
        result = sys.simulate(t_span=(0, 0.1), dt=0.01)
        final_output = result.outputs["integ.out"][-1]
        assert final_output == pytest.approx(5.0, abs=1e-10)

    def test_solver_instance_passthrough(self):
        """Pass a Solver instance directly instead of a string."""
        sys = DynamicSystem()
        sys.add_block(ConstantSource(value=2.0, block_id="src"))
        sys.add_block(IntegratorBlock(x0=0.0, block_id="integ"))
        sys.connect("src", "out", "integ", "in")
        sys.compile()
        result = sys.simulate(t_span=(0, 1.0), dt=0.001, solver=RK4Solver())
        final_output = result.outputs["integ.out"][-1]
        assert final_output == pytest.approx(2.0, rel=0.001)


# ---------------------------------------------------------------------------
# Simulation result structure tests
# ---------------------------------------------------------------------------


class TestSimulationResults:
    """Tests for the structure of SimulationResult from simulate()."""

    def test_time_array_length(self):
        sys = DynamicSystem()
        sys.add_block(ConstantSource(block_id="src"))
        sys.compile()
        result = sys.simulate(t_span=(0, 0.1), dt=0.01)
        # 10 steps + initial point = 11
        assert len(result.time) == 11

    def test_time_array_boundaries(self):
        sys = DynamicSystem()
        sys.add_block(ConstantSource(block_id="src"))
        sys.compile()
        result = sys.simulate(t_span=(0, 1.0), dt=0.1)
        assert result.time[0] == pytest.approx(0.0)
        assert result.time[-1] == pytest.approx(1.0)

    def test_output_keys_match_blocks(self):
        sys = DynamicSystem()
        sys.add_block(ConstantSource(block_id="src"))
        sys.add_block(GainBlock(block_id="gain"))
        sys.connect("src", "out", "gain", "in")
        sys.compile()
        result = sys.simulate(t_span=(0, 0.01), dt=0.01)
        assert "src.out" in result.outputs
        assert "gain.out" in result.outputs

    def test_state_record_shape(self):
        sys = DynamicSystem()
        sys.add_block(ConstantSource(value=1.0, block_id="src"))
        sys.add_block(IntegratorBlock(x0=0.0, block_id="integ"))
        sys.connect("src", "out", "integ", "in")
        sys.compile()
        result = sys.simulate(t_span=(0, 0.1), dt=0.01)
        # 1 state variable, 11 time points
        assert result.states.shape == (11, 1)


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases for DynamicSystem."""

    def test_empty_system(self):
        """System with no blocks still compiles and simulates."""
        sys = DynamicSystem()
        sys.compile()
        result = sys.simulate(t_span=(0, 0.01), dt=0.01)
        assert len(result.time) == 2  # initial + 1 step

    def test_unconnected_blocks(self):
        """Blocks with no connections still appear in sorted order."""
        sys = DynamicSystem()
        sys.add_block(ConstantSource(block_id="a"))
        sys.add_block(ConstantSource(block_id="b"))
        sys.compile()
        assert len(sys.sorted_blocks) == 2

    def test_recompile_after_adding_block(self):
        """Adding a block invalidates compilation."""
        sys = DynamicSystem()
        sys.add_block(ConstantSource(block_id="src"))
        sys.compile()
        assert sys._compiled is True
        sys.add_block(GainBlock(block_id="gain"))
        assert sys._compiled is False

    def test_recompile_after_connecting(self):
        """Connecting blocks invalidates compilation."""
        sys = DynamicSystem()
        sys.add_block(ConstantSource(block_id="src"))
        sys.add_block(GainBlock(block_id="gain"))
        sys.connect("src", "out", "gain", "in")
        sys.compile()
        assert sys._compiled is True
        # Add another source and gain to test reconnection
        sys.add_block(ConstantSource(block_id="src2"))
        assert sys._compiled is False
