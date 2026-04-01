"""Delay block: algebraic loop breaker.

The :class:`Delay` block introduces a one-step time lag by outputting
the *previous* step's input value.  This breaks algebraic loops in the
block graph, allowing topological sort to succeed.

The graph module (:mod:`blocksim.core.graph`) recognises Delay blocks
by checking for ``"Delay"`` in the class name.
"""

from __future__ import annotations

from blocksim.core.block import Block, InputPort, OutputPort


# ---------------------------------------------------------------------------
# Delay
# ---------------------------------------------------------------------------


class Delay(Block):
    """One-step delay (zero-order hold): outputs the previous step's input.

    On the first evaluation, the output is *initial*.  Subsequent evaluations
    output the value that was received at the previous time step.

    This is the primary mechanism for breaking algebraic loops.

    Parameters
    ----------
    initial:
        The value output on the first simulation step (before any input
        has been received).
    """

    _input_port_defs = [InputPort("in")]
    _output_port_defs = [OutputPort("out")]

    def __init__(self, initial: float = 0.0, **kwargs) -> None:
        super().__init__(params={"initial": initial}, **kwargs)
        self._held_value: float = initial

    def compute(self, t: float) -> None:
        """Output the held (previous step) value, then capture current input.

        The held value is output *first*, then updated with the current
        input.  This ensures a one-step delay: the current input will
        appear on the output at the *next* time step.
        """
        # 1. Output the held value from the previous step.
        self.set_output("out", self._held_value)

        # 2. Capture current input — this becomes the output next step.
        self._held_value = self.get_input("in")
