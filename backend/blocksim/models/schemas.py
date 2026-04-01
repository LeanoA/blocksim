"""Pydantic v2 models for API serialization.

These schemas define the data contracts for:
- Block and port definitions
- Connection definitions
- Model (system) definitions
- Simulation configuration
- Simulation results

All models use Pydantic v2 ``model_config`` conventions.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Port schema
# ---------------------------------------------------------------------------


class PortSchema(BaseModel):
    """Schema for a port on a block."""

    name: str
    direction: Literal["in", "out"]
    dtype: str = "float"


# ---------------------------------------------------------------------------
# Block schema
# ---------------------------------------------------------------------------


class BlockSchema(BaseModel):
    """Schema for a block definition (used in model CRUD)."""

    id: str
    type: str
    params: dict[str, Any] = Field(default_factory=dict)
    position: tuple[float, float] = (0.0, 0.0)


# ---------------------------------------------------------------------------
# Connection schema
# ---------------------------------------------------------------------------


class ConnectionSchema(BaseModel):
    """Schema for a connection between two blocks."""

    source_block: str
    source_port: str
    target_block: str
    target_port: str


# ---------------------------------------------------------------------------
# Model (system) schema
# ---------------------------------------------------------------------------


class ModelSchema(BaseModel):
    """Schema for a complete model definition (blocks + connections)."""

    name: str = "Untitled"
    blocks: list[BlockSchema] = Field(default_factory=list)
    connections: list[ConnectionSchema] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Simulation configuration
# ---------------------------------------------------------------------------


class SimulationConfigSchema(BaseModel):
    """Schema for simulation run parameters."""

    t_start: float = 0.0
    t_end: float = 1.0
    dt: float = 0.001
    solver: Literal["euler", "rk4", "scipy_rk45", "radau"] = "rk4"


# ---------------------------------------------------------------------------
# Simulation result
# ---------------------------------------------------------------------------


class SimulationResultSchema(BaseModel):
    """Schema for simulation output data."""

    time: list[float]
    signals: dict[str, list[float]]

    model_config = {"arbitrary_types_allowed": True}


# ---------------------------------------------------------------------------
# WebSocket frame (for streaming)
# ---------------------------------------------------------------------------


class SimFrameSchema(BaseModel):
    """Schema for a single WebSocket simulation frame."""

    t: float
    signals: dict[str, float]
