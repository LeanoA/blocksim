"""Math and continuous-time blocks.

Math blocks perform algebraic operations on signals:
- :class:`Gain` — multiplies input by a constant
- :class:`Sum` — adds/subtracts two inputs with configurable signs
- :class:`Multiply` — element-wise multiplication of two inputs

Continuous blocks have internal state (ODE integration):
- :class:`Integrator` — integrates input signal over time
- :class:`Derivative` — approximates time derivative of input (finite difference)
"""

from __future__ import annotations

import numpy as np

from blocksim.core.block import Block, InputPort, OutputPort


# ---------------------------------------------------------------------------
# Gain
# ---------------------------------------------------------------------------


class Gain(Block):
    """Multiplies the input signal by a constant gain factor.

    ``out = k * in``

    Parameters
    ----------
    k:
        Gain factor.
    """

    _input_port_defs = [InputPort("in")]
    _output_port_defs = [OutputPort("out")]

    def __init__(self, k: float = 1.0, **kwargs) -> None:
        super().__init__(params={"k": k}, **kwargs)

    def compute(self, t: float) -> None:
        self.set_output("out", self.params["k"] * self.get_input("in"))


# ---------------------------------------------------------------------------
# Sum
# ---------------------------------------------------------------------------


class Sum(Block):
    """Adds or subtracts two input signals.

    ``out = signs[0] * in1 + signs[1] * in2``

    Parameters
    ----------
    signs:
        A string like ``"++"`` or ``"+-"`` indicating the sign of each input.
        Default is ``"++"`` (add both).
    """

    _input_port_defs = [InputPort("in1"), InputPort("in2")]
    _output_port_defs = [OutputPort("out")]

    def __init__(self, signs: str = "++", **kwargs) -> None:
        if len(signs) != 2 or not all(s in ("+", "-") for s in signs):
            raise ValueError(
                f"signs must be a 2-character string of '+' and '-', got '{signs}'"
            )
        super().__init__(params={"signs": signs}, **kwargs)

    def compute(self, t: float) -> None:
        signs = self.params["signs"]
        s1 = 1.0 if signs[0] == "+" else -1.0
        s2 = 1.0 if signs[1] == "+" else -1.0
        result = s1 * self.get_input("in1") + s2 * self.get_input("in2")
        self.set_output("out", result)


# ---------------------------------------------------------------------------
# Multiply
# ---------------------------------------------------------------------------


class Multiply(Block):
    """Element-wise multiplication of two input signals.

    ``out = in1 * in2``
    """

    _input_port_defs = [InputPort("in1"), InputPort("in2")]
    _output_port_defs = [OutputPort("out")]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    def compute(self, t: float) -> None:
        self.set_output("out", self.get_input("in1") * self.get_input("in2"))


# ---------------------------------------------------------------------------
# Integrator (stateful — continuous time)
# ---------------------------------------------------------------------------


class Integrator(Block):
    """Integrates the input signal over time.

    The integrator maintains an internal state ``x`` and its derivative
    is the input signal: ``dx/dt = in``.  The output is the current
    state value: ``out = x``.

    Parameters
    ----------
    x0:
        Initial value of the integrator state.
    """

    _input_port_defs = [InputPort("in")]
    _output_port_defs = [OutputPort("out")]

    def __init__(self, x0: float = 0.0, **kwargs) -> None:
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


# ---------------------------------------------------------------------------
# Derivative (approximation via finite differences)
# ---------------------------------------------------------------------------


class Derivative(Block):
    """Approximates the time derivative of the input signal.

    Uses a first-order backward difference: ``out = (in - in_prev) / dt``.

    On the first step (no previous value available), the output is 0.0.

    Parameters
    ----------
    initial:
        Initial value of the previous input (default 0.0).
    """

    _input_port_defs = [InputPort("in")]
    _output_port_defs = [OutputPort("out")]

    def __init__(self, initial: float = 0.0, **kwargs) -> None:
        super().__init__(params={"initial": initial}, **kwargs)
        self._prev_input: float = initial
        self._prev_time: float | None = None

    def compute(self, t: float) -> None:
        current = self.get_input("in")
        if self._prev_time is None:
            # First evaluation — no previous sample yet.
            self.set_output("out", 0.0)
        else:
            dt = t - self._prev_time
            if dt > 0:
                self.set_output("out", (current - self._prev_input) / dt)
            else:
                self.set_output("out", 0.0)
        self._prev_input = current
        self._prev_time = t
