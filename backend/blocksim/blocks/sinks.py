"""Sink and utility blocks: signal recorders and displays.

Sink blocks consume signals and record or display them:
- :class:`Scope` — records the full time-series of an input signal
- :class:`Display` — stores only the last received value
"""

from __future__ import annotations

from blocksim.core.block import Block, InputPort


# ---------------------------------------------------------------------------
# Scope
# ---------------------------------------------------------------------------


class Scope(Block):
    """Records the time-series history of an input signal.

    The Scope block stores ``(time, value)`` pairs for every simulation step.
    After simulation, the recorded data is available via :attr:`history`.

    The Scope has no output ports — it is a pure sink.
    """

    _input_port_defs = [InputPort("in")]
    _output_port_defs = []  # pure sink

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.history: list[tuple[float, float]] = []

    def compute(self, t: float) -> None:
        value = self.get_input("in")
        self.history.append((t, value))

    @property
    def times(self) -> list[float]:
        """Return recorded time values."""
        return [pt[0] for pt in self.history]

    @property
    def values(self) -> list[float]:
        """Return recorded signal values."""
        return [pt[1] for pt in self.history]

    def clear(self) -> None:
        """Clear recorded history."""
        self.history.clear()


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------


class Display(Block):
    """Stores only the last received value of an input signal.

    Useful for monitoring a signal's final or current value without
    recording the full time-series.
    """

    _input_port_defs = [InputPort("in")]
    _output_port_defs = []  # pure sink

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.last_value: float | None = None
        self.last_time: float | None = None

    def compute(self, t: float) -> None:
        self.last_value = self.get_input("in")
        self.last_time = t
