"""Tests for per-block error isolation in simulation (Task 6.3).

Covers:
- A block that raises during compute() doesn't crash the simulation
- NaN outputs are produced for the failed block
- block_errors are collected in SimulationResult
- Downstream blocks receive NaN and continue
- Multiple failing blocks
- Non-failing simulation is identical to before (no error overhead)
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from blocksim.core.block import Block, InputPort, OutputPort
from blocksim.core.system import DynamicSystem


# ---------------------------------------------------------------------------
# Custom blocks for testing
# ---------------------------------------------------------------------------


class AlwaysFailBlock(Block):
    """A block that always raises ValueError during compute()."""

    _input_port_defs = [InputPort("in")]
    _output_port_defs = [OutputPort("out")]

    def compute(self, t: float) -> None:
        raise ValueError("Intentional failure in AlwaysFailBlock")


class FailAfterStepBlock(Block):
    """A block that fails after a specified number of successful compute() calls.

    Params: fail_after (int) — number of times compute succeeds before failing.
    """

    _input_port_defs = [InputPort("in")]
    _output_port_defs = [OutputPort("out")]

    def __init__(self, fail_after: int = 3, **kwargs):
        super().__init__(params={"fail_after": fail_after}, **kwargs)
        self._call_count = 0

    def compute(self, t: float) -> None:
        self._call_count += 1
        if self._call_count > self.params["fail_after"]:
            raise RuntimeError(f"FailAfterStepBlock failed at call {self._call_count}")
        self.set_output("out", self.get_input("in") * 2.0)


class ConstSource(Block):
    """Simple constant source for testing."""

    _output_port_defs = [OutputPort("out")]

    def __init__(self, value: float = 1.0, **kwargs):
        super().__init__(params={"value": value}, **kwargs)

    def compute(self, t: float) -> None:
        self.set_output("out", self.params["value"])


class PassthroughBlock(Block):
    """Passes input to output unchanged."""

    _input_port_defs = [InputPort("in")]
    _output_port_defs = [OutputPort("out")]

    def compute(self, t: float) -> None:
        self.set_output("out", self.get_input("in"))


class ScopeBlock(Block):
    """Sink block — records input (no output ports)."""

    _input_port_defs = [InputPort("in")]

    def compute(self, t: float) -> None:
        pass


# ===========================================================================
# Single block failure
# ===========================================================================


class TestSingleBlockFailure:
    """A single failing block should not crash the simulation."""

    def test_simulation_completes(self) -> None:
        """Simulation should run to completion even with a failing block."""
        sys = DynamicSystem()
        sys.add_block(ConstSource(value=5.0, block_id="src"))
        sys.add_block(AlwaysFailBlock(block_id="fail"))
        sys.connect("src", "out", "fail", "in")
        sys.compile()

        result = sys.simulate(t_span=(0, 0.01), dt=0.01)
        assert result is not None
        assert len(result.time) > 0

    def test_failed_block_outputs_nan(self) -> None:
        """The failing block's outputs should be NaN."""
        sys = DynamicSystem()
        sys.add_block(ConstSource(value=5.0, block_id="src"))
        sys.add_block(AlwaysFailBlock(block_id="fail"))
        sys.connect("src", "out", "fail", "in")
        sys.compile()

        result = sys.simulate(t_span=(0, 0.05), dt=0.01)
        fail_output = result.outputs["fail.out"]
        # All values after t=0 should be NaN (the block always fails).
        for val in fail_output[1:]:  # skip t=0 initial
            assert math.isnan(val), f"Expected NaN but got {val}"

    def test_block_errors_collected(self) -> None:
        """block_errors should contain entries for the failing block."""
        sys = DynamicSystem()
        sys.add_block(ConstSource(value=5.0, block_id="src"))
        sys.add_block(AlwaysFailBlock(block_id="fail"))
        sys.connect("src", "out", "fail", "in")
        sys.compile()

        result = sys.simulate(t_span=(0, 0.05), dt=0.01)
        assert "fail" in result.block_errors
        errors = result.block_errors["fail"]
        assert len(errors) > 0

        # Each error entry should have the expected keys.
        for err in errors:
            assert err["block_id"] == "fail"
            assert "step" in err
            assert "time" in err
            assert "error" in err
            assert "Intentional failure" in err["error"]

    def test_non_failing_block_produces_normal_output(self) -> None:
        """A non-failing source block should produce normal output."""
        sys = DynamicSystem()
        sys.add_block(ConstSource(value=5.0, block_id="src"))
        sys.add_block(AlwaysFailBlock(block_id="fail"))
        sys.connect("src", "out", "fail", "in")
        sys.compile()

        result = sys.simulate(t_span=(0, 0.05), dt=0.01)
        src_output = result.outputs["src.out"]
        for val in src_output:
            assert val == pytest.approx(5.0)


# ===========================================================================
# Downstream NaN propagation
# ===========================================================================


class TestNanPropagation:
    """NaN from a failed block should propagate to downstream blocks."""

    def test_downstream_receives_nan_input(self) -> None:
        """A block downstream of a failing block should receive NaN."""
        sys = DynamicSystem()
        sys.add_block(ConstSource(value=3.0, block_id="src"))
        sys.add_block(AlwaysFailBlock(block_id="fail"))
        sys.add_block(PassthroughBlock(block_id="downstream"))
        sys.connect("src", "out", "fail", "in")
        sys.connect("fail", "out", "downstream", "in")
        sys.compile()

        result = sys.simulate(t_span=(0, 0.05), dt=0.01)
        downstream_output = result.outputs["downstream.out"]
        # Downstream should also be NaN since its input is NaN.
        for val in downstream_output[1:]:
            assert math.isnan(val), f"Expected NaN but got {val}"


# ===========================================================================
# Delayed failure (block fails at a specific step)
# ===========================================================================


class TestDelayedFailure:
    """A block that fails after N steps should produce normal output before failure."""

    def test_normal_output_before_failure(self) -> None:
        """Output should be normal before the block fails."""
        sys = DynamicSystem()
        sys.add_block(ConstSource(value=4.0, block_id="src"))
        # fail_after=3: succeeds for calls 1-3, fails from call 4 onwards.
        # Note: compute is called at t=0 (initial) + each step.
        sys.add_block(FailAfterStepBlock(fail_after=3, block_id="delayed"))
        sys.connect("src", "out", "delayed", "in")
        sys.compile()

        result = sys.simulate(t_span=(0, 0.1), dt=0.01)
        delayed_output = result.outputs["delayed.out"]

        # First few should be normal (4.0 * 2.0 = 8.0).
        assert delayed_output[0] == pytest.approx(8.0)
        assert delayed_output[1] == pytest.approx(8.0)
        assert delayed_output[2] == pytest.approx(8.0)

        # After failure, should be NaN.
        # The exact transition point depends on the call counting in the block.
        nan_found = False
        for val in delayed_output[3:]:
            if math.isnan(val):
                nan_found = True
                break
        assert nan_found, "Expected NaN values after failure step"

    def test_errors_contain_failure_step(self) -> None:
        """The recorded errors should reflect the correct step."""
        sys = DynamicSystem()
        sys.add_block(ConstSource(value=4.0, block_id="src"))
        sys.add_block(FailAfterStepBlock(fail_after=3, block_id="delayed"))
        sys.connect("src", "out", "delayed", "in")
        sys.compile()

        result = sys.simulate(t_span=(0, 0.1), dt=0.01)
        assert "delayed" in result.block_errors
        errors = result.block_errors["delayed"]
        assert len(errors) > 0
        # First error should occur at a step > 0.
        assert errors[0]["step"] > 0


# ===========================================================================
# Multiple failing blocks
# ===========================================================================


class TestMultipleFailingBlocks:
    """Multiple blocks can fail independently."""

    def test_multiple_failures_both_recorded(self) -> None:
        """Both failing blocks should have entries in block_errors."""
        sys = DynamicSystem()
        sys.add_block(ConstSource(value=1.0, block_id="src"))
        sys.add_block(AlwaysFailBlock(block_id="fail1"))
        sys.add_block(AlwaysFailBlock(block_id="fail2"))
        sys.connect("src", "out", "fail1", "in")
        sys.connect("src", "out", "fail2", "in")
        sys.compile()

        result = sys.simulate(t_span=(0, 0.05), dt=0.01)
        assert "fail1" in result.block_errors
        assert "fail2" in result.block_errors

    def test_simulation_completes_with_multiple_failures(self) -> None:
        """Simulation completes even with multiple failing blocks."""
        sys = DynamicSystem()
        sys.add_block(ConstSource(value=1.0, block_id="src"))
        sys.add_block(AlwaysFailBlock(block_id="fail1"))
        sys.add_block(AlwaysFailBlock(block_id="fail2"))
        sys.connect("src", "out", "fail1", "in")
        sys.connect("src", "out", "fail2", "in")
        sys.compile()

        result = sys.simulate(t_span=(0, 0.05), dt=0.01)
        assert len(result.time) > 0
        # Source should still be fine.
        for val in result.outputs["src.out"]:
            assert val == pytest.approx(1.0)


# ===========================================================================
# No-failure baseline (no performance regression)
# ===========================================================================


class TestNoFailureBaseline:
    """When no blocks fail, behavior should be identical to the old system."""

    def test_no_block_errors_when_all_succeed(self) -> None:
        """block_errors should be empty when no blocks fail."""
        sys = DynamicSystem()
        sys.add_block(ConstSource(value=5.0, block_id="src"))
        sys.add_block(PassthroughBlock(block_id="pass"))
        sys.connect("src", "out", "pass", "in")
        sys.compile()

        result = sys.simulate(t_span=(0, 0.1), dt=0.01)
        assert result.block_errors == {}

    def test_outputs_correct_when_no_failure(self) -> None:
        """Outputs should be numerically correct in the no-failure case."""
        sys = DynamicSystem()
        sys.add_block(ConstSource(value=7.0, block_id="src"))
        sys.add_block(PassthroughBlock(block_id="pass"))
        sys.connect("src", "out", "pass", "in")
        sys.compile()

        result = sys.simulate(t_span=(0, 0.1), dt=0.01)
        for val in result.outputs["pass.out"]:
            assert val == pytest.approx(7.0)
