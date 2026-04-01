"""In-memory model store with thread-safe CRUD operations.

Provides a simple dict-backed store for simulation model definitions.
Each model is stored as a :class:`ModelSchema` with a unique string ID.

Usage::

    from blocksim.api.store import model_store

    model_id = model_store.create(model_schema)
    model = model_store.get(model_id)
    model_store.update(model_id, updated_schema)
    model_store.delete(model_id)
"""

from __future__ import annotations

import threading
import uuid

from blocksim.models.schemas import ModelSchema


class ModelNotFoundError(Exception):
    """Raised when a model ID is not found in the store."""

    def __init__(self, model_id: str) -> None:
        self.model_id = model_id
        super().__init__(f"Model '{model_id}' not found.")


class ModelStore:
    """Thread-safe in-memory store for simulation models.

    All public methods are protected by a reentrant lock so the store
    can be safely used from multiple threads (e.g. FastAPI workers).
    """

    def __init__(self) -> None:
        self._models: dict[str, ModelSchema] = {}
        self._lock = threading.RLock()

    def create(self, model: ModelSchema) -> str:
        """Store a new model and return its generated ID.

        Parameters
        ----------
        model:
            The model definition to store.

        Returns
        -------
        str
            The unique ID assigned to the model.
        """
        model_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._models[model_id] = model
        return model_id

    def get(self, model_id: str) -> ModelSchema:
        """Retrieve a model by ID.

        Raises
        ------
        ModelNotFoundError
            If the model ID does not exist.
        """
        with self._lock:
            if model_id not in self._models:
                raise ModelNotFoundError(model_id)
            return self._models[model_id]

    def update(self, model_id: str, model: ModelSchema) -> None:
        """Replace a model's definition.

        Raises
        ------
        ModelNotFoundError
            If the model ID does not exist.
        """
        with self._lock:
            if model_id not in self._models:
                raise ModelNotFoundError(model_id)
            self._models[model_id] = model

    def delete(self, model_id: str) -> None:
        """Remove a model by ID.

        Raises
        ------
        ModelNotFoundError
            If the model ID does not exist.
        """
        with self._lock:
            if model_id not in self._models:
                raise ModelNotFoundError(model_id)
            del self._models[model_id]

    def list_all(self) -> dict[str, ModelSchema]:
        """Return a copy of all stored models."""
        with self._lock:
            return dict(self._models)

    def clear(self) -> None:
        """Remove all models (useful for testing)."""
        with self._lock:
            self._models.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._models)

    def __contains__(self, model_id: str) -> bool:
        with self._lock:
            return model_id in self._models


# ---------------------------------------------------------------------------
# Singleton instance
# ---------------------------------------------------------------------------

model_store = ModelStore()
