"""Tests for simulation divergence detection (T-2.2).

Covers:
- SimulationDivergenceError is raised when state contains NaN
- SimulationDivergenceError is raised when state contains Inf
- Error includes helpful diagnostics (time, step, block ID)
- Normal simulations are not affected
"""

from __future__ import annotations

import numpy as np
import pytest

from blocksim.blocks.math_ops import Gain, Integrator
from blocksim.blocks.sources import ConstantSource
from blocksim.core.block import Block, InputPort, OutputPort
from blocksim.core.system import DynamicSystem, SimulationDivergenceError


# ---------------------------------------------------------------------------
# Helper: a block that deliberately produces NaN/Inf derivatives
# ---------------------------------------------------------------------------


class DivergentBlock(Block):
    """A block that produces divergent (Inf) derivatives after a threshold time.

    This simulates a stiff or unstable system for testing purposes.
    """

    _input_port_defs = [InputPort("in")]
    _output_port_defs = [OutputPort("out")]

    def __init__(self, diverge_after: float = 0.01, **kwargs) -> None:
        super().__init__(params={"diverge_after": diverge_after}, **kwargs)

    @property
    def state_size(self) -> int:
        return 1

    def initialize(self, t0: float) -> np.ndarray:
        return np.array([1.0], dtype=np.float64)

    def compute(self, t: float) -> None:
        self.set_output("out", self._state[0])

    def derivatives(self, t: float, state: np.ndarray) -> np.ndarray:
        if t > self.params["diverge_after"]:
            return np.array([np.inf], dtype=np.float64)
        return np.array([1.0], dtype=np.float64)


class NaNBlock(Block):
    """A block that produces NaN derivatives after a threshold time."""

    _input_port_defs = [InputPort("in")]
    _output_port_defs = [OutputPort("out")]

    def __init__(self, diverge_after: float = 0.01, **kwargs) -> None:
        super().__init__(params={"diverge_after": diverge_after}, **kwargs)

    @property
    def state_size(self) -> int:
        return 1

    def initialize(self, t0: float) -> np.ndarray:
        return np.array([1.0], dtype=np.float64)

    def compute(self, t: float) -> None:
        self.set_output("out", self._state[0])

    def derivatives(self, t: float, state: np.ndarray) -> np.ndarray:
        if t > self.params["diverge_after"]:
            return np.array([np.nan], dtype=np.float64)
        return np.array([1.0], dtype=np.float64)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSimulationDivergenceError:

    def test_error_has_correct_attributes(self):
        err = SimulationDivergenceError(
            time=0.5,
            step=500,
            block_id="inductor_1",
            state_values=np.array([np.inf]),
        )
        assert err.time == 0.5
        assert err.step == 500
        assert err.block_id == "inductor_1"
        assert "0.5" in str(err)
        assert "inductor_1" in str(err)

    def test_error_without_block_id(self):
        err = SimulationDivergenceError(time=0.1, step=10)
        assert err.block_id is None
        assert "0.1" in str(err)

    def test_error_message_suggests_fix(self):
        err = SimulationDivergenceError(time=0.1, step=10)
        assert "reducing dt" in str(err) or "dt" in str(err)


class TestDivergenceGuardInf:

    def test_inf_raises_divergence_error(self):
        """Simulation with Inf derivatives should raise SimulationDivergenceError."""
        sys = DynamicSystem()

        src = ConstantSource(value=1.0, block_id="src")
        div = DivergentBlock(diverge_after=0.005, block_id="div_block")

        sys.add_block(src)
        sys.add_block(div)
        sys.connect("src", "out", "div_block", "in")
        sys.compile()

        with pytest.raises(SimulationDivergenceError) as exc_info:
            sys.simulate(t_span=(0.0, 0.1), dt=0.001)

        err = exc_info.value
        assert err.block_id == "div_block"
        assert err.step > 0
        assert err.time > 0

    def test_inf_error_contains_state_values(self):
        sys = DynamicSystem()

        src = ConstantSource(value=1.0, block_id="src")
        div = DivergentBlock(diverge_after=0.005, block_id="div_block")

        sys.add_block(src)
        sys.add_block(div)
        sys.connect("src", "out", "div_block", "in")
        sys.compile()

        with pytest.raises(SimulationDivergenceError) as exc_info:
            sys.simulate(t_span=(0.0, 0.1), dt=0.001)

        assert exc_info.value.state_values is not None


class TestDivergenceGuardNaN:

    def test_nan_raises_divergence_error(self):
        """Simulation with NaN derivatives should raise SimulationDivergenceError."""
        sys = DynamicSystem()

        src = ConstantSource(value=1.0, block_id="src")
        nan_block = NaNBlock(diverge_after=0.005, block_id="nan_block")

        sys.add_block(src)
        sys.add_block(nan_block)
        sys.connect("src", "out", "nan_block", "in")
        sys.compile()

        with pytest.raises(SimulationDivergenceError) as exc_info:
            sys.simulate(t_span=(0.0, 0.1), dt=0.001)

        err = exc_info.value
        assert err.block_id == "nan_block"


class TestDivergenceGuardNormalOperation:

    def test_normal_simulation_not_affected(self):
        """A normal stable simulation should complete without errors."""
        sys = DynamicSystem()

        src = ConstantSource(value=1.0, block_id="src")
        integ = Integrator(x0=0.0, block_id="integ")

        sys.add_block(src)
        sys.add_block(integ)
        sys.connect("src", "out", "integ", "in")
        sys.compile()

        result = sys.simulate(t_span=(0.0, 1.0), dt=0.001)
        # Integrator should produce y=t at t=1.0 → y ≈ 1.0
        assert np.all(np.isfinite(result.states))

    def test_stateless_simulation_not_affected(self):
        """A pure stateless simulation (no ODE) should not trigger divergence."""
        sys = DynamicSystem()

        src = ConstantSource(value=5.0, block_id="src")
        gain = Gain(k=2.0, block_id="gain")

        sys.add_block(src)
        sys.add_block(gain)
        sys.connect("src", "out", "gain", "in")
        sys.compile()

        result = sys.simulate(t_span=(0.0, 0.1), dt=0.01)
        final_output = result.outputs["gain.out"][-1]
        assert final_output == pytest.approx(10.0)
