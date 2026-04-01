"""Tests for ODE solvers: Euler, RK4, ScipySolver, solver factory.

Covers spec scenarios:
- RK4 solver execution: integrating dy/dt=1 from 0→1 yields y=1.0 within 0.1%
- Solver selectable by name string
- Euler and RK4 accuracy against analytical solutions
- ScipySolver (RK45, Radau) accuracy for adaptive integration
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from blocksim.core.solver import (
    EulerSolver,
    RK4Solver,
    ScipySolver,
    SimulationResult,
    Solver,
    get_solver,
)


# ---------------------------------------------------------------------------
# Helper: run a solver over a time span
# ---------------------------------------------------------------------------


def _integrate(
    solver: Solver,
    f,
    t_span: tuple[float, float],
    y0: np.ndarray,
    dt: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Run a solver from t_span[0] to t_span[1] at fixed dt.

    Returns (time_array, final_state).
    """
    t = t_span[0]
    y = y0.copy()
    while t < t_span[1] - dt / 2:
        y = solver.step(f, t, y, dt)
        t += dt
    return np.array(t), y


# ---------------------------------------------------------------------------
# EulerSolver tests
# ---------------------------------------------------------------------------


class TestEulerSolver:
    """Tests for the Euler solver."""

    def test_name(self):
        assert EulerSolver().name == "euler"

    def test_constant_derivative(self):
        """dy/dt = 1 → y(1) = 1.0 (exact for Euler)."""
        solver = EulerSolver()
        f = lambda t, y: np.array([1.0])
        y = np.array([0.0])
        dt = 0.001
        for i in range(1000):
            y = solver.step(f, i * dt, y, dt)
        assert y[0] == pytest.approx(1.0, abs=1e-10)

    def test_linear_derivative(self):
        """dy/dt = t → y(t) = t²/2. Euler has O(dt) global error."""
        solver = EulerSolver()
        f = lambda t, y: np.array([t])
        y = np.array([0.0])
        dt = 0.001
        n_steps = 1000  # t from 0 to 1
        for i in range(n_steps):
            t = i * dt
            y = solver.step(f, t, y, dt)
        # Analytical: y(1) = 0.5. Euler error ~ O(dt) ≈ 0.001
        assert y[0] == pytest.approx(0.5, abs=0.01)

    def test_exponential_decay(self):
        """dy/dt = -y → y(t) = e^(-t). Check at t=1."""
        solver = EulerSolver()
        f = lambda t, y: -y
        y = np.array([1.0])
        dt = 0.0001
        n_steps = 10000  # t from 0 to 1
        for i in range(n_steps):
            y = solver.step(f, i * dt, y, dt)
        expected = math.exp(-1.0)
        assert y[0] == pytest.approx(expected, rel=0.01)

    def test_multi_state(self):
        """Two-dimensional system: dy0/dt = 1, dy1/dt = 2."""
        solver = EulerSolver()
        f = lambda t, y: np.array([1.0, 2.0])
        y = np.array([0.0, 0.0])
        y = solver.step(f, 0.0, y, 0.1)
        np.testing.assert_allclose(y, [0.1, 0.2])


# ---------------------------------------------------------------------------
# RK4Solver tests
# ---------------------------------------------------------------------------


class TestRK4Solver:
    """Tests for the RK4 solver."""

    def test_name(self):
        assert RK4Solver().name == "rk4"

    def test_constant_derivative(self):
        """dy/dt = 1 → y(1) = 1.0 (exact for RK4)."""
        solver = RK4Solver()
        f = lambda t, y: np.array([1.0])
        y = np.array([0.0])
        dt = 0.001
        for i in range(1000):
            y = solver.step(f, i * dt, y, dt)
        assert y[0] == pytest.approx(1.0, abs=1e-10)

    def test_quadratic_exact(self):
        """dy/dt = t → y(t) = t²/2. RK4 is exact for polynomials up to degree 4."""
        solver = RK4Solver()
        f = lambda t, y: np.array([t])
        y = np.array([0.0])
        dt = 0.01
        n_steps = 100  # t from 0 to 1
        for i in range(n_steps):
            t = i * dt
            y = solver.step(f, t, y, dt)
        # RK4 is exact for polynomials ≤ degree 4.
        assert y[0] == pytest.approx(0.5, abs=1e-10)

    def test_exponential_decay_high_accuracy(self):
        """dy/dt = -y → y(t) = e^(-t). RK4 should be much more accurate than Euler."""
        solver = RK4Solver()
        f = lambda t, y: -y
        y = np.array([1.0])
        dt = 0.001
        n_steps = 1000  # t from 0 to 1
        for i in range(n_steps):
            y = solver.step(f, i * dt, y, dt)
        expected = math.exp(-1.0)
        # RK4 global error is O(dt⁴) ≈ 1e-12 here. Use 0.1% tolerance.
        assert y[0] == pytest.approx(expected, rel=0.001)

    def test_harmonic_oscillator(self):
        """dy0/dt = y1, dy1/dt = -y0 → y0(t) = cos(t), y1(t) = -sin(t)."""
        solver = RK4Solver()
        f = lambda t, y: np.array([y[1], -y[0]])
        y = np.array([1.0, 0.0])  # cos(0)=1, -sin(0)=0
        dt = 0.001
        n_steps = 1000  # t from 0 to 1
        for i in range(n_steps):
            y = solver.step(f, i * dt, y, dt)
        assert y[0] == pytest.approx(math.cos(1.0), rel=0.001)
        assert y[1] == pytest.approx(-math.sin(1.0), rel=0.001)

    def test_rk4_spec_scenario_integration(self):
        """Spec scenario: integrating dy/dt=1 from 0→1 yields y=1.0 within 0.1%."""
        solver = RK4Solver()
        f = lambda t, y: np.array([1.0])
        y = np.array([0.0])
        dt = 0.001
        for i in range(1000):
            y = solver.step(f, i * dt, y, dt)
        assert y[0] == pytest.approx(1.0, rel=0.001)


# ---------------------------------------------------------------------------
# SimulationResult tests
# ---------------------------------------------------------------------------


class TestSimulationResult:
    """Tests for the SimulationResult container."""

    def test_creation(self):
        t = np.linspace(0, 1, 100)
        s = np.zeros((100, 2))
        result = SimulationResult(time=t, states=s)
        assert len(result.time) == 100
        assert result.states.shape == (100, 2)
        assert result.outputs == {}

    def test_with_outputs(self):
        t = np.array([0.0, 0.1, 0.2])
        s = np.zeros((3, 1))
        outputs = {"scope.in": np.array([1.0, 2.0, 3.0])}
        result = SimulationResult(time=t, states=s, outputs=outputs)
        assert "scope.in" in result.outputs
        np.testing.assert_array_equal(result.outputs["scope.in"], [1.0, 2.0, 3.0])


# ---------------------------------------------------------------------------
# Solver factory tests
# ---------------------------------------------------------------------------


class TestSolverFactory:
    """Tests for get_solver() factory function."""

    def test_get_euler(self):
        solver = get_solver("euler")
        assert isinstance(solver, EulerSolver)

    def test_get_rk4(self):
        solver = get_solver("rk4")
        assert isinstance(solver, RK4Solver)

    def test_case_insensitive(self):
        solver = get_solver("RK4")
        assert isinstance(solver, RK4Solver)

    def test_unknown_solver_raises(self):
        with pytest.raises(ValueError, match="Unknown solver"):
            get_solver("nonexistent")

    def test_unknown_solver_lists_available(self):
        with pytest.raises(ValueError, match="euler"):
            get_solver("bad_name")

    def test_get_scipy_rk45(self):
        solver = get_solver("scipy_rk45")
        assert isinstance(solver, ScipySolver)
        assert solver.name == "scipy_rk45"

    def test_get_radau(self):
        solver = get_solver("radau")
        assert isinstance(solver, ScipySolver)
        assert solver.name == "scipy_radau"

    def test_radau_case_insensitive(self):
        solver = get_solver("Radau")
        assert isinstance(solver, ScipySolver)


# ---------------------------------------------------------------------------
# ScipySolver tests
# ---------------------------------------------------------------------------


class TestScipySolver:
    """Tests for the SciPy adaptive solver wrapper."""

    def test_name_rk45(self):
        solver = ScipySolver(method="RK45")
        assert solver.name == "scipy_rk45"

    def test_name_radau(self):
        solver = ScipySolver(method="Radau")
        assert solver.name == "scipy_radau"

    def test_constant_derivative(self):
        """dy/dt = 1 → y(1) = 1.0 (should be exact)."""
        solver = ScipySolver(method="RK45")
        f = lambda t, y: np.array([1.0])
        y = np.array([0.0])
        dt = 0.001
        for i in range(1000):
            y = solver.step(f, i * dt, y, dt)
        assert y[0] == pytest.approx(1.0, abs=1e-6)

    def test_exponential_decay_rk45(self):
        """dy/dt = -y → y(t) = e^(-t). SciPy RK45 should be highly accurate."""
        solver = ScipySolver(method="RK45")
        f = lambda t, y: -y
        y = np.array([1.0])
        dt = 0.01
        n_steps = 100  # t from 0 to 1
        for i in range(n_steps):
            y = solver.step(f, i * dt, y, dt)
        expected = math.exp(-1.0)
        assert y[0] == pytest.approx(expected, rel=1e-6)

    def test_exponential_decay_radau(self):
        """dy/dt = -y → y(t) = e^(-t). Radau solver for implicit integration."""
        solver = ScipySolver(method="Radau")
        f = lambda t, y: -y
        y = np.array([1.0])
        dt = 0.01
        n_steps = 100  # t from 0 to 1
        for i in range(n_steps):
            y = solver.step(f, i * dt, y, dt)
        expected = math.exp(-1.0)
        assert y[0] == pytest.approx(expected, rel=1e-4)

    def test_radau_stiff_system(self):
        """Test Radau on a mildly stiff problem: dy/dt = -50*y, y(0) = 1.

        Analytical: y(t) = e^(-50t). At t=0.1, y ≈ e^(-5) ≈ 0.006738.
        Radau handles stiff systems well even with larger time steps.
        """
        solver = ScipySolver(method="Radau")
        f = lambda t, y: np.array([-50.0 * y[0]])
        y = np.array([1.0])
        # Use fewer, larger steps to exercise the implicit method
        dt = 0.01
        n_steps = 10  # t from 0 to 0.1
        for i in range(n_steps):
            y = solver.step(f, i * dt, y, dt)
        expected = math.exp(-5.0)
        assert y[0] == pytest.approx(expected, rel=1e-3)

    def test_harmonic_oscillator_rk45(self):
        """dy0/dt = y1, dy1/dt = -y0 → y0(t) = cos(t)."""
        solver = ScipySolver(method="RK45")
        f = lambda t, y: np.array([y[1], -y[0]])
        y = np.array([1.0, 0.0])
        dt = 0.01
        n_steps = 100  # t from 0 to 1
        for i in range(n_steps):
            y = solver.step(f, i * dt, y, dt)
        assert y[0] == pytest.approx(math.cos(1.0), rel=1e-6)
        assert y[1] == pytest.approx(-math.sin(1.0), rel=1e-6)

    def test_multi_state(self):
        """Two-dimensional constant system: dy0/dt = 1, dy1/dt = 2."""
        solver = ScipySolver(method="RK45")
        f = lambda t, y: np.array([1.0, 2.0])
        y = np.array([0.0, 0.0])
        y = solver.step(f, 0.0, y, 0.1)
        np.testing.assert_allclose(y, [0.1, 0.2], atol=1e-10)
