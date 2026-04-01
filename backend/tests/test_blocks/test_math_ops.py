"""Tests for math and continuous blocks (blocks/math_ops.py).

Covers:
- Gain: multiplication by constant
- Sum: configurable sign addition/subtraction
- Multiply: element-wise product
- Integrator: stateful, state_size=1, derivatives
- Derivative: finite-difference approximation
"""

from __future__ import annotations

import numpy as np
import pytest

from blocksim.blocks.math_ops import Derivative, Gain, Integrator, Multiply, Sum


# ---------------------------------------------------------------------------
# Gain
# ---------------------------------------------------------------------------


class TestGain:

    def test_gain_default(self):
        g = Gain()
        g.set_input("in", 5.0)
        g.compute(t=0.0)
        assert g.get_output("out") == pytest.approx(5.0)

    def test_gain_positive(self):
        g = Gain(k=3.0)
        g.set_input("in", 4.0)
        g.compute(t=0.0)
        assert g.get_output("out") == pytest.approx(12.0)

    def test_gain_negative(self):
        g = Gain(k=-2.0)
        g.set_input("in", 5.0)
        g.compute(t=0.0)
        assert g.get_output("out") == pytest.approx(-10.0)

    def test_gain_zero(self):
        g = Gain(k=0.0)
        g.set_input("in", 100.0)
        g.compute(t=0.0)
        assert g.get_output("out") == pytest.approx(0.0)

    def test_gain_ports(self):
        g = Gain()
        assert "in" in g.input_ports
        assert "out" in g.output_ports

    def test_gain_stateless(self):
        g = Gain()
        assert g.state_size == 0

    def test_gain_params(self):
        g = Gain(k=7.0)
        assert g.params["k"] == 7.0

    def test_gain_block_type(self):
        g = Gain()
        assert g.block_type == "Gain"


# ---------------------------------------------------------------------------
# Sum
# ---------------------------------------------------------------------------


class TestSum:

    def test_sum_plus_plus(self):
        s = Sum(signs="++")
        s.set_input("in1", 3.0)
        s.set_input("in2", 4.0)
        s.compute(t=0.0)
        assert s.get_output("out") == pytest.approx(7.0)

    def test_sum_plus_minus(self):
        s = Sum(signs="+-")
        s.set_input("in1", 10.0)
        s.set_input("in2", 3.0)
        s.compute(t=0.0)
        assert s.get_output("out") == pytest.approx(7.0)

    def test_sum_minus_plus(self):
        s = Sum(signs="-+")
        s.set_input("in1", 3.0)
        s.set_input("in2", 10.0)
        s.compute(t=0.0)
        assert s.get_output("out") == pytest.approx(7.0)

    def test_sum_minus_minus(self):
        s = Sum(signs="--")
        s.set_input("in1", 3.0)
        s.set_input("in2", 4.0)
        s.compute(t=0.0)
        assert s.get_output("out") == pytest.approx(-7.0)

    def test_sum_default_is_plus_plus(self):
        s = Sum()
        s.set_input("in1", 1.0)
        s.set_input("in2", 2.0)
        s.compute(t=0.0)
        assert s.get_output("out") == pytest.approx(3.0)

    def test_sum_invalid_signs_raises(self):
        with pytest.raises(ValueError, match="signs must be"):
            Sum(signs="abc")

    def test_sum_too_short_raises(self):
        with pytest.raises(ValueError):
            Sum(signs="+")

    def test_sum_ports(self):
        s = Sum()
        assert "in1" in s.input_ports
        assert "in2" in s.input_ports
        assert "out" in s.output_ports

    def test_sum_stateless(self):
        s = Sum()
        assert s.state_size == 0


# ---------------------------------------------------------------------------
# Multiply
# ---------------------------------------------------------------------------


class TestMultiply:

    def test_multiply_basic(self):
        m = Multiply()
        m.set_input("in1", 3.0)
        m.set_input("in2", 4.0)
        m.compute(t=0.0)
        assert m.get_output("out") == pytest.approx(12.0)

    def test_multiply_by_zero(self):
        m = Multiply()
        m.set_input("in1", 100.0)
        m.set_input("in2", 0.0)
        m.compute(t=0.0)
        assert m.get_output("out") == pytest.approx(0.0)

    def test_multiply_negative(self):
        m = Multiply()
        m.set_input("in1", -3.0)
        m.set_input("in2", 4.0)
        m.compute(t=0.0)
        assert m.get_output("out") == pytest.approx(-12.0)

    def test_multiply_ports(self):
        m = Multiply()
        assert "in1" in m.input_ports
        assert "in2" in m.input_ports
        assert "out" in m.output_ports

    def test_multiply_stateless(self):
        m = Multiply()
        assert m.state_size == 0


# ---------------------------------------------------------------------------
# Integrator
# ---------------------------------------------------------------------------


class TestIntegrator:

    def test_integrator_state_size(self):
        integ = Integrator()
        assert integ.state_size == 1

    def test_integrator_initialize(self):
        integ = Integrator(x0=5.0)
        state = integ.initialize(t0=0.0)
        np.testing.assert_array_equal(state, [5.0])

    def test_integrator_default_x0(self):
        integ = Integrator()
        state = integ.initialize(t0=0.0)
        np.testing.assert_array_equal(state, [0.0])

    def test_integrator_derivatives(self):
        integ = Integrator()
        integ.set_input("in", 7.0)
        dy = integ.derivatives(t=0.0, state=np.array([0.0]))
        np.testing.assert_array_equal(dy, [7.0])

    def test_integrator_compute_outputs_state(self):
        integ = Integrator()
        integ.set_state(np.array([3.14]))
        integ.compute(t=0.0)
        assert integ.get_output("out") == pytest.approx(3.14)

    def test_integrator_ports(self):
        integ = Integrator()
        assert "in" in integ.input_ports
        assert "out" in integ.output_ports

    def test_integrator_params(self):
        integ = Integrator(x0=2.0)
        assert integ.params["x0"] == 2.0


# ---------------------------------------------------------------------------
# Derivative
# ---------------------------------------------------------------------------


class TestDerivative:

    def test_derivative_first_step_is_zero(self):
        d = Derivative()
        d.set_input("in", 5.0)
        d.compute(t=0.0)
        assert d.get_output("out") == pytest.approx(0.0)

    def test_derivative_constant_input_is_zero(self):
        d = Derivative()
        d.set_input("in", 5.0)
        d.compute(t=0.0)
        d.set_input("in", 5.0)
        d.compute(t=1.0)
        assert d.get_output("out") == pytest.approx(0.0)

    def test_derivative_linear_input(self):
        d = Derivative(initial=0.0)
        # First step: output is 0
        d.set_input("in", 0.0)
        d.compute(t=0.0)
        # Second step: input=2.0 at t=1.0 → derivative = (2.0-0.0)/1.0 = 2.0
        d.set_input("in", 2.0)
        d.compute(t=1.0)
        assert d.get_output("out") == pytest.approx(2.0)

    def test_derivative_small_dt(self):
        d = Derivative()
        d.set_input("in", 0.0)
        d.compute(t=0.0)
        d.set_input("in", 0.01)
        d.compute(t=0.01)
        assert d.get_output("out") == pytest.approx(1.0)

    def test_derivative_ports(self):
        d = Derivative()
        assert "in" in d.input_ports
        assert "out" in d.output_ports

    def test_derivative_stateless(self):
        d = Derivative()
        assert d.state_size == 0

    def test_derivative_same_time_returns_zero(self):
        d = Derivative()
        d.set_input("in", 1.0)
        d.compute(t=0.0)
        d.set_input("in", 2.0)
        d.compute(t=0.0)  # same time — dt=0
        assert d.get_output("out") == pytest.approx(0.0)
