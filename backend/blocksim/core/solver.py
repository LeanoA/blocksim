"""ODE solvers for BlockSim: Euler, RK4, and SciPy-based adaptive solvers.

This module implements a pluggable solver strategy:

- :class:`Solver` — abstract base defining the solver interface
- :class:`EulerSolver` — first-order fixed-step Euler method
- :class:`RK4Solver` — fourth-order Runge-Kutta (primary solver for MVP)
- :class:`ScipySolver` — SciPy ``solve_ivp`` wrapper (RK45, Radau, etc.)
- :func:`get_solver` — factory to retrieve solvers by name string

Each solver's :meth:`step` method advances the state vector by one time step
given a derivatives function ``f(t, y) → dy/dt``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
from scipy.integrate import solve_ivp


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

# Derivatives function: f(t, state) → d(state)/dt
DerivativesFn = Callable[[float, np.ndarray], np.ndarray]


# ---------------------------------------------------------------------------
# Simulation result container
# ---------------------------------------------------------------------------


@dataclass
class SimulationResult:
    """Container for simulation output data.

    Parameters
    ----------
    time:
        1-D array of time values (length N).
    states:
        2-D array of state vectors (N × state_size).
    outputs:
        Dict mapping ``"block_id.port_name"`` → 1-D array of values (length N).
    block_errors:
        Dict mapping ``block_id`` → list of error dicts recorded during
        simulation.  Each dict has keys ``block_id``, ``step``, ``time``,
        and ``error``.  Empty when no errors occurred.
    """

    time: np.ndarray
    states: np.ndarray
    outputs: dict[str, np.ndarray] = field(default_factory=dict)
    block_errors: dict[str, list[dict]] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Solver ABC
# ---------------------------------------------------------------------------


class Solver(ABC):
    """Abstract base class for ODE solvers.

    Sub-classes implement :meth:`step` which advances state by one ``dt``.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable solver name."""
        ...

    @abstractmethod
    def step(
        self,
        f: DerivativesFn,
        t: float,
        state: np.ndarray,
        dt: float,
    ) -> np.ndarray:
        """Advance *state* by one time step.

        Parameters
        ----------
        f:
            Derivatives function ``f(t, y) → dy/dt``.
        t:
            Current time.
        state:
            Current state vector.
        dt:
            Time step size.

        Returns
        -------
        np.ndarray
            New state vector at ``t + dt``.
        """
        ...


# ---------------------------------------------------------------------------
# Euler solver
# ---------------------------------------------------------------------------


class EulerSolver(Solver):
    """First-order explicit Euler method: y_{n+1} = y_n + dt * f(t_n, y_n).

    Simple and fast, but only first-order accurate.  Useful for testing and
    debugging; not recommended for production simulations.
    """

    @property
    def name(self) -> str:
        return "euler"

    def step(
        self,
        f: DerivativesFn,
        t: float,
        state: np.ndarray,
        dt: float,
    ) -> np.ndarray:
        dy = f(t, state)
        return state + dt * dy


# ---------------------------------------------------------------------------
# RK4 solver
# ---------------------------------------------------------------------------


class RK4Solver(Solver):
    """Classic fourth-order Runge-Kutta method.

    This is the primary fixed-step solver for BlockSim.  Fourth-order
    accuracy provides a good balance between precision and performance for
    most simulation scenarios.

    The update rule is:

        k1 = f(t,        y)
        k2 = f(t + dt/2, y + dt/2 * k1)
        k3 = f(t + dt/2, y + dt/2 * k2)
        k4 = f(t + dt,   y + dt * k3)
        y_{n+1} = y_n + (dt / 6) * (k1 + 2*k2 + 2*k3 + k4)
    """

    @property
    def name(self) -> str:
        return "rk4"

    def step(
        self,
        f: DerivativesFn,
        t: float,
        state: np.ndarray,
        dt: float,
    ) -> np.ndarray:
        k1 = f(t, state)
        k2 = f(t + dt / 2, state + dt / 2 * k1)
        k3 = f(t + dt / 2, state + dt / 2 * k2)
        k4 = f(t + dt, state + dt * k3)
        return state + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)


# ---------------------------------------------------------------------------
# SciPy adaptive solver
# ---------------------------------------------------------------------------


class ScipySolver(Solver):
    """Adaptive solver wrapping :func:`scipy.integrate.solve_ivp`.

    This solver delegates integration to SciPy, supporting multiple methods:

    - ``"RK45"`` — explicit Runge-Kutta 4(5) (Dormand-Prince), good default
    - ``"Radau"`` — implicit Runge-Kutta (Radau IIA, order 5), excellent for
      stiff systems such as RLC circuits with very different time constants

    The :meth:`step` method integrates over a single ``[t, t+dt]`` interval
    and returns the state at ``t + dt``, matching the fixed-step solver API.

    Parameters
    ----------
    method:
        SciPy solver method string, e.g. ``"RK45"`` or ``"Radau"``.
    rtol:
        Relative tolerance for the adaptive solver.
    atol:
        Absolute tolerance for the adaptive solver.
    """

    def __init__(
        self,
        method: str = "RK45",
        rtol: float = 1e-8,
        atol: float = 1e-10,
    ) -> None:
        self._method = method
        self._rtol = rtol
        self._atol = atol

    @property
    def name(self) -> str:
        return f"scipy_{self._method.lower()}"

    def step(
        self,
        f: DerivativesFn,
        t: float,
        state: np.ndarray,
        dt: float,
    ) -> np.ndarray:
        """Integrate from *t* to *t + dt* using SciPy's ``solve_ivp``.

        Parameters
        ----------
        f:
            Derivatives function ``f(t, y) → dy/dt``.
        t:
            Current time.
        state:
            Current state vector.
        dt:
            Time step size.

        Returns
        -------
        np.ndarray
            New state vector at ``t + dt``.

        Raises
        ------
        RuntimeError
            If the SciPy integrator fails to converge.
        """
        result = solve_ivp(
            fun=f,
            t_span=(t, t + dt),
            y0=state,
            method=self._method,
            rtol=self._rtol,
            atol=self._atol,
            dense_output=False,
        )
        if not result.success:
            raise RuntimeError(
                f"ScipySolver({self._method}) failed at t={t}: {result.message}"
            )
        # result.y has shape (n_states, n_points); take the last column
        return np.asarray(result.y[:, -1], dtype=float)


# ---------------------------------------------------------------------------
# Solver registry / factory
# ---------------------------------------------------------------------------

_SOLVER_REGISTRY: dict[str, type[Solver] | Callable[[], Solver]] = {
    "euler": EulerSolver,
    "rk4": RK4Solver,
    "scipy_rk45": lambda: ScipySolver(method="RK45"),
    "radau": lambda: ScipySolver(method="Radau"),
}


def get_solver(name: str) -> Solver:
    """Return a solver instance by name.

    Parameters
    ----------
    name:
        Solver name: ``"euler"``, ``"rk4"``, ``"scipy_rk45"``, or ``"radau"``.

    Returns
    -------
    Solver
        An instantiated solver.

    Raises
    ------
    ValueError
        If *name* is not a registered solver.
    """
    key = name.lower()
    if key not in _SOLVER_REGISTRY:
        available = ", ".join(sorted(_SOLVER_REGISTRY.keys()))
        raise ValueError(
            f"Unknown solver '{name}'. Available solvers: {available}"
        )
    factory = _SOLVER_REGISTRY[key]
    return factory()
