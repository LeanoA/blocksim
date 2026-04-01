"""Tests for electrical blocks (blocks/electrical.py).

Covers:
- VoltageSource: DC and step output modes
- Resistor: Ohm's law V = I * R
- Inductor: stateful dI/dt = V/L
- Capacitor: stateful dV/dt = I/C
- All blocks have correct ports and registration
"""

from __future__ import annotations

import numpy as np
import pytest

from blocksim.blocks.electrical import Capacitor, Inductor, Resistor, VoltageSource
from blocksim.blocks.registry import registry


# ---------------------------------------------------------------------------
# VoltageSource
# ---------------------------------------------------------------------------


class TestVoltageSource:

    def test_dc_output(self):
        vs = VoltageSource(voltage=10.0)
        vs.compute(t=0.0)
        assert vs.get_output("out") == pytest.approx(10.0)

    def test_dc_output_various_times(self):
        vs = VoltageSource(voltage=5.0)
        for t in [0.0, 0.5, 1.0, 100.0]:
            vs.compute(t=t)
            assert vs.get_output("out") == pytest.approx(5.0)

    def test_step_before_step_time(self):
        vs = VoltageSource(voltage=10.0, step_time=1.0, initial=0.0)
        vs.compute(t=0.5)
        assert vs.get_output("out") == pytest.approx(0.0)

    def test_step_at_step_time(self):
        vs = VoltageSource(voltage=10.0, step_time=1.0, initial=0.0)
        vs.compute(t=1.0)
        assert vs.get_output("out") == pytest.approx(10.0)

    def test_step_after_step_time(self):
        vs = VoltageSource(voltage=10.0, step_time=1.0, initial=0.0)
        vs.compute(t=2.0)
        assert vs.get_output("out") == pytest.approx(10.0)

    def test_no_input_ports(self):
        vs = VoltageSource()
        assert len(vs.input_ports) == 0

    def test_has_output_port(self):
        vs = VoltageSource()
        assert "out" in vs.output_ports

    def test_is_stateless(self):
        vs = VoltageSource()
        assert vs.state_size == 0

    def test_default_voltage(self):
        vs = VoltageSource()
        vs.compute(t=0.0)
        assert vs.get_output("out") == pytest.approx(1.0)

    def test_custom_block_id(self):
        vs = VoltageSource(voltage=5.0, block_id="vs1")
        assert vs.id == "vs1"

    def test_params_stored(self):
        vs = VoltageSource(voltage=12.0, step_time=0.5, initial=3.0)
        assert vs.params["voltage"] == 12.0
        assert vs.params["step_time"] == 0.5
        assert vs.params["initial"] == 3.0


# ---------------------------------------------------------------------------
# Resistor
# ---------------------------------------------------------------------------


class TestResistor:

    def test_ohms_law(self):
        r = Resistor(resistance=100.0)
        r.set_input("in", 0.5)  # 0.5 A
        r.compute(t=0.0)
        assert r.get_output("out") == pytest.approx(50.0)  # V = I * R

    def test_zero_current(self):
        r = Resistor(resistance=100.0)
        r.set_input("in", 0.0)
        r.compute(t=0.0)
        assert r.get_output("out") == pytest.approx(0.0)

    def test_negative_current(self):
        r = Resistor(resistance=10.0)
        r.set_input("in", -2.0)
        r.compute(t=0.0)
        assert r.get_output("out") == pytest.approx(-20.0)

    def test_default_resistance(self):
        r = Resistor()
        r.set_input("in", 5.0)
        r.compute(t=0.0)
        assert r.get_output("out") == pytest.approx(5.0)

    def test_invalid_resistance_zero(self):
        with pytest.raises(ValueError, match="positive"):
            Resistor(resistance=0.0)

    def test_invalid_resistance_negative(self):
        with pytest.raises(ValueError, match="positive"):
            Resistor(resistance=-10.0)

    def test_has_correct_ports(self):
        r = Resistor()
        assert "in" in r.input_ports
        assert "out" in r.output_ports

    def test_is_stateless(self):
        r = Resistor()
        assert r.state_size == 0


# ---------------------------------------------------------------------------
# Inductor
# ---------------------------------------------------------------------------


class TestInductor:

    def test_state_size(self):
        ind = Inductor(inductance=1.0)
        assert ind.state_size == 1

    def test_initial_state(self):
        ind = Inductor(inductance=1.0, i0=2.5)
        state = ind.initialize(t0=0.0)
        assert state == pytest.approx(np.array([2.5]))

    def test_default_initial_current(self):
        ind = Inductor(inductance=1.0)
        state = ind.initialize(t0=0.0)
        assert state == pytest.approx(np.array([0.0]))

    def test_derivatives(self):
        """dI/dt = V_L / L. With V=10V, L=2H → dI/dt = 5 A/s."""
        ind = Inductor(inductance=2.0)
        ind.set_state(np.array([0.0]))
        ind.set_input("in", 10.0)
        dy = ind.derivatives(t=0.0, state=np.array([0.0]))
        assert dy == pytest.approx(np.array([5.0]))

    def test_compute_outputs_current(self):
        ind = Inductor(inductance=1.0)
        ind.set_state(np.array([3.0]))
        ind.compute(t=0.0)
        assert ind.get_output("out") == pytest.approx(3.0)

    def test_invalid_inductance_zero(self):
        with pytest.raises(ValueError, match="positive"):
            Inductor(inductance=0.0)

    def test_invalid_inductance_negative(self):
        with pytest.raises(ValueError, match="positive"):
            Inductor(inductance=-1.0)

    def test_has_correct_ports(self):
        ind = Inductor()
        assert "in" in ind.input_ports
        assert "out" in ind.output_ports


# ---------------------------------------------------------------------------
# Capacitor
# ---------------------------------------------------------------------------


class TestCapacitor:

    def test_state_size(self):
        cap = Capacitor(capacitance=100e-6)
        assert cap.state_size == 1

    def test_initial_state(self):
        cap = Capacitor(capacitance=100e-6, v0=5.0)
        state = cap.initialize(t0=0.0)
        assert state == pytest.approx(np.array([5.0]))

    def test_default_initial_voltage(self):
        cap = Capacitor(capacitance=100e-6)
        state = cap.initialize(t0=0.0)
        assert state == pytest.approx(np.array([0.0]))

    def test_derivatives(self):
        """dV/dt = I / C. With I=0.001A, C=100µF → dV/dt = 10 V/s."""
        cap = Capacitor(capacitance=100e-6)
        cap.set_state(np.array([0.0]))
        cap.set_input("in", 0.001)
        dy = cap.derivatives(t=0.0, state=np.array([0.0]))
        assert dy == pytest.approx(np.array([10.0]))

    def test_compute_outputs_voltage(self):
        cap = Capacitor(capacitance=100e-6)
        cap.set_state(np.array([7.5]))
        cap.compute(t=0.0)
        assert cap.get_output("out") == pytest.approx(7.5)

    def test_invalid_capacitance_zero(self):
        with pytest.raises(ValueError, match="positive"):
            Capacitor(capacitance=0.0)

    def test_invalid_capacitance_negative(self):
        with pytest.raises(ValueError, match="positive"):
            Capacitor(capacitance=-1e-6)

    def test_has_correct_ports(self):
        cap = Capacitor()
        assert "in" in cap.input_ports
        assert "out" in cap.output_ports


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestElectricalRegistry:

    def test_voltage_source_registered(self):
        assert "VoltageSource" in registry

    def test_resistor_registered(self):
        assert "Resistor" in registry

    def test_inductor_registered(self):
        assert "Inductor" in registry

    def test_capacitor_registered(self):
        assert "Capacitor" in registry

    def test_create_voltage_source(self):
        block = registry.create("VoltageSource", voltage=12.0)
        assert isinstance(block, VoltageSource)

    def test_create_resistor(self):
        block = registry.create("Resistor", resistance=100.0)
        assert isinstance(block, Resistor)

    def test_total_registry_count(self):
        """After adding 4 electrical blocks, total should be 16."""
        assert len(registry) == 16
