"""WebSocket endpoint for real-time simulation streaming.

The client connects to ``/ws/simulate/{model_id}`` and sends a JSON message
to start the simulation.  The server streams ``SimFrame`` objects back and
finally sends a ``complete`` or ``error`` status message.

Protocol::

    Client → Server: {"action": "start", "config": {solver, dt, t_end, ...}}
    Server → Client: {"type": "frame", "data": {"t": 0.001, "signals": {...}}}
    Server → Client: {"type": "frame", "data": {"t": 0.002, "signals": {...}}}
    ...
    Server → Client: {"type": "complete", "summary": {"steps": N, "t_end": ...}}
    OR
    Server → Client: {"type": "error", "message": "..."}
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from blocksim.api.routes import _build_system
from blocksim.api.store import ModelNotFoundError, model_store
from blocksim.core.solver import RK4Solver, get_solver
from blocksim.core.system import SimulationDivergenceError
from blocksim.models.schemas import SimulationConfigSchema

ws_router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Maximum number of simulation steps between yielding to the event loop.
# This keeps the WebSocket responsive even during long simulations.
_STEPS_PER_YIELD = 100

# Minimum interval (in steps) between streamed frames.
# For a simulation with dt=1e-5 and 100k steps, we don't want 100k frames.
# Instead, we down-sample to roughly 1 frame per `_FRAME_INTERVAL_STEPS`.
_DEFAULT_FRAME_SKIP = 10


def _parse_config(data: dict[str, Any]) -> SimulationConfigSchema:
    """Extract simulation config from the WebSocket message."""
    config_data = data.get("config", {})
    return SimulationConfigSchema(**config_data)


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------


@ws_router.websocket("/ws/simulate/{model_id}")
async def ws_simulate(websocket: WebSocket, model_id: str) -> None:
    """Stream simulation results over WebSocket.

    After accepting the connection, waits for a ``{"action": "start", ...}``
    message, then runs the simulation step-by-step, streaming frames to the
    client.  Supports ``{"action": "stop"}`` to abort early.
    """
    await websocket.accept()

    try:
        # Wait for start command.
        start_msg = await websocket.receive_json()

        action = start_msg.get("action", "start")
        if action != "start":
            await websocket.send_json(
                {"type": "error", "message": f"Expected action 'start', got '{action}'"}
            )
            await websocket.close()
            return

        config = _parse_config(start_msg)

        # Validate model exists.
        try:
            model = model_store.get(model_id)
        except ModelNotFoundError as exc:
            await websocket.send_json(
                {"type": "error", "message": str(exc)}
            )
            await websocket.close()
            return

        # Build and compile system.
        try:
            system = _build_system(model)
        except Exception as exc:
            await websocket.send_json(
                {"type": "error", "message": f"Build error: {exc}"}
            )
            await websocket.close()
            return

        # Run simulation with streaming.
        await _stream_simulation(websocket, system, config)

    except WebSocketDisconnect:
        pass  # Client disconnected — nothing to do.
    except Exception as exc:
        try:
            await websocket.send_json(
                {"type": "error", "message": f"Unexpected error: {exc}"}
            )
            await websocket.close()
        except Exception:
            pass  # Connection already closed.


async def _stream_simulation(
    websocket: WebSocket,
    system: "DynamicSystem",
    config: SimulationConfigSchema,
) -> None:
    """Execute the simulation loop, streaming frames over the WebSocket.

    This performs the same simulation as ``DynamicSystem.simulate()`` but
    yields control to the event loop periodically and streams output frames.
    """
    from blocksim.core.solver import RK4Solver, get_solver

    # Resolve solver.
    if config.solver:
        solver = get_solver(config.solver)
    else:
        solver = RK4Solver()

    t_start = config.t_start
    t_end = config.t_end
    dt = config.dt
    n_steps = max(1, int(round((t_end - t_start) / dt)))

    # Compute frame skip based on total steps (aim for ~500-1000 frames max).
    frame_skip = max(1, n_steps // 1000)

    # Initialize.
    state = system._assemble_initial_state(t_start)
    system._distribute_state(state)
    system._propagate_signals(t_start)

    # Send initial frame.
    signals = _collect_signals(system)
    await websocket.send_json(
        {"type": "frame", "data": {"t": t_start, "signals": signals}}
    )

    # Simulation loop.
    t = t_start
    stopped = False

    for step_idx in range(1, n_steps + 1):
        # Check for stop command (non-blocking).
        try:
            msg = await asyncio.wait_for(
                websocket.receive_json(), timeout=0.0
            )
            if msg.get("action") == "stop":
                stopped = True
                break
        except (asyncio.TimeoutError, WebSocketDisconnect):
            pass

        # Advance state.
        if system._total_state_size > 0:
            state = solver.step(
                system._system_derivatives, t, state, dt
            )

            # Divergence guard.
            if not np.all(np.isfinite(state)):
                divergent_block = system._find_divergent_block(state)
                await websocket.send_json({
                    "type": "error",
                    "message": (
                        f"Simulation diverged at t={t + dt:.6g}, step={step_idx}"
                        + (f" (block: '{divergent_block}')" if divergent_block else "")
                    ),
                })
                await websocket.close()
                return

            system._distribute_state(state)

        t = t_start + step_idx * dt
        system._propagate_signals(t)

        # Stream frame at intervals.
        if step_idx % frame_skip == 0 or step_idx == n_steps:
            signals = _collect_signals(system)
            await websocket.send_json(
                {"type": "frame", "data": {"t": round(t, 10), "signals": signals}}
            )

        # Yield to event loop periodically for responsiveness.
        if step_idx % _STEPS_PER_YIELD == 0:
            await asyncio.sleep(0)

    # Send completion message.
    status = "stopped" if stopped else "complete"
    await websocket.send_json({
        "type": status,
        "summary": {
            "steps": step_idx if stopped else n_steps,
            "t_end": round(t, 10),
            "solver": config.solver,
        },
    })
    await websocket.close()


def _collect_signals(system: "DynamicSystem") -> dict[str, float]:
    """Collect current output values from all blocks.

    Returns a flat dict mapping ``"block_id.port_name"`` to current float values.
    """
    signals: dict[str, float] = {}
    assert system._sorted_blocks is not None
    for block in system._sorted_blocks:
        for port_name in block.output_ports:
            key = f"{block.id}.{port_name}"
            signals[key] = float(block.get_output(port_name))
    return signals
