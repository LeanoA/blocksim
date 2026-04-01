"""Tests for source blocks (blocks/sources.py).

Covers:
- ConstantSource: fixed output value
- StepSource: step transition at step_time
- SineSource: sinusoidal output with amplitude, frequency, phase
- RampSource: linear ramp from start_time
- All blocks have correct ports (no inputs, one output)
"""

from __future__ import annotations

import math

import pytest

from blocksim.blocks.sources import ConstantSource, RampSource, SineSource, StepSource


# ---------------------------------------------------------------------------
# ConstantSource
# ---------------------------------------------------------------------------


class TestConstantSource:

    def test_default_value(self):
        src = ConstantSource()
        src.compute(t=0.0)
        assert src.get_output("out") == pytest.approx(1.0)

    def test_custom_value(self):
        src = ConstantSource(value=42.0)
        src.compute(t=0.0)
        assert src.get_output("out") == pytest.approx(42.0)

    def test_value_independent_of_time(self):
        src = ConstantSource(value=3.14)
        for t in [0.0, 0.5, 1.0, 100.0]:
            src.compute(t=t)
            assert src.get_output("out") == pytest.approx(3.14)

    def test_no_input_ports(self):
        src = ConstantSource()
        assert len(src.input_ports) == 0

    def test_has_output_port(self):
        src = ConstantSource()
        assert "out" in src.output_ports

    def test_state_size_zero(self):
        src = ConstantSource()
        assert src.state_size == 0

    def test_params_stored(self):
        src = ConstantSource(value=7.0)
        assert src.params["value"] == 7.0

    def test_block_type(self):
        src = ConstantSource()
        assert src.block_type == "ConstantSource"


# ---------------------------------------------------------------------------
# StepSource
# ---------------------------------------------------------------------------


class TestStepSource:

    def test_before_step_time(self):
        src = StepSource(step_time=1.0, initial=0.0, final=5.0)
        src.compute(t=0.0)
        assert src.get_output("out") == pytest.approx(0.0)
        src.compute(t=0.99)
        assert src.get_output("out") == pytest.approx(0.0)

    def test_at_step_time(self):
        src = StepSource(step_time=1.0, initial=0.0, final=5.0)
        src.compute(t=1.0)
        assert src.get_output("out") == pytest.approx(5.0)

    def test_after_step_time(self):
        src = StepSource(step_time=1.0, initial=0.0, final=5.0)
        src.compute(t=2.0)
        assert src.get_output("out") == pytest.approx(5.0)

    def test_default_parameters(self):
        src = StepSource()
        # Default: step_time=0.0, initial=0.0, final=1.0
        src.compute(t=0.0)
        assert src.get_output("out") == pytest.approx(1.0)

    def test_negative_step(self):
        src = StepSource(step_time=0.5, initial=10.0, final=0.0)
        src.compute(t=0.0)
        assert src.get_output("out") == pytest.approx(10.0)
        src.compute(t=0.5)
        assert src.get_output("out") == pytest.approx(0.0)

    def test_params_stored(self):
        src = StepSource(step_time=2.0, initial=1.0, final=3.0)
        assert src.params["step_time"] == 2.0
        assert src.params["initial"] == 1.0
        assert src.params["final"] == 3.0


# ---------------------------------------------------------------------------
# SineSource
# ---------------------------------------------------------------------------


class TestSineSource:

    def test_sine_at_t_zero(self):
        src = SineSource(amplitude=1.0, frequency=1.0, phase=0.0)
        src.compute(t=0.0)
        assert src.get_output("out") == pytest.approx(0.0)

    def test_sine_at_quarter_period(self):
        src = SineSource(amplitude=1.0, frequency=1.0, phase=0.0)
        src.compute(t=0.25)  # quarter period of 1 Hz
        assert src.get_output("out") == pytest.approx(1.0)

    def test_sine_amplitude(self):
        src = SineSource(amplitude=5.0, frequency=1.0, phase=0.0)
        src.compute(t=0.25)
        assert src.get_output("out") == pytest.approx(5.0)

    def test_sine_with_phase(self):
        src = SineSource(amplitude=1.0, frequency=1.0, phase=math.pi / 2)
        src.compute(t=0.0)
        # sin(pi/2) = 1.0
        assert src.get_output("out") == pytest.approx(1.0)

    def test_sine_frequency(self):
        src = SineSource(amplitude=1.0, frequency=2.0, phase=0.0)
        src.compute(t=0.125)  # quarter period of 2 Hz
        assert src.get_output("out") == pytest.approx(1.0)

    def test_default_parameters(self):
        src = SineSource()
        assert src.params["amplitude"] == 1.0
        assert src.params["frequency"] == 1.0
        assert src.params["phase"] == 0.0

    def test_sine_multiple_points(self):
        src = SineSource(amplitude=2.0, frequency=1.0)
        expected_values = [
            (0.0, 0.0),
            (0.25, 2.0),
            (0.5, 0.0),
            (0.75, -2.0),
            (1.0, 0.0),
        ]
        for t, expected in expected_values:
            src.compute(t=t)
            assert src.get_output("out") == pytest.approx(expected, abs=1e-10)


# ---------------------------------------------------------------------------
# RampSource
# ---------------------------------------------------------------------------


class TestRampSource:

    def test_before_start_time(self):
        src = RampSource(slope=2.0, start_time=1.0, initial=0.0)
        src.compute(t=0.0)
        assert src.get_output("out") == pytest.approx(0.0)
        src.compute(t=0.99)
        assert src.get_output("out") == pytest.approx(0.0)

    def test_at_start_time(self):
        src = RampSource(slope=2.0, start_time=1.0, initial=0.0)
        src.compute(t=1.0)
        assert src.get_output("out") == pytest.approx(0.0)

    def test_after_start_time(self):
        src = RampSource(slope=2.0, start_time=1.0, initial=0.0)
        src.compute(t=2.0)
        assert src.get_output("out") == pytest.approx(2.0)  # 2.0 * (2.0 - 1.0)

    def test_ramp_with_initial(self):
        src = RampSource(slope=1.0, start_time=0.0, initial=5.0)
        src.compute(t=3.0)
        assert src.get_output("out") == pytest.approx(8.0)  # 5.0 + 1.0 * 3.0

    def test_default_parameters(self):
        src = RampSource()
        assert src.params["slope"] == 1.0
        assert src.params["start_time"] == 0.0
        assert src.params["initial"] == 0.0

    def test_negative_slope(self):
        src = RampSource(slope=-3.0, start_time=0.0, initial=10.0)
        src.compute(t=2.0)
        assert src.get_output("out") == pytest.approx(4.0)  # 10.0 + (-3.0) * 2.0

    def test_ramp_linearity(self):
        src = RampSource(slope=1.0, start_time=0.0)
        for t in [0.0, 0.5, 1.0, 2.0, 5.0]:
            src.compute(t=t)
            assert src.get_output("out") == pytest.approx(t)
