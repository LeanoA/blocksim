"""Source blocks: signal generators with no inputs.

Source blocks produce output signals as functions of time.  They have no
input ports and their output is determined solely by their parameters and
the current simulation time.

Blocks:
- :class:`ConstantSource` — outputs a fixed value
- :class:`StepSource` — outputs a step function at a given time
- :class:`SineSource` — outputs a sinusoidal signal
- :class:`RampSource` — outputs a linear ramp signal
"""

from __future__ import annotations

import math


from blocksim.core.block import Block, OutputPort


# ---------------------------------------------------------------------------
# ConstantSource
# ---------------------------------------------------------------------------


class ConstantSource(Block):
    """Outputs a constant value at all times.

    Parameters
    ----------
    value:
        The constant output value.
    """

    _output_port_defs = [OutputPort("out")]

    def __init__(self, value: float = 1.0, **kwargs) -> None:
        super().__init__(params={"value": value}, **kwargs)

    def compute(self, t: float) -> None:
        self.set_output("out", self.params["value"])


# ---------------------------------------------------------------------------
# StepSource
# ---------------------------------------------------------------------------


class StepSource(Block):
    """Outputs a step function: *initial* before *step_time*, *final* after.

    Parameters
    ----------
    step_time:
        The time at which the step occurs.
    initial:
        Output value before the step.
    final:
        Output value at and after the step.
    """

    _output_port_defs = [OutputPort("out")]

    def __init__(
        self,
        step_time: float = 0.0,
        initial: float = 0.0,
        final: float = 1.0,
        **kwargs,
    ) -> None:
        super().__init__(
            params={"step_time": step_time, "initial": initial, "final": final},
            **kwargs,
        )

    def compute(self, t: float) -> None:
        if t < self.params["step_time"]:
            self.set_output("out", self.params["initial"])
        else:
            self.set_output("out", self.params["final"])


# ---------------------------------------------------------------------------
# SineSource
# ---------------------------------------------------------------------------


class SineSource(Block):
    """Outputs a sinusoidal signal: ``amplitude * sin(2*pi*frequency*t + phase)``.

    Parameters
    ----------
    amplitude:
        Peak amplitude of the sine wave.
    frequency:
        Frequency in Hz.
    phase:
        Phase offset in radians.
    """

    _output_port_defs = [OutputPort("out")]

    def __init__(
        self,
        amplitude: float = 1.0,
        frequency: float = 1.0,
        phase: float = 0.0,
        **kwargs,
    ) -> None:
        super().__init__(
            params={"amplitude": amplitude, "frequency": frequency, "phase": phase},
            **kwargs,
        )

    def compute(self, t: float) -> None:
        a = self.params["amplitude"]
        f = self.params["frequency"]
        p = self.params["phase"]
        self.set_output("out", a * math.sin(2.0 * math.pi * f * t + p))


# ---------------------------------------------------------------------------
# RampSource
# ---------------------------------------------------------------------------


class RampSource(Block):
    """Outputs a linear ramp: ``slope * (t - start_time)`` after *start_time*.

    Before *start_time* the output is *initial*.

    Parameters
    ----------
    slope:
        Rate of change per second.
    start_time:
        Time at which the ramp begins.
    initial:
        Output value before the ramp starts.
    """

    _output_port_defs = [OutputPort("out")]

    def __init__(
        self,
        slope: float = 1.0,
        start_time: float = 0.0,
        initial: float = 0.0,
        **kwargs,
    ) -> None:
        super().__init__(
            params={"slope": slope, "start_time": start_time, "initial": initial},
            **kwargs,
        )

    def compute(self, t: float) -> None:
        if t < self.params["start_time"]:
            self.set_output("out", self.params["initial"])
        else:
            elapsed = t - self.params["start_time"]
            self.set_output("out", self.params["initial"] + self.params["slope"] * elapsed)
