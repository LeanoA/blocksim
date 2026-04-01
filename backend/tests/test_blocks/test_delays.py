"""Tests for Delay block (blocks/delays.py).

Covers:
- Initial value output on first step
- One-step delay behavior
- Loop-breaking (class name contains 'Delay')
"""

from __future__ import annotations

import pytest

from blocksim.blocks.delays import Delay


# ---------------------------------------------------------------------------
# Delay
# ---------------------------------------------------------------------------


class TestDelay:

    def test_initial_output(self):
        d = Delay(initial=0.0)
        d.set_input("in", 5.0)
        d.compute(t=0.0)
        # First compute: should output the initial value (0.0),
        # then latch the input (5.0) for next step.
        assert d.get_output("out") == pytest.approx(0.0)

    def test_one_step_delay(self):
        d = Delay(initial=0.0)
        # Step 1: input=10, output should be initial=0
        d.set_input("in", 10.0)
        d.compute(t=0.0)
        assert d.get_output("out") == pytest.approx(0.0)

        # Step 2: input=20, output should be previous input=10
        d.set_input("in", 20.0)
        d.compute(t=0.1)
        assert d.get_output("out") == pytest.approx(10.0)

        # Step 3: input=30, output should be previous input=20
        d.set_input("in", 30.0)
        d.compute(t=0.2)
        assert d.get_output("out") == pytest.approx(20.0)

    def test_custom_initial(self):
        d = Delay(initial=42.0)
        d.set_input("in", 1.0)
        d.compute(t=0.0)
        assert d.get_output("out") == pytest.approx(42.0)

    def test_delay_ports(self):
        d = Delay()
        assert "in" in d.input_ports
        assert "out" in d.output_ports

    def test_delay_stateless(self):
        # Delay uses internal state but not ODE state.
        d = Delay()
        assert d.state_size == 0

    def test_delay_is_recognized_as_delay(self):
        """Graph module identifies delay blocks by class name."""
        d = Delay()
        assert "Delay" in type(d).__name__

    def test_delay_params(self):
        d = Delay(initial=7.0)
        assert d.params["initial"] == 7.0

    def test_delay_constant_input(self):
        d = Delay(initial=0.0)
        # Send same value multiple times.
        d.set_input("in", 5.0)
        d.compute(t=0.0)
        assert d.get_output("out") == pytest.approx(0.0)

        d.set_input("in", 5.0)
        d.compute(t=0.1)
        assert d.get_output("out") == pytest.approx(5.0)

        d.set_input("in", 5.0)
        d.compute(t=0.2)
        assert d.get_output("out") == pytest.approx(5.0)
