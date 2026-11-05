"""Block base class, Port system, Connection model, and related errors.

This module defines the foundational abstractions for BlockSim:
- Port / InputPort / OutputPort: typed connection endpoints on blocks
- Connection: a directed link between an output port and an input port
- Block: abstract base class that all simulation blocks inherit from
- PortAlreadyConnectedError: raised when connecting to an occupied input
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class PortAlreadyConnectedError(Exception):
    """Raised when attempting to connect to an input port that already has a connection."""

    def __init__(self, block_id: str, port_name: str) -> None:
        self.block_id = block_id
        self.port_name = port_name
        super().__init__(
            f"Input port '{port_name}' on block '{block_id}' is already connected. "
            "Each input port accepts exactly one connection."
        )


# ---------------------------------------------------------------------------
# Ports
# ---------------------------------------------------------------------------


class PortDirection(str, Enum):
    """Direction of a port on a block."""

    IN = "in"
    OUT = "out"


@dataclass
class Port:
    """A named, typed connection point on a :class:`Block`.

    Parameters
    ----------
    name:
        Human-readable identifier unique within the owning block.
    direction:
        Whether this is an input or output port.
    dtype:
        The value type carried through this port (``float`` for MVP).
    """

    name: str
    direction: PortDirection
    dtype: type = float

    def __repr__(self) -> str:  # pragma: no cover
        arrow = "→" if self.direction is PortDirection.IN else "←"
        return f"Port({arrow} {self.name}: {self.dtype.__name__})"


def InputPort(name: str, dtype: type = float) -> Port:
    """Convenience factory for creating an input :class:`Port`."""
    return Port(name=name, direction=PortDirection.IN, dtype=dtype)


def OutputPort(name: str, dtype: type = float) -> Port:
    """Convenience factory for creating an output :class:`Port`."""
    return Port(name=name, direction=PortDirection.OUT, dtype=dtype)


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Connection:
    """A directed link from one block's output port to another block's input port.

    Parameters
    ----------
    source_block_id:
        ID of the block that produces the value.
    source_port:
        Name of the output port on the source block.
    target_block_id:
        ID of the block that consumes the value.
    target_port:
        Name of the input port on the target block.
    """

    source_block_id: str
    source_port: str
    target_block_id: str
    target_port: str

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"Connection({self.source_block_id}.{self.source_port} "
            f"→ {self.target_block_id}.{self.target_port})"
        )


# ---------------------------------------------------------------------------
# Block Abstract Base Class
# ---------------------------------------------------------------------------


class Block(ABC):
    """Abstract base class for all simulation blocks.

    A block is a self-describing computational unit with typed input/output
    ports, optional internal state (for continuous-time dynamics), and a
    ``compute`` method that transforms inputs to outputs at each time step.

    Sub-classes **must** implement :meth:`compute`.  Stateful blocks (those
    with ``state_size > 0``) **must** also implement :meth:`initialize` and
    :meth:`derivatives`.

    Parameters
    ----------
    block_id:
        Unique identifier.  Auto-generated UUID if *None*.
    params:
        Arbitrary parameter dict supplied at construction.
    """

    # Subclasses declare these as class-level lists; each instance gets copies.
    _input_port_defs: list[Port] = []
    _output_port_defs: list[Port] = []

    def __init__(
        self,
        block_id: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> None:
        self.id: str = block_id or uuid.uuid4().hex[:12]
        self.params: dict[str, Any] = params or {}

        # Build per-instance port dicts for fast look-up.
        self.input_ports: dict[str, Port] = {
            p.name: Port(name=p.name, direction=p.direction, dtype=p.dtype)
            for p in self._input_port_defs
        }
        self.output_ports: dict[str, Port] = {
            p.name: Port(name=p.name, direction=p.direction, dtype=p.dtype)
            for p in self._output_port_defs
        }

        # Runtime value caches (populated during simulation).
        self._input_values: dict[str, float] = {
            name: 0.0 for name in self.input_ports
        }
        self._output_values: dict[str, float] = {
            name: 0.0 for name in self.output_ports
        }

        # Track which input ports have an incoming connection.
        self._connected_inputs: set[str] = set()

        # Internal state vector (empty for stateless blocks).
        self._state: np.ndarray = np.array([], dtype=np.float64)

    # -- Port helpers -------------------------------------------------------

    def get_input(self, name: str) -> float:
        """Return the current value of input port *name*."""
        return self._input_values[name]

    def set_input(self, name: str, value: float) -> None:
        """Set the current value of input port *name* (called by the engine)."""
        self._input_values[name] = value

    def get_output(self, name: str) -> float:
        """Return the current value of output port *name*."""
        return self._output_values[name]

    def set_output(self, name: str, value: float) -> None:
        """Set the current value of output port *name* (called from :meth:`compute`)."""
        self._output_values[name] = value

    def mark_input_connected(self, port_name: str) -> None:
        """Mark *port_name* as connected, raising if already occupied.

        Raises
        ------
        PortAlreadyConnectedError
            If the port already has an incoming connection.
        KeyError
            If *port_name* is not a valid input port.
        """
        if port_name not in self.input_ports:
            raise KeyError(
                f"Block '{self.id}' has no input port '{port_name}'. "
                f"Available: {list(self.input_ports.keys())}"
            )
        if port_name in self._connected_inputs:
            raise PortAlreadyConnectedError(self.id, port_name)
        self._connected_inputs.add(port_name)

    def unmark_input_connected(self, port_name: str) -> None:
        """Remove the connected mark from *port_name* (e.g. when disconnecting)."""
        self._connected_inputs.discard(port_name)

    # -- State management ---------------------------------------------------

    @property
    def state_size(self) -> int:
        """Number of continuous state variables owned by this block.

        Override in subclasses that have internal dynamics (e.g. Integrator).
        """
        return 0

    def get_state(self) -> np.ndarray:
        """Return a copy of the block's internal state vector."""
        return self._state.copy()

    def set_state(self, state: np.ndarray) -> None:
        """Replace the block's internal state vector (called by the solver)."""
        self._state = np.asarray(state, dtype=np.float64)

    # -- Abstract interface -------------------------------------------------

    @abstractmethod
    def compute(self, t: float) -> None:
        """Compute output port values from current inputs at time *t*.

        Implementations should call :meth:`set_output` for each output port.
        Input values are available via :meth:`get_input`.
        """
        ...

    def initialize(self, t0: float) -> np.ndarray:
        """Return the initial state vector at time *t0*.

        Stateful blocks (``state_size > 0``) **must** override this.
        The default implementation returns an empty array.
        """
        return np.array([], dtype=np.float64)

    def derivatives(self, t: float, state: np.ndarray) -> np.ndarray:
        """Return the time-derivative of the state vector.

        Stateful blocks **must** override this.  The default returns an
        empty array.
        """
        return np.array([], dtype=np.float64)

    # -- Introspection ------------------------------------------------------

    @property
    def block_type(self) -> str:
        """Return the class name as the block type string."""
        return type(self).__name__

    def describe(self) -> dict[str, Any]:
        """Return a JSON-serialisable description of this block."""
        return {
            "id": self.id,
            "type": self.block_type,
            "params": self.params,
            "input_ports": [
                {"name": p.name, "dtype": p.dtype.__name__}
                for p in self.input_ports.values()
            ],
            "output_ports": [
                {"name": p.name, "dtype": p.dtype.__name__}
                for p in self.output_ports.values()
            ],
            "state_size": self.state_size,
        }

    def __repr__(self) -> str:  # pragma: no cover
        ins = ", ".join(self.input_ports.keys())
        outs = ", ".join(self.output_ports.keys())
        return f"<{self.block_type}(id={self.id!r}, in=[{ins}], out=[{outs}])>"
