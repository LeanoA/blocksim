"""Electrical blocks: signal-flow models of electrical components.

These blocks model electrical components using signal-flow conventions
(directed signals through ports), NOT SPICE-style nodal analysis.

For a series RLC circuit, the modeling approach is:
- The circuit current I is the primary state variable
- VoltageSource provides the driving voltage
- KVL: V_source = V_R + V_L + V_C
- The Inductor and Capacitor use internal ODE state

Blocks:
- :class:`Resistor` — V = I * R (or I = V / R)
- :class:`Inductor` — stateful: V = L * dI/dt, outputs current I
- :class:`Capacitor` — stateful: I = C * dV/dt, outputs voltage V
- :class:`VoltageSource` — outputs a voltage signal (wraps StepSource behavior)
"""

from __future__ import annotations

import numpy as np

from blocksim.core.block import Block, InputPort, OutputPort


# ---------------------------------------------------------------------------
# VoltageSource
# ---------------------------------------------------------------------------


class VoltageSource(Block):
    """Outputs a DC voltage or step voltage signal.

    Can operate in two modes:
    - DC mode: outputs a constant voltage (when step_time is not set)
    - Step mode: outputs ``initial`` before ``step_time``, ``voltage`` after

    Parameters
    ----------
    voltage:
        The output voltage value (or final value in step mode).
    step_time:
        Time at which to step from ``initial`` to ``voltage``.
        If None, outputs constant ``voltage``.
    initial:
        Voltage before step_time (only used in step mode).
    """

    _output_port_defs = [OutputPort("out")]

    def __init__(
        self,
        voltage: float = 1.0,
        step_time: float | None = None,
        initial: float = 0.0,
        **kwargs,
    ) -> None:
        super().__init__(
            params={
                "voltage": voltage,
                "step_time": step_time,
                "initial": initial,
            },
            **kwargs,
        )

    def compute(self, t: float) -> None:
        step_time = self.params["step_time"]
        if step_time is not None and t < step_time:
            self.set_output("out", self.params["initial"])
        else:
            self.set_output("out", self.params["voltage"])


# ---------------------------------------------------------------------------
# Resistor
# ---------------------------------------------------------------------------


class Resistor(Block):
    """Models a resistor using Ohm's law: V_out = I_in * R.

    In signal-flow convention:
    - Input port ``in`` receives current I
    - Output port ``out`` produces voltage drop V = I * R

    This can also be used as I = V / R by connecting voltage to input
    and using Gain(1/R) instead, but the primary convention is V = I * R.

    Parameters
    ----------
    resistance:
        Resistance in ohms (Ω). Must be positive.
    """

    _input_port_defs = [InputPort("in")]
    _output_port_defs = [OutputPort("out")]

    def __init__(self, resistance: float = 1.0, **kwargs) -> None:
        if resistance <= 0:
            raise ValueError(f"Resistance must be positive, got {resistance}")
        super().__init__(params={"resistance": resistance}, **kwargs)

    def compute(self, t: float) -> None:
        current = self.get_input("in")
        voltage = current * self.params["resistance"]
        self.set_output("out", voltage)


# ---------------------------------------------------------------------------
# Inductor
# ---------------------------------------------------------------------------


class Inductor(Block):
    """Models an inductor: V = L * dI/dt.

    The inductor is a stateful block. Its state is the current I flowing
    through it.  Given an input voltage V across the inductor:

        dI/dt = V / L

    - Input port ``in`` receives voltage across the inductor (V_L)
    - Output port ``out`` produces the current through the inductor (I)

    Parameters
    ----------
    inductance:
        Inductance in henries (H). Must be positive.
    i0:
        Initial current through the inductor (default 0.0).
    """

    _input_port_defs = [InputPort("in")]
    _output_port_defs = [OutputPort("out")]

    def __init__(
        self,
        inductance: float = 1.0,
        i0: float = 0.0,
        **kwargs,
    ) -> None:
        if inductance <= 0:
            raise ValueError(f"Inductance must be positive, got {inductance}")
        super().__init__(
            params={"inductance": inductance, "i0": i0},
            **kwargs,
        )

    @property
    def state_size(self) -> int:
        return 1

    def initialize(self, t0: float) -> np.ndarray:
        return np.array([self.params["i0"]], dtype=np.float64)

    def compute(self, t: float) -> None:
        # Output is the current (state variable)
        self.set_output("out", self._state[0])

    def derivatives(self, t: float, state: np.ndarray) -> np.ndarray:
        # dI/dt = V_L / L
        v_in = self.get_input("in")
        inductance = self.params["inductance"]
        return np.array([v_in / inductance], dtype=np.float64)


# ---------------------------------------------------------------------------
# Capacitor
# ---------------------------------------------------------------------------


class Capacitor(Block):
    """Models a capacitor: I = C * dV/dt.

    The capacitor is a stateful block. Its state is the voltage V across it.
    Given an input current I flowing into the capacitor:

        dV/dt = I / C

    - Input port ``in`` receives current into the capacitor (I)
    - Output port ``out`` produces the voltage across the capacitor (V_C)

    Parameters
    ----------
    capacitance:
        Capacitance in farads (F). Must be positive.
    v0:
        Initial voltage across the capacitor (default 0.0).
    """

    _input_port_defs = [InputPort("in")]
    _output_port_defs = [OutputPort("out")]

    def __init__(
        self,
        capacitance: float = 1e-6,
        v0: float = 0.0,
        **kwargs,
    ) -> None:
        if capacitance <= 0:
            raise ValueError(f"Capacitance must be positive, got {capacitance}")
        super().__init__(
            params={"capacitance": capacitance, "v0": v0},
            **kwargs,
        )

    @property
    def state_size(self) -> int:
        return 1

    def initialize(self, t0: float) -> np.ndarray:
        return np.array([self.params["v0"]], dtype=np.float64)

    def compute(self, t: float) -> None:
        # Output is the voltage (state variable)
        self.set_output("out", self._state[0])

    def derivatives(self, t: float, state: np.ndarray) -> np.ndarray:
        # dV/dt = I / C
        i_in = self.get_input("in")
        capacitance = self.params["capacitance"]
        return np.array([i_in / capacitance], dtype=np.float64)
