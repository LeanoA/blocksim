"""REST API routes for BlockSim.

Endpoints:
- ``GET  /api/blocks/library`` — list all registered block types
- ``POST /api/models`` — create a new model
- ``GET  /api/models`` — list all models
- ``GET  /api/models/{model_id}`` — get a model by ID
- ``PUT  /api/models/{model_id}`` — update a model
- ``DELETE /api/models/{model_id}`` — delete a model
- ``GET  /api/models/{model_id}/export`` — export model as a downloadable JSON file
- ``POST /api/models/import`` — import a model from an uploaded JSON file
- ``POST /api/models/{model_id}/validate`` — validate an existing model
- ``POST /api/simulate/{model_id}`` — run a simulation synchronously
"""

from __future__ import annotations

import json
import re
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel as PydanticBaseModel

from blocksim.api.store import ModelNotFoundError, model_store
from blocksim.blocks.registry import registry
from blocksim.core.block import Block, PortAlreadyConnectedError
from blocksim.core.graph import AlgebraicLoopError
from blocksim.core.system import (
    DuplicateBlockIdError,
    DynamicSystem,
    InvalidConnectionError,
    SimulationDivergenceError,
    SystemNotCompiledError,
)
from blocksim.models.persistence import (
    ModelFileError,
    SchemaVersionError,
    build_export_envelope,
    parse_import_file,
    load_model as load_model_from_file,
    save_model as save_model_to_file,
)
from blocksim.models.schemas import (
    BlockExecutionErrorSchema,
    BlockSchema,
    ConnectionSchema,
    ModelSchema,
    SimulationConfigSchema,
    SimulationResultSchema,
    ValidationIssue,
    ValidationResult,
)
from blocksim.models.validator import ModelValidator

router = APIRouter()

# Maximum upload size for model import (10 MB).
_MAX_IMPORT_SIZE = 10 * 1024 * 1024


def _sanitize_filename(name: str) -> str:
    """Sanitize a model name for use in a download filename.

    Replaces any character that is not alphanumeric, hyphen, or underscore
    with an underscore.

    Parameters
    ----------
    name:
        The raw model name string.

    Returns
    -------
    str
        A safe filename component (e.g. ``"My_Circuit_v2_"``).
    """
    return re.sub(r"[^a-zA-Z0-9_-]", "_", name)


# ---------------------------------------------------------------------------
# Block library
# ---------------------------------------------------------------------------


@router.get("/blocks/library")
async def list_blocks() -> dict[str, Any]:
    """Return all registered block types with their metadata.

    Each block type includes its port definitions and default parameters.
    """
    blocks = []
    for name in registry.list_all():
        cls = registry.get(name)
        # Instantiate a temporary block to introspect ports.
        try:
            instance = cls(block_id="__introspect__")
            info = instance.describe()
            # Remove the introspection ID.
            info.pop("id", None)
            info["type"] = name
        except Exception:
            info = {"type": name, "error": "Could not introspect block"}
        blocks.append(info)

    return {"blocks": blocks}


# ---------------------------------------------------------------------------
# Model CRUD
# ---------------------------------------------------------------------------


@router.post("/models", status_code=201)
async def create_model(model: ModelSchema) -> dict[str, Any]:
    """Create a new simulation model.

    Returns the generated ID along with the model definition.
    """
    model_id = model_store.create(model)
    return {"id": model_id, "model": model.model_dump()}


@router.get("/models")
async def list_models() -> dict[str, Any]:
    """List all stored models."""
    all_models = model_store.list_all()
    return {
        "models": [
            {"id": mid, "model": m.model_dump()}
            for mid, m in all_models.items()
        ]
    }


@router.get("/models/{model_id}")
async def get_model(model_id: str) -> dict[str, Any]:
    """Retrieve a model by ID.

    Raises 404 if the model is not found.
    """
    model = model_store.get(model_id)
    return {"id": model_id, "model": model.model_dump()}


@router.put("/models/{model_id}")
async def update_model(model_id: str, model: ModelSchema) -> dict[str, Any]:
    """Replace a model's definition.

    Raises 404 if the model is not found.
    """
    model_store.update(model_id, model)
    return {"id": model_id, "model": model.model_dump()}


@router.delete("/models/{model_id}", status_code=204)
async def delete_model(model_id: str) -> None:
    """Delete a model by ID.

    Raises 404 if the model is not found.
    """
    model_store.delete(model_id)


# ---------------------------------------------------------------------------
# Model sub-resources: blocks and connections
# ---------------------------------------------------------------------------


@router.post("/models/{model_id}/blocks", status_code=201)
async def add_block_to_model(model_id: str, block: BlockSchema) -> dict[str, Any]:
    """Add a block to an existing model.

    Parameters
    ----------
    model_id:
        The ID of the model to modify.
    block:
        The block definition to add.

    Returns
    -------
    dict
        The updated model with the new block included.

    Raises
    ------
    ModelNotFoundError (404)
        If the model ID does not exist.
    ValueError (400)
        If a block with the same ID already exists in the model.
    """
    model = model_store.get(model_id)

    # Check for duplicate block ID.
    existing_ids = {b.id for b in model.blocks}
    if block.id in existing_ids:
        raise ValueError(
            f"Block with ID '{block.id}' already exists in model '{model_id}'."
        )

    updated = model.model_copy(
        update={"blocks": [*model.blocks, block]}
    )
    model_store.update(model_id, updated)
    return {"id": model_id, "model": updated.model_dump()}


@router.delete("/models/{model_id}/blocks/{block_id}", status_code=200)
async def remove_block_from_model(
    model_id: str, block_id: str
) -> dict[str, Any]:
    """Remove a block from a model and any connections referencing it.

    Parameters
    ----------
    model_id:
        The ID of the model to modify.
    block_id:
        The ID of the block to remove.

    Returns
    -------
    dict
        The updated model without the removed block.

    Raises
    ------
    ModelNotFoundError (404)
        If the model ID does not exist.
    ValueError (400)
        If the block ID is not found in the model.
    """
    model = model_store.get(model_id)

    # Find and remove the block.
    new_blocks = [b for b in model.blocks if b.id != block_id]
    if len(new_blocks) == len(model.blocks):
        raise ValueError(
            f"Block '{block_id}' not found in model '{model_id}'."
        )

    # Also remove any connections referencing this block.
    new_conns = [
        c for c in model.connections
        if c.source_block != block_id and c.target_block != block_id
    ]

    updated = model.model_copy(
        update={"blocks": new_blocks, "connections": new_conns}
    )
    model_store.update(model_id, updated)
    return {"id": model_id, "model": updated.model_dump()}


@router.post("/models/{model_id}/connections", status_code=201)
async def add_connection_to_model(
    model_id: str, connection: ConnectionSchema
) -> dict[str, Any]:
    """Add a connection to an existing model.

    Parameters
    ----------
    model_id:
        The ID of the model to modify.
    connection:
        The connection definition to add.

    Returns
    -------
    dict
        The updated model with the new connection included.

    Raises
    ------
    ModelNotFoundError (404)
        If the model ID does not exist.
    ValueError (400)
        If the connection references blocks not in the model, or if the
        target port already has a connection.
    """
    model = model_store.get(model_id)

    # Validate that referenced blocks exist in the model.
    block_ids = {b.id for b in model.blocks}
    if connection.source_block not in block_ids:
        raise ValueError(
            f"Source block '{connection.source_block}' not found in model."
        )
    if connection.target_block not in block_ids:
        raise ValueError(
            f"Target block '{connection.target_block}' not found in model."
        )

    # Check that the target port isn't already connected.
    for existing in model.connections:
        if (
            existing.target_block == connection.target_block
            and existing.target_port == connection.target_port
        ):
            raise ValueError(
                f"Target port '{connection.target_port}' on block "
                f"'{connection.target_block}' is already connected."
            )

    updated = model.model_copy(
        update={"connections": [*model.connections, connection]}
    )
    model_store.update(model_id, updated)
    return {"id": model_id, "model": updated.model_dump()}


@router.delete("/models/{model_id}/connections", status_code=200)
async def remove_connection_from_model(
    model_id: str, connection: ConnectionSchema
) -> dict[str, Any]:
    """Remove a specific connection from a model.

    The connection must match all four fields (source_block, source_port,
    target_block, target_port) exactly.

    Parameters
    ----------
    model_id:
        The ID of the model to modify.
    connection:
        The connection definition to remove.

    Returns
    -------
    dict
        The updated model without the removed connection.

    Raises
    ------
    ModelNotFoundError (404)
        If the model ID does not exist.
    ValueError (400)
        If the connection is not found in the model.
    """
    model = model_store.get(model_id)

    new_conns = [
        c for c in model.connections
        if not (
            c.source_block == connection.source_block
            and c.source_port == connection.source_port
            and c.target_block == connection.target_block
            and c.target_port == connection.target_port
        )
    ]

    if len(new_conns) == len(model.connections):
        raise ValueError(
            f"Connection {connection.source_block}.{connection.source_port} → "
            f"{connection.target_block}.{connection.target_port} not found in model."
        )

    updated = model.model_copy(update={"connections": new_conns})
    model_store.update(model_id, updated)
    return {"id": model_id, "model": updated.model_dump()}


# ---------------------------------------------------------------------------
# Model persistence (save/load to JSON files)
# ---------------------------------------------------------------------------


class SaveModelRequest(PydanticBaseModel):
    """Request body for saving a model to a JSON file."""

    path: str


class LoadModelRequest(PydanticBaseModel):
    """Request body for loading a model from a JSON file."""

    path: str


@router.post("/models/{model_id}/save")
async def save_model(model_id: str, request: SaveModelRequest) -> dict[str, Any]:
    """Save a stored model to a JSON file on disk.

    Parameters
    ----------
    model_id:
        The ID of the model to save.
    request:
        Contains the file path to write to.

    Returns
    -------
    dict
        Confirmation with the resolved file path.
    """
    model = model_store.get(model_id)
    try:
        resolved = save_model_to_file(model, request.path)
    except OSError as exc:
        raise ValueError(f"Cannot save model: {exc}") from exc
    return {"id": model_id, "path": str(resolved)}


@router.post("/models/load")
async def load_model(request: LoadModelRequest) -> dict[str, Any]:
    """Load a model from a JSON file and store it.

    Parameters
    ----------
    request:
        Contains the file path to read from.

    Returns
    -------
    dict
        The generated model ID and loaded model definition.
    """
    try:
        model = load_model_from_file(request.path)
    except (ModelFileError, SchemaVersionError) as exc:
        raise ValueError(str(exc)) from exc
    model_id = model_store.create(model)
    return {"id": model_id, "model": model.model_dump()}


# ---------------------------------------------------------------------------
# Export / Import / Validate
# ---------------------------------------------------------------------------


@router.get("/models/{model_id}/export")
async def export_model(model_id: str) -> StreamingResponse:
    """Export a stored model as a downloadable JSON file.

    Returns a ``StreamingResponse`` with ``Content-Disposition: attachment``
    so the browser triggers a file download.  The file includes an
    :class:`ExportEnvelope` with a SHA-256 checksum.

    Parameters
    ----------
    model_id:
        The ID of the model to export.

    Returns
    -------
    StreamingResponse
        JSON file download.

    Raises
    ------
    ModelNotFoundError (404)
        If the model ID is not found.
    """
    model = model_store.get(model_id)
    envelope = build_export_envelope(model)
    envelope_json = json.dumps(
        envelope.model_dump(), indent=2, ensure_ascii=False
    )

    safe_name = _sanitize_filename(model.name)
    filename = f"{safe_name}.blocksim.json"

    return StreamingResponse(
        iter([envelope_json]),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.post("/models/import", status_code=201)
async def import_model(file: UploadFile) -> dict[str, Any]:
    """Import a model from an uploaded JSON file.

    Accepts a multipart file upload, parses the JSON, verifies the
    checksum (if present), runs 3-level validation, stores the model,
    and returns the model together with the validation result.

    Parameters
    ----------
    file:
        The uploaded ``.blocksim.json`` file.

    Returns
    -------
    dict
        ``{id, model, validation}`` — the stored model ID, the model
        definition, and the validation result (including checksum info).

    Raises
    ------
    ValueError (400)
        If the file is not valid JSON or is missing the ``model`` key.
    HTTPException (413)
        If the file exceeds the 10 MB limit.
    """
    # Read file content with size check.
    file_bytes = await file.read()
    if len(file_bytes) > _MAX_IMPORT_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File too large. Maximum size is 10 MB.",
        )

    # Parse the file and check checksum.
    try:
        data, checksum_match = parse_import_file(file_bytes)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    # Run 3-level validation on the model data.
    model_data = data.get("model", data)
    validator = ModelValidator(registry)
    parsed_model, validation = validator.validate(model_data)

    # Add checksum info to the validation result.
    validation.checksum_match = checksum_match
    if checksum_match is False:
        validation.issues.append(
            ValidationIssue(
                severity="warning",
                category="checksum",
                message="Checksum mismatch: the file's checksum does not match "
                "the recomputed checksum of the model data. The file may "
                "have been modified.",
            )
        )

    # Store the model — even if validation found errors (REQ-IMP-3).
    if parsed_model is not None:
        model_to_store = parsed_model
    else:
        # Schema validation failed — try to store what we can.
        try:
            model_to_store = ModelSchema.model_validate(model_data)
        except Exception:
            # Fall back: store with defaults + whatever we have.
            model_to_store = ModelSchema(
                name=model_data.get("name", "Imported (invalid)"),
            )

    model_id = model_store.create(model_to_store)
    return {
        "id": model_id,
        "model": model_to_store.model_dump(),
        "validation": validation.model_dump(),
    }


@router.post("/models/{model_id}/validate")
async def validate_model(model_id: str) -> dict[str, Any]:
    """Run 3-level validation on an existing stored model.

    Parameters
    ----------
    model_id:
        The ID of the model to validate.

    Returns
    -------
    dict
        ``{validation: ValidationResult}`` with all issues found.

    Raises
    ------
    ModelNotFoundError (404)
        If the model ID is not found.
    """
    model = model_store.get(model_id)
    validator = ModelValidator(registry)
    _, validation = validator.validate(model.model_dump())
    return {"validation": validation.model_dump()}


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------


def _build_system(model: ModelSchema) -> DynamicSystem:
    """Construct a DynamicSystem from a ModelSchema.

    Creates block instances from the registry, wires connections,
    and compiles the system for simulation.

    Parameters
    ----------
    model:
        The model definition with blocks and connections.

    Returns
    -------
    DynamicSystem
        A compiled system ready for simulation.

    Raises
    ------
    KeyError
        If a block type is not found in the registry.
    InvalidConnectionError
        If a connection references invalid blocks or ports.
    AlgebraicLoopError
        If the system has unresolvable algebraic loops.
    """
    system = DynamicSystem()

    # Create blocks.
    for block_def in model.blocks:
        block_cls = registry.get(block_def.type)
        block = block_cls(block_id=block_def.id, **block_def.params)
        system.add_block(block)

    # Wire connections.
    for conn in model.connections:
        system.connect(
            conn.source_block,
            conn.source_port,
            conn.target_block,
            conn.target_port,
        )

    # Compile (topological sort, loop detection).
    system.compile()
    return system


@router.post("/simulate/{model_id}")
async def simulate(
    model_id: str,
    config: SimulationConfigSchema | None = None,
) -> SimulationResultSchema:
    """Run a simulation on a stored model and return the results.

    Parameters
    ----------
    model_id:
        The ID of the model to simulate.
    config:
        Optional simulation configuration. Defaults to RK4, dt=0.001, t_end=1.0.

    Returns
    -------
    SimulationResultSchema
        Time array and signal data for all block outputs.

    Raises
    ------
    ModelNotFoundError (404)
        If the model ID is not found.
    ValueError (400)
        If the model has invalid block types or connection issues.
    SimulationDivergenceError (422)
        If the simulation diverges (NaN/Inf detected).
    """
    if config is None:
        config = SimulationConfigSchema()

    model = model_store.get(model_id)
    system = _build_system(model)

    result = system.simulate(
        t_span=(config.t_start, config.t_end),
        dt=config.dt,
        solver=config.solver,
    )

    # Convert numpy arrays to lists for JSON serialization.
    # Build block_errors as schema objects.
    block_errors_schema: dict[str, list[BlockExecutionErrorSchema]] = {}
    for block_id, errors in result.block_errors.items():
        block_errors_schema[block_id] = [
            BlockExecutionErrorSchema(
                block_id=err["block_id"],
                step=err["step"],
                time=err["time"],
                error=err["error"],
            )
            for err in errors
        ]

    status = (
        "completed_with_errors" if block_errors_schema else "completed"
    )

    return SimulationResultSchema(
        time=result.time.tolist(),
        signals={
            key: values.tolist()
            for key, values in result.outputs.items()
        },
        block_errors=block_errors_schema,
        status=status,
    )
