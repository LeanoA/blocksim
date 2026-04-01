"""RLC circuit validation: analytical solution comparison (T-2.3).

This is the MVP validation test that proves the BlockSim simulation engine
produces physically correct results by comparing a series RLC circuit step
response against its known analytical solution.

Series RLC Circuit:
    Vs ─── R ─── L ─── C ─── GND

KVL: V_s = V_R + V_L + V_C = I*R + L*dI/dt + V_C
State equations:
    dI/dt  = (V_s - I*R - V_C) / L
    dV_C/dt = I / C

Analytical solution for underdamped step response:
    α = R / (2L)
    ω0 = 1 / √(LC)
    ωd = √(ω0² - α²)
    V_C(t) = V_s * (1 - e^(-αt) * (cos(ωd*t) + (α/ωd)*sin(ωd*t)))

Block diagram (signal-flow):
    VoltageSource → Sum1(+-) → Sum2(+-) → Inductor → Resistor
                         ↑                    ↓           ↓
                         │                    │     V_R ──┘
                         │                    ↓
                         └── V_C ── Capacitor ←── I

Where:
    Sum1: V_s - V_R → intermediate
    Sum2: intermediate - V_C → V_L (input to inductor)
    Inductor: dI/dt = V_L / L, outputs I
    Resistor: V_R = I * R
    Capacitor: dV/dt = I / C, outputs V_C
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from blocksim.blocks.electrical import Capacitor, Inductor, Resistor, VoltageSource
from blocksim.blocks.math_ops import Sum
from blocksim.blocks.sinks import Scope
from blocksim.core.system import DynamicSystem


# ---------------------------------------------------------------------------
# Analytical solutions
# ---------------------------------------------------------------------------


def analytical_vc_underdamped(
    t: np.ndarray,
    vs: float,
    r: float,
    l: float,
    c: float,
) -> np.ndarray:
    """Analytical capacitor voltage for underdamped series RLC step response.

    Parameters
    ----------
    t: time array
    vs: step voltage
    r: resistance (Ω)
    l: inductance (H)
    c: capacitance (F)

    Returns
    -------
    V_C(t) array
    """
    alpha = r / (2.0 * l)
    omega_0 = 1.0 / math.sqrt(l * c)
    omega_d = math.sqrt(omega_0**2 - alpha**2)

    vc = vs * (
        1.0
        - np.exp(-alpha * t)
        * (np.cos(omega_d * t) + (alpha / omega_d) * np.sin(omega_d * t))
    )
    return vc


def analytical_current_underdamped(
    t: np.ndarray,
    vs: float,
    r: float,
    l: float,
    c: float,
) -> np.ndarray:
    """Analytical current for underdamped series RLC step response.

    I(t) = (V_s / (ωd * L)) * e^(-αt) * sin(ωd * t)
    """
    alpha = r / (2.0 * l)
    omega_0 = 1.0 / math.sqrt(l * c)
    omega_d = math.sqrt(omega_0**2 - alpha**2)

    current = (vs / (omega_d * l)) * np.exp(-alpha * t) * np.sin(omega_d * t)
    return current


def analytical_vc_overdamped(
    t: np.ndarray,
    vs: float,
    r: float,
    l: float,
    c: float,
) -> np.ndarray:
    """Analytical capacitor voltage for overdamped series RLC step response.

    V_C(t) = V_s * (1 - (s2*e^(s1*t) - s1*e^(s2*t)) / (s2 - s1))
    where s1,s2 = -α ± √(α² - ω0²)
    """
    alpha = r / (2.0 * l)
    omega_0 = 1.0 / math.sqrt(l * c)
    beta = math.sqrt(alpha**2 - omega_0**2)

    s1 = -alpha + beta
    s2 = -alpha - beta

    vc = vs * (1.0 - (s2 * np.exp(s1 * t) - s1 * np.exp(s2 * t)) / (s2 - s1))
    return vc


def analytical_vc_critically_damped(
    t: np.ndarray,
    vs: float,
    r: float,
    l: float,
    c: float,
) -> np.ndarray:
    """Analytical capacitor voltage for critically damped series RLC step response.

    V_C(t) = V_s * (1 - (1 + α*t) * e^(-αt))
    """
    alpha = r / (2.0 * l)

    vc = vs * (1.0 - (1.0 + alpha * t) * np.exp(-alpha * t))
    return vc


def rms_error_percent(simulated: np.ndarray, analytical: np.ndarray) -> float:
    """Compute RMS error as a percentage of the signal range.

    Returns
    -------
    float
        RMS error as percentage of the peak-to-peak analytical range.
    """
    error = simulated - analytical
    rms = np.sqrt(np.mean(error**2))
    signal_range = np.max(np.abs(analytical)) if np.max(np.abs(analytical)) > 0 else 1.0
    return (rms / signal_range) * 100.0


# ---------------------------------------------------------------------------
# Helper: Build series RLC system using blocks
# ---------------------------------------------------------------------------


def build_series_rlc_system(
    vs_voltage: float,
    resistance: float,
    inductance: float,
    capacitance: float,
) -> tuple[DynamicSystem, dict[str, str]]:
    """Build a series RLC circuit using BlockSim electrical blocks.

    The circuit topology is:

        VoltageSource → Sum1(+-) → Sum2(+-) → Inductor
                             ↑                    ↓
                             │            I → Capacitor → V_C ──→ Sum2
                             │            ↓
                             └── V_R ← Resistor

    Returns
    -------
    (system, block_ids)
        The compiled DynamicSystem and a dict of block IDs.
    """
    sys = DynamicSystem()

    # Create blocks
    vsrc = VoltageSource(voltage=vs_voltage, block_id="vsrc")
    resistor = Resistor(resistance=resistance, block_id="resistor")
    inductor = Inductor(inductance=inductance, i0=0.0, block_id="inductor")
    capacitor = Capacitor(capacitance=capacitance, v0=0.0, block_id="capacitor")
    sum1 = Sum(signs="+-", block_id="sum1")  # V_s - V_R
    sum2 = Sum(signs="+-", block_id="sum2")  # (V_s - V_R) - V_C = V_L
    scope_vc = Scope(block_id="scope_vc")
    scope_i = Scope(block_id="scope_i")

    # Add blocks
    for block in [vsrc, resistor, inductor, capacitor, sum1, sum2, scope_vc, scope_i]:
        sys.add_block(block)

    # Wire the circuit:
    # Sum1: in1 = V_s, in2 = V_R → out = V_s - V_R
    sys.connect("vsrc", "out", "sum1", "in1")
    sys.connect("resistor", "out", "sum1", "in2")

    # Sum2: in1 = Sum1.out, in2 = V_C → out = (V_s - V_R) - V_C = V_L
    sys.connect("sum1", "out", "sum2", "in1")
    sys.connect("capacitor", "out", "sum2", "in2")

    # Inductor: in = V_L → out = I
    sys.connect("sum2", "out", "inductor", "in")

    # Resistor: in = I → out = V_R
    sys.connect("inductor", "out", "resistor", "in")

    # Capacitor: in = I → out = V_C
    sys.connect("inductor", "out", "capacitor", "in")

    # Scopes
    sys.connect("capacitor", "out", "scope_vc", "in")
    sys.connect("inductor", "out", "scope_i", "in")

    sys.compile()

    block_ids = {
        "vsrc": vsrc.id,
        "resistor": resistor.id,
        "inductor": inductor.id,
        "capacitor": capacitor.id,
        "scope_vc": scope_vc.id,
        "scope_i": scope_i.id,
    }

    return sys, block_ids


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSeriesRLCUnderdamped:
    """Underdamped RLC circuit: ω0 > α (oscillatory response).

    Test parameters: R=10Ω, L=1H, C=100µF, Vs=10V
    α = R/(2L) = 5
    ω0 = 1/√(LC) = 100 rad/s
    ωd = √(ω0² - α²) = √(10000 - 25) ≈ 99.87 rad/s
    """

    R = 10.0       # Ω
    L = 1.0        # H
    C = 100e-6     # F (100 µF)
    VS = 10.0      # V
    DT = 1e-5      # s (10 µs — small enough for RK4 accuracy)
    T_END = 0.5    # s (enough for several oscillation cycles)

    def test_capacitor_voltage_matches_analytical(self):
        """Core acceptance test: V_C(t) within 1% RMS error of analytical."""
        sys, _ = build_series_rlc_system(self.VS, self.R, self.L, self.C)
        result = sys.simulate(t_span=(0.0, self.T_END), dt=self.DT, solver="rk4")

        t = result.time
        vc_sim = result.outputs["capacitor.out"]

        vc_analytical = analytical_vc_underdamped(t, self.VS, self.R, self.L, self.C)

        error_pct = rms_error_percent(vc_sim, vc_analytical)
        assert error_pct < 1.0, (
            f"RMS error {error_pct:.4f}% exceeds 1% threshold. "
            f"Simulation does not match analytical solution."
        )

    def test_current_matches_analytical(self):
        """Verify inductor current matches analytical solution."""
        sys, _ = build_series_rlc_system(self.VS, self.R, self.L, self.C)
        result = sys.simulate(t_span=(0.0, self.T_END), dt=self.DT, solver="rk4")

        t = result.time
        i_sim = result.outputs["inductor.out"]

        i_analytical = analytical_current_underdamped(t, self.VS, self.R, self.L, self.C)

        error_pct = rms_error_percent(i_sim, i_analytical)
        assert error_pct < 1.0, (
            f"Current RMS error {error_pct:.4f}% exceeds 1% threshold."
        )

    def test_initial_conditions(self):
        """V_C(0) = 0 and I(0) = 0 for zero initial conditions."""
        sys, _ = build_series_rlc_system(self.VS, self.R, self.L, self.C)
        result = sys.simulate(t_span=(0.0, self.T_END), dt=self.DT, solver="rk4")

        assert result.outputs["capacitor.out"][0] == pytest.approx(0.0, abs=1e-10)
        assert result.outputs["inductor.out"][0] == pytest.approx(0.0, abs=1e-10)

    def test_steady_state_voltage(self):
        """At steady state, V_C should approach V_s."""
        # Extend simulation time for steady-state check.
        # With α=5, settling time ≈ 5/α = 1s. Use t_end=2s.
        sys, _ = build_series_rlc_system(self.VS, self.R, self.L, self.C)
        result = sys.simulate(t_span=(0.0, 2.0), dt=self.DT, solver="rk4")

        vc_final = result.outputs["capacitor.out"][-1]
        assert vc_final == pytest.approx(self.VS, rel=0.01)

    def test_steady_state_current_zero(self):
        """At steady state, current should approach 0 (capacitor fully charged)."""
        sys, _ = build_series_rlc_system(self.VS, self.R, self.L, self.C)
        result = sys.simulate(t_span=(0.0, self.T_END), dt=self.DT, solver="rk4")

        i_final = result.outputs["inductor.out"][-1]
        assert i_final == pytest.approx(0.0, abs=0.01)

    def test_oscillation_present(self):
        """Underdamped response should show oscillation (V_C overshoots V_s)."""
        sys, _ = build_series_rlc_system(self.VS, self.R, self.L, self.C)
        result = sys.simulate(t_span=(0.0, self.T_END), dt=self.DT, solver="rk4")

        vc = result.outputs["capacitor.out"]
        # The underdamped response overshoots V_s
        assert np.max(vc) > self.VS * 1.01, "Expected overshoot in underdamped response"

    def test_energy_conservation_approximate(self):
        """Total energy should be roughly conserved (minus resistive dissipation)."""
        # Use longer simulation to reach true steady state.
        sys, _ = build_series_rlc_system(self.VS, self.R, self.L, self.C)
        result = sys.simulate(t_span=(0.0, 2.0), dt=self.DT, solver="rk4")

        # At steady state: all energy stored in capacitor
        # E_C = 0.5 * C * V_C²
        vc_final = result.outputs["capacitor.out"][-1]
        energy_cap = 0.5 * self.C * vc_final**2
        energy_source = 0.5 * self.C * self.VS**2

        # Capacitor energy should be close to source energy at steady state
        assert energy_cap == pytest.approx(energy_source, rel=0.02)


class TestSeriesRLCOverdamped:
    """Overdamped RLC circuit: α > ω0 (no oscillation).

    Test parameters: R=200Ω, L=1H, C=100µF
    α = R/(2L) = 100
    ω0 = 1/√(LC) = 100 rad/s → α = ω0, so use R=201 for overdamped
    Actually let's use: R=400Ω, L=1H, C=100µF
    α = 200, ω0 = 100 → clearly overdamped
    """

    R = 400.0      # Ω
    L = 1.0        # H
    C = 100e-6     # F
    VS = 10.0      # V
    DT = 1e-4      # s (overdamped is less stiff, can use larger dt)
    T_END = 0.2    # s

    def test_capacitor_voltage_matches_analytical(self):
        """V_C(t) within 1% RMS error for overdamped case."""
        sys, _ = build_series_rlc_system(self.VS, self.R, self.L, self.C)
        result = sys.simulate(t_span=(0.0, self.T_END), dt=self.DT, solver="rk4")

        t = result.time
        vc_sim = result.outputs["capacitor.out"]

        vc_analytical = analytical_vc_overdamped(t, self.VS, self.R, self.L, self.C)

        error_pct = rms_error_percent(vc_sim, vc_analytical)
        assert error_pct < 1.0, (
            f"Overdamped RMS error {error_pct:.4f}% exceeds 1% threshold."
        )

    def test_no_overshoot(self):
        """Overdamped response should not overshoot V_s."""
        sys, _ = build_series_rlc_system(self.VS, self.R, self.L, self.C)
        result = sys.simulate(t_span=(0.0, self.T_END), dt=self.DT, solver="rk4")

        vc = result.outputs["capacitor.out"]
        # Should monotonically approach V_s without exceeding it
        assert np.max(vc) <= self.VS * 1.001, "Overdamped should not overshoot"

    def test_monotonic_rise(self):
        """Overdamped capacitor voltage should increase monotonically."""
        sys, _ = build_series_rlc_system(self.VS, self.R, self.L, self.C)
        result = sys.simulate(t_span=(0.0, self.T_END), dt=self.DT, solver="rk4")

        vc = result.outputs["capacitor.out"]
        # Check that V_C is monotonically non-decreasing
        diffs = np.diff(vc)
        assert np.all(diffs >= -1e-10), "Overdamped V_C should be monotonically increasing"


class TestSeriesRLCCriticallyDamped:
    """Critically damped RLC circuit: α = ω0 (fastest non-oscillatory response).

    R² = 4L/C → R = 2√(L/C)
    With L=1H, C=100µF: R = 2√(1/100e-6) = 2*100 = 200Ω
    """

    L = 1.0        # H
    C = 100e-6     # F
    R = 2.0 * math.sqrt(1.0 / 100e-6)  # = 200Ω
    VS = 10.0      # V
    DT = 1e-4      # s
    T_END = 0.2    # s

    def test_capacitor_voltage_matches_analytical(self):
        """V_C(t) within 1% RMS error for critically damped case."""
        sys, _ = build_series_rlc_system(self.VS, self.R, self.L, self.C)
        result = sys.simulate(t_span=(0.0, self.T_END), dt=self.DT, solver="rk4")

        t = result.time
        vc_sim = result.outputs["capacitor.out"]

        vc_analytical = analytical_vc_critically_damped(t, self.VS, self.R, self.L, self.C)

        error_pct = rms_error_percent(vc_sim, vc_analytical)
        assert error_pct < 1.0, (
            f"Critically damped RMS error {error_pct:.4f}% exceeds 1% threshold."
        )

    def test_no_overshoot(self):
        """Critically damped should not overshoot."""
        sys, _ = build_series_rlc_system(self.VS, self.R, self.L, self.C)
        result = sys.simulate(t_span=(0.0, self.T_END), dt=self.DT, solver="rk4")

        vc = result.outputs["capacitor.out"]
        assert np.max(vc) <= self.VS * 1.001, "Critically damped should not overshoot"


class TestRLCWithDifferentSolvers:
    """Test the same RLC circuit with different solvers."""

    R = 10.0
    L = 1.0
    C = 100e-6
    VS = 10.0

    def test_euler_less_accurate_than_rk4(self):
        """Euler should be less accurate than RK4 for the same dt."""
        dt = 1e-4
        t_end = 0.1

        sys_rk4, _ = build_series_rlc_system(self.VS, self.R, self.L, self.C)
        result_rk4 = sys_rk4.simulate(t_span=(0.0, t_end), dt=dt, solver="rk4")

        sys_euler, _ = build_series_rlc_system(self.VS, self.R, self.L, self.C)
        result_euler = sys_euler.simulate(t_span=(0.0, t_end), dt=dt, solver="euler")

        t = result_rk4.time
        vc_analytical = analytical_vc_underdamped(t, self.VS, self.R, self.L, self.C)

        error_rk4 = rms_error_percent(result_rk4.outputs["capacitor.out"], vc_analytical)
        error_euler = rms_error_percent(result_euler.outputs["capacitor.out"], vc_analytical)

        assert error_rk4 < error_euler, "RK4 should be more accurate than Euler"

    def test_euler_converges_with_small_dt(self):
        """Euler with very small dt should still get reasonable accuracy."""
        dt = 1e-5  # Much smaller dt for Euler
        t_end = 0.1

        sys, _ = build_series_rlc_system(self.VS, self.R, self.L, self.C)
        result = sys.simulate(t_span=(0.0, t_end), dt=dt, solver="euler")

        t = result.time
        vc_analytical = analytical_vc_underdamped(t, self.VS, self.R, self.L, self.C)

        error_pct = rms_error_percent(result.outputs["capacitor.out"], vc_analytical)
        # Euler with small dt should be within 5%
        assert error_pct < 5.0, f"Euler error {error_pct:.2f}% too high even with small dt"


class TestRLCCircuitTopology:
    """Test that the RLC circuit compiles and runs without algebraic loop errors."""

    def test_system_compiles(self):
        """Series RLC should compile without AlgebraicLoopError."""
        sys, _ = build_series_rlc_system(10.0, 10.0, 1.0, 100e-6)
        # If we get here, compile succeeded (called in build_series_rlc_system)
        assert len(sys.sorted_blocks) == 8  # 6 blocks + 2 scopes

    def test_system_has_two_stateful_blocks(self):
        """Inductor and Capacitor should be the stateful blocks."""
        sys, _ = build_series_rlc_system(10.0, 10.0, 1.0, 100e-6)
        stateful_ids = [b.id for b in sys._stateful_blocks]
        assert "inductor" in stateful_ids
        assert "capacitor" in stateful_ids
        assert len(stateful_ids) == 2

    def test_total_state_size(self):
        """Total state: 1 (inductor current) + 1 (capacitor voltage) = 2."""
        sys, _ = build_series_rlc_system(10.0, 10.0, 1.0, 100e-6)
        assert sys._total_state_size == 2
