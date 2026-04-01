"""JSON model persistence: save and load simulation models to/from files.

This module provides functions to serialize :class:`ModelSchema` instances
to JSON files and deserialize them back, with schema versioning for
forward compatibility.

Usage::

    from blocksim.models.persistence import save_model, load_model

    save_model(model, "my_circuit.json")
    loaded = load_model("my_circuit.json")
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from blocksim.models.schemas import ModelSchema

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
