"""Pydantic v2 models for API serialization.

These schemas define the data contracts for:
- Block and port definitions
- Connection definitions
- Model (system) definitions
- Simulation configuration
- Simulation results
- Export envelope (with SHA-256 checksum)
- Validation issues and results
- Block execution errors

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
# Block execution error
# ---------------------------------------------------------------------------


class BlockExecutionErrorSchema(BaseModel):
    """Record of a single block execution failure during simulation.

    Parameters
    ----------
    block_id:
        The ID of the block that failed.
    step:
        The simulation step index at which the failure occurred.
    time:
        The simulation time at which the failure occurred.
    error:
        Human-readable error message from the exception.
    """

    block_id: str
    step: int
    time: float
    error: str


# ---------------------------------------------------------------------------
# Simulation result
# ---------------------------------------------------------------------------


class SimulationResultSchema(BaseModel):
    """Schema for simulation output data."""

    time: list[float]
    signals: dict[str, list[float]]
    block_errors: dict[str, list[BlockExecutionErrorSchema]] = Field(
        default_factory=dict
    )
    status: Literal["completed", "completed_with_errors"] = "completed"

    model_config = {"arbitrary_types_allowed": True}


# ---------------------------------------------------------------------------
# WebSocket frame (for streaming)
# ---------------------------------------------------------------------------


class SimFrameSchema(BaseModel):
    """Schema for a single WebSocket simulation frame."""

    t: float
    signals: dict[str, float]


# ---------------------------------------------------------------------------
# Validation models
# ---------------------------------------------------------------------------


class ValidationIssue(BaseModel):
    """A single validation issue found during model validation.

    Parameters
    ----------
    severity:
        ``"error"`` (blocks simulation), ``"warning"`` (informational),
        or ``"info"`` (cosmetic).
    category:
        Validation level that produced this issue:
        ``"schema"``, ``"referential"``, or ``"semantic"``.
    message:
        Human-readable description of the issue.
    block_id:
        The ID of the block involved, if applicable.
    field:
        The specific field that caused the issue, if applicable.
    """

    severity: Literal["error", "warning", "info"]
    category: str
    message: str
    block_id: str | None = None
    field: str | None = None


class ValidationResult(BaseModel):
    """Aggregated result of model validation.

    ``valid`` is ``True`` when there are no ``error``-severity issues.
    Warnings and info issues do not prevent the model from being considered
    valid.
    """

    valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)
    checksum_match: bool | None = None


# ---------------------------------------------------------------------------
# Export envelope
# ---------------------------------------------------------------------------


class ExportEnvelope(BaseModel):
    """Top-level wrapper for exported model files.

    Contains metadata (version, timestamp, checksum) alongside the model
    definition itself.  The checksum is the SHA-256 hex digest of the
    canonical JSON serialization of the ``model`` field (sorted keys,
    compact separators).

    Parameters
    ----------
    schema_version:
        Version of the export envelope schema (e.g. ``"1.0.0"``).
    exported_at:
        ISO-8601 timestamp of the export.
    blocksim_version:
        Version of BlockSim that produced the export.
    checksum:
        SHA-256 hex digest of the canonical model JSON.
    model:
        The full model definition.
    """

    schema_version: str
    exported_at: str
    blocksim_version: str
    checksum: str
    model: ModelSchema
