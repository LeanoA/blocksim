"""JSON model persistence: save and load simulation models to/from files.

This module provides functions to serialize :class:`ModelSchema` instances
to JSON files and deserialize them back, with schema versioning for
forward compatibility.

It also provides export envelope building (with SHA-256 checksum) and
import parsing with checksum verification.

Usage::

    from blocksim.models.persistence import save_model, load_model

    save_model(model, "my_circuit.json")
    loaded = load_model("my_circuit.json")

    # Export envelope
    from blocksim.models.persistence import build_export_envelope
    envelope = build_export_envelope(model)

    # Import parsing
    from blocksim.models.persistence import parse_import_file
    data, checksum_match = parse_import_file(file_bytes)
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import blocksim
from blocksim.models.schemas import ExportEnvelope, ModelSchema

# Current schema version — bump when the JSON structure changes.
SCHEMA_VERSION = "1.0.0"


class ModelFileError(Exception):
    """Raised when a model file cannot be read or parsed."""

    def __init__(self, path: str, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"Failed to load model from '{path}': {reason}")


class SchemaVersionError(Exception):
    """Raised when a model file has an unsupported schema version."""

    def __init__(self, path: str, file_version: str, supported: str) -> None:
        self.path = path
        self.file_version = file_version
        self.supported = supported
        super().__init__(
            f"Model file '{path}' has schema version '{file_version}', "
            f"but this version of BlockSim supports up to '{supported}'. "
            "Please upgrade BlockSim to open this file."
        )


def save_model(model: ModelSchema, path: str | Path) -> Path:
    """Serialize a model to a JSON file.

    The output file includes a ``schema_version`` field for forward
    compatibility, plus the full model definition.

    Parameters
    ----------
    model:
        The model to save.
    path:
        File path (string or Path). Parent directories are created
        automatically if they don't exist.

    Returns
    -------
    Path
        The resolved path to the written file.

    Raises
    ------
    OSError
        If the file cannot be written.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    envelope: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "model": model.model_dump(),
    }

    path.write_text(
        json.dumps(envelope, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path.resolve()


def load_model(path: str | Path) -> ModelSchema:
    """Deserialize a model from a JSON file.

    Validates the schema version and parses the model definition.

    Parameters
    ----------
    path:
        File path to a BlockSim model JSON file.

    Returns
    -------
    ModelSchema
        The deserialized model.

    Raises
    ------
    ModelFileError
        If the file does not exist, is not valid JSON, or is missing
        required fields.
    SchemaVersionError
        If the file's schema version is newer than what this version
        of BlockSim supports.
    """
    path = Path(path)

    if not path.exists():
        raise ModelFileError(str(path), "File does not exist.")

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ModelFileError(str(path), f"Cannot read file: {exc}") from exc

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ModelFileError(str(path), f"Invalid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ModelFileError(str(path), "Expected a JSON object at top level.")

    # --- Version check ---
    file_version = data.get("schema_version", "0.0.0")
    if not _is_version_compatible(file_version, SCHEMA_VERSION):
        raise SchemaVersionError(str(path), file_version, SCHEMA_VERSION)

    # --- Parse model ---
    model_data = data.get("model")
    if model_data is None:
        raise ModelFileError(str(path), "Missing 'model' key in JSON envelope.")

    try:
        return ModelSchema.model_validate(model_data)
    except Exception as exc:
        raise ModelFileError(
            str(path), f"Invalid model data: {exc}"
        ) from exc


def _is_version_compatible(file_version: str, supported_version: str) -> bool:
    """Check if *file_version* is compatible with *supported_version*.

    We use simple major-version compatibility: a file is compatible if
    its major version is less than or equal to the supported major version.

    Parameters
    ----------
    file_version:
        The version string from the file (e.g. "1.0.0").
    supported_version:
        The maximum supported version (e.g. "1.0.0").

    Returns
    -------
    bool
        True if compatible.
    """
    try:
        file_major = int(file_version.split(".")[0])
        supported_major = int(supported_version.split(".")[0])
    except (ValueError, IndexError):
        # If version strings are malformed, be permissive.
        return True

    return file_major <= supported_major


# ---------------------------------------------------------------------------
# Checksum computation
# ---------------------------------------------------------------------------


def compute_checksum(model_dict: dict[str, Any]) -> str:
    """Compute the SHA-256 hex digest of the canonical JSON of *model_dict*.

    Canonical JSON uses sorted keys and compact separators
    (``separators=(',', ':')``), producing a deterministic string regardless
    of key insertion order or formatting.

    Parameters
    ----------
    model_dict:
        The model data dictionary (typically from ``ModelSchema.model_dump()``).

    Returns
    -------
    str
        Lowercase hex SHA-256 digest.
    """
    canonical = json.dumps(
        model_dict, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Export envelope
# ---------------------------------------------------------------------------


def build_export_envelope(model: ModelSchema) -> ExportEnvelope:
    """Build an :class:`ExportEnvelope` for the given model.

    The envelope includes the schema version, the current ISO-8601 timestamp,
    the BlockSim version, a SHA-256 checksum of the model data, and the
    model itself.

    Parameters
    ----------
    model:
        The model to export.

    Returns
    -------
    ExportEnvelope
        The fully populated export envelope.
    """
    model_dict = model.model_dump()
    checksum = compute_checksum(model_dict)

    return ExportEnvelope(
        schema_version=SCHEMA_VERSION,
        exported_at=datetime.now(timezone.utc).isoformat(),
        blocksim_version=blocksim.__version__,
        checksum=checksum,
        model=model,
    )


# ---------------------------------------------------------------------------
# Import parsing
# ---------------------------------------------------------------------------


def parse_import_file(file_bytes: bytes) -> tuple[dict[str, Any], bool | None]:
    """Parse an imported model file and verify its checksum.

    Accepts raw file bytes, parses JSON, and compares the embedded
    ``checksum`` field (if present) against the recomputed SHA-256 of
    the ``model`` data.

    Parameters
    ----------
    file_bytes:
        Raw bytes of the uploaded JSON file.

    Returns
    -------
    tuple[dict, bool | None]
        A tuple of ``(parsed_data, checksum_match)`` where:
        - ``parsed_data`` is the top-level JSON object (dict)
        - ``checksum_match`` is ``True`` if the checksum matches,
          ``False`` if it doesn't, or ``None`` if no checksum was present
          in the file (legacy format).

    Raises
    ------
    json.JSONDecodeError
        If the file content is not valid JSON.
    ValueError
        If the top-level JSON is not a dict or is missing the ``model`` key.
    """
    data = json.loads(file_bytes)

    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object at top level.")

    model_data = data.get("model")
    if model_data is None:
        raise ValueError("Missing 'model' key in JSON data.")

    # Check the checksum if present.
    stored_checksum = data.get("checksum")
    if stored_checksum is None:
        checksum_match = None
    else:
        computed = compute_checksum(model_data)
        checksum_match = computed == stored_checksum

    return data, checksum_match
