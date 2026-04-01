"""DynamicSystem: the top-level simulation container.

A :class:`DynamicSystem` manages a collection of blocks, their connections,
and orchestrates the simulation loop:

1. ``add_block()`` — register blocks
2. ``connect()`` — wire output ports to input ports
3. ``compile()`` — topological sort, loop detection, state vector assembly
4. ``simulate()`` — run the simulation using a chosen solver
"""

from __future__ import annotations

from typing import Any

import numpy as np

from blocksim.core.block import Block, Connection, PortAlreadyConnectedError
from blocksim.core.graph import (
    AlgebraicLoopError,
    build_graph,
    topological_sort,
)
from blocksim.core.solver import (
    RK4Solver,
    SimulationResult,
    Solver,
    get_solver,
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SimulationDivergenceError(Exception):
    """Raised when the simulation detects NaN or Inf in the state vector.

    This typically indicates numerical instability due to a stiff system,
    too-large time step, or incorrect model parameters.

    Parameters
    ----------
    time:
        Simulation time at which divergence was detected.
    step:
        Step index at which divergence was detected.
    block_id:
        ID of the first block whose state diverged, or None if unknown.
    state_values:
        The divergent state vector values.
    """

    def __init__(
        self,
        time: float,
        step: int,
        block_id: str | None = None,
        state_values: np.ndarray | None = None,
    ) -> None:
        self.time = time
        self.step = step
        self.block_id = block_id
        self.state_values = state_values

        msg = f"Simulation diverged at t={time:.6g}, step={step}"
        if block_id:
            msg += f" (first divergent block: '{block_id}')"
        if state_values is not None:
            msg += f". State values: {state_values}"
        msg += ". Try reducing dt or checking model parameters."
        super().__init__(msg)


class SystemNotCompiledError(Exception):
    """Raised when simulate() is called before compile()."""

    def __init__(self) -> None:
        super().__init__(
            "System has not been compiled. Call system.compile() before simulate()."
        )


class DuplicateBlockIdError(Exception):
    """Raised when adding a block with an ID that already exists."""

    def __init__(self, block_id: str) -> None:
        self.block_id = block_id
        super().__init__(
            f"Block with ID '{block_id}' already exists in the system."
        )


class InvalidConnectionError(Exception):
    """Raised for invalid connections (bad block IDs, bad port names, etc.)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


# ---------------------------------------------------------------------------
# DynamicSystem
# ---------------------------------------------------------------------------


class DynamicSystem:
    """Top-level simulation container.

    A DynamicSystem holds blocks and connections, resolves execution order
    via topological sort, assembles a flat state vector from stateful blocks,
    and orchestrates the simulation loop.

    Example
    -------
    >>> sys = DynamicSystem()
    >>> sys.add_block(source)
    >>> sys.add_block(gain)
    >>> sys.connect("source", "out", "gain", "in")
    >>> sys.compile()
    >>> result = sys.simulate(t_span=(0, 1), dt=0.001)
    """

    def __init__(self) -> None:
        self.blocks: dict[str, Block] = {}
        self.connections: list[Connection] = []

        # Set after compile().
        self._sorted_blocks: list[Block] | None = None
        self._stateful_blocks: list[Block] = []
        self._state_slices: dict[str, tuple[int, int]] = {}
        self._total_state_size: int = 0
        self._compiled: bool = False

        # Block error tracking (populated during simulation).
        self._block_errors: dict[str, list[dict]] = {}
        self._current_step: int = 0
        self._accumulate_errors: bool = False

    # -- Block management ---------------------------------------------------

    def add_block(self, block: Block) -> None:
        """Add a block to the system.

        Parameters
        ----------
        block:
            The block instance to add.

        Raises
        ------
        DuplicateBlockIdError
            If a block with the same ID is already registered.
        """
        if block.id in self.blocks:
            raise DuplicateBlockIdError(block.id)
        self.blocks[block.id] = block
        self._compiled = False

    # -- Connection management ----------------------------------------------

    def connect(
        self,
        source_block_id: str,
        source_port: str,
        target_block_id: str,
        target_port: str,
    ) -> Connection:
        """Wire an output port to an input port.

        Parameters
        ----------
        source_block_id:
            ID of the block producing the value.
        source_port:
            Name of the output port on the source block.
        target_block_id:
            ID of the block consuming the value.
        target_port:
            Name of the input port on the target block.

        Returns
        -------
        Connection
            The newly created connection.

        Raises
        ------
        InvalidConnectionError
            If block IDs or port names are invalid.
        PortAlreadyConnectedError
            If the target input port already has a connection.
        """
        # Validate source block.
        if source_block_id not in self.blocks:
            raise InvalidConnectionError(
                f"Source block '{source_block_id}' not found in system."
            )
        src_block = self.blocks[source_block_id]

        # Validate source port.
        if source_port not in src_block.output_ports:
            raise InvalidConnectionError(
                f"Block '{source_block_id}' has no output port '{source_port}'. "
                f"Available: {list(src_block.output_ports.keys())}"
            )

        # Validate target block.
        if target_block_id not in self.blocks:
            raise InvalidConnectionError(
                f"Target block '{target_block_id}' not found in system."
            )
        tgt_block = self.blocks[target_block_id]

        # Validate target port.
        if target_port not in tgt_block.input_ports:
            raise InvalidConnectionError(
                f"Block '{target_block_id}' has no input port '{target_port}'. "
                f"Available: {list(tgt_block.input_ports.keys())}"
            )

        # Mark the input port as connected (raises PortAlreadyConnectedError if occupied).
        tgt_block.mark_input_connected(target_port)

        conn = Connection(source_block_id, source_port, target_block_id, target_port)
        self.connections.append(conn)
        self._compiled = False
        return conn

    # -- Compilation --------------------------------------------------------

    def compile(self) -> None:
        """Resolve execution order, detect loops, assemble state mapping.

        Must be called before :meth:`simulate`.

        Raises
        ------
        AlgebraicLoopError
            If the connection graph has a cycle with no Delay block.
        InvalidConnectionError
            If required input ports are not connected (validation).
        """
        # Validate that all required input ports are connected.
        self._validate_connections()

        # Build graph and sort.
        graph = build_graph(self.blocks, self.connections)
        self._sorted_blocks = topological_sort(graph, self.blocks)

        # Identify stateful blocks and build state slices.
        self._stateful_blocks = []
        self._state_slices = {}
        offset = 0
        for block in self._sorted_blocks:
            if block.state_size > 0:
                self._stateful_blocks.append(block)
                self._state_slices[block.id] = (offset, offset + block.state_size)
                offset += block.state_size
        self._total_state_size = offset

        self._compiled = True

    @property
    def sorted_blocks(self) -> list[Block]:
        """Return blocks in execution order (requires compile)."""
        if self._sorted_blocks is None:
            raise SystemNotCompiledError()
        return list(self._sorted_blocks)

    # -- Simulation ---------------------------------------------------------

    def simulate(
        self,
        t_span: tuple[float, float] = (0.0, 1.0),
        dt: float = 0.001,
        solver: Solver | str | None = None,
    ) -> SimulationResult:
        """Run the simulation.

        Parameters
        ----------
        t_span:
            ``(t_start, t_end)`` time range.
        dt:
            Fixed time step.
        solver:
            A :class:`Solver` instance or a solver name string (e.g. ``"rk4"``).
            Defaults to :class:`RK4Solver`.

        Returns
        -------
        SimulationResult
            Time array, state history, and recorded outputs.

        Raises
        ------
        SystemNotCompiledError
            If :meth:`compile` has not been called.
        """
        if not self._compiled or self._sorted_blocks is None:
            raise SystemNotCompiledError()

        # Resolve solver.
        if solver is None:
            solver_instance = RK4Solver()
        elif isinstance(solver, str):
            solver_instance = get_solver(solver)
        else:
            solver_instance = solver

        t_start, t_end = t_span
        n_steps = max(1, int(round((t_end - t_start) / dt)))

        # --- Initialize phase ---
        # Reset block error tracking for this simulation run.
        self._block_errors = {}
        self._current_step = 0
        self._accumulate_errors = False

        state = self._assemble_initial_state(t_start)

        # Pre-allocate recording arrays.
        time_record = np.zeros(n_steps + 1)
        state_record = np.zeros((n_steps + 1, self._total_state_size))
        output_records: dict[str, list[float]] = {}

        # Record initial state.
        time_record[0] = t_start
        if self._total_state_size > 0:
            state_record[0] = state.copy()

        # Propagate initial values and record outputs at t=0.
        self._distribute_state(state)
        self._accumulate_errors = True
        self._propagate_signals(t_start)
        self._accumulate_errors = False
        self._record_outputs(output_records)

        # --- Simulation loop ---
        t = t_start
        for step_idx in range(1, n_steps + 1):
            self._current_step = step_idx

            if self._total_state_size > 0:
                # Advance state using the solver.
                # Note: _accumulate_errors stays False during solver calls
                # so _propagate_signals invoked by _system_derivatives
                # won't double-count errors.
                state = solver_instance.step(
                    self._system_derivatives, t, state, dt
                )

                # Divergence guard: check for NaN or Inf.
                if not np.all(np.isfinite(state)):
                    divergent_block = self._find_divergent_block(state)
                    raise SimulationDivergenceError(
                        time=t + dt,
                        step=step_idx,
                        block_id=divergent_block,
                        state_values=state,
                    )

                self._distribute_state(state)

            t = t_start + step_idx * dt

            # Propagate signals in topological order (main loop — accumulate errors).
            self._accumulate_errors = True
            self._propagate_signals(t)
            self._accumulate_errors = False

            # Record.
            time_record[step_idx] = t
            if self._total_state_size > 0:
                state_record[step_idx] = state.copy()
            self._record_outputs(output_records)

        # --- Finalize ---
        outputs = {
            key: np.array(vals) for key, vals in output_records.items()
        }

        return SimulationResult(
            time=time_record,
            states=state_record,
            outputs=outputs,
            block_errors=self._block_errors,
        )

    # -- Internal helpers ---------------------------------------------------

    def _assemble_initial_state(self, t0: float) -> np.ndarray:
        """Collect initial states from all stateful blocks into a flat vector."""
        if self._total_state_size == 0:
            return np.array([], dtype=np.float64)

        state = np.zeros(self._total_state_size, dtype=np.float64)
        for block in self._stateful_blocks:
            s0 = block.initialize(t0)
            block.set_state(s0)
            start, end = self._state_slices[block.id]
            state[start:end] = s0
        return state

    def _distribute_state(self, state: np.ndarray) -> None:
        """Push slices of the flat state vector back to each stateful block."""
        for block in self._stateful_blocks:
            start, end = self._state_slices[block.id]
            block.set_state(state[start:end])

    def _propagate_signals(self, t: float) -> None:
        """Evaluate blocks in topological order, propagating port values.

        When ``self._accumulate_errors`` is ``True`` (main simulation loop),
        exceptions in ``block.compute(t)`` are caught: the block's outputs
        are set to ``NaN``, the error is recorded, and propagation continues.

        When ``_accumulate_errors`` is ``False`` (ODE solver sub-steps),
        exceptions propagate normally to avoid silently hiding solver
        instabilities.
        """
        assert self._sorted_blocks is not None

        for block in self._sorted_blocks:
            # Push connected inputs.
            for conn in self.connections:
                if conn.target_block_id == block.id:
                    src = self.blocks[conn.source_block_id]
                    value = src.get_output(conn.source_port)
                    block.set_input(conn.target_port, value)

            # Evaluate the block (with optional error isolation).
            if self._accumulate_errors:
                try:
                    block.compute(t)
                except Exception as exc:
                    # Set all output ports to NaN.
                    for port_name in block.output_ports:
                        block.set_output(port_name, float("nan"))

                    # Record the error.
                    error_entry = {
                        "block_id": block.id,
                        "step": self._current_step,
                        "time": t,
                        "error": str(exc),
                    }
                    if block.id not in self._block_errors:
                        self._block_errors[block.id] = []
                    self._block_errors[block.id].append(error_entry)
            else:
                block.compute(t)

    def _system_derivatives(self, t: float, state: np.ndarray) -> np.ndarray:
        """Compute the combined derivative vector for all stateful blocks.

        This is the function passed to the solver: ``f(t, y) → dy/dt``.
        """
        # Distribute state so blocks have current values.
        self._distribute_state(state)

        # Propagate signals so inputs are up to date.
        self._propagate_signals(t)

        # Collect derivatives.
        if self._total_state_size == 0:
            return np.array([], dtype=np.float64)

        dy = np.zeros(self._total_state_size, dtype=np.float64)
        for block in self._stateful_blocks:
            start, end = self._state_slices[block.id]
            dy[start:end] = block.derivatives(t, block.get_state())
        return dy

    def _record_outputs(self, records: dict[str, list[float]]) -> None:
        """Record current output port values for all blocks."""
        assert self._sorted_blocks is not None

        for block in self._sorted_blocks:
            for port_name in block.output_ports:
                key = f"{block.id}.{port_name}"
                if key not in records:
                    records[key] = []
                records[key].append(block.get_output(port_name))

    def _find_divergent_block(self, state: np.ndarray) -> str | None:
        """Identify the first stateful block whose state contains NaN/Inf.

        Parameters
        ----------
        state:
            The flat state vector.

        Returns
        -------
        str | None
            The block ID of the first divergent block, or None.
        """
        for block in self._stateful_blocks:
            start, end = self._state_slices[block.id]
            block_state = state[start:end]
            if not np.all(np.isfinite(block_state)):
                return block.id
        return None

    def _validate_connections(self) -> None:
        """Check that all non-source blocks have their input ports connected.

        Source blocks (those with no input ports) are excluded from validation.
        Blocks with unconnected input ports get a warning-level validation
        error collected and raised as an InvalidConnectionError.

        Raises
        ------
        InvalidConnectionError
            If any block has input ports that are not connected.
        """
        # Build a set of (target_block, target_port) tuples from connections.
        connected_ports: set[tuple[str, str]] = set()
        for conn in self.connections:
            connected_ports.add((conn.target_block_id, conn.target_port))

        missing: list[str] = []
        for block_id, block in self.blocks.items():
            if not block.input_ports:
                continue  # Source blocks — no inputs to validate.
            for port_name in block.input_ports:
                if (block_id, port_name) not in connected_ports:
                    missing.append(f"'{block_id}'.'{port_name}'")

        if missing:
            raise InvalidConnectionError(
                f"The following input ports are not connected: "
                f"{', '.join(missing)}. "
                f"Connect all required input ports before compiling."
            )
