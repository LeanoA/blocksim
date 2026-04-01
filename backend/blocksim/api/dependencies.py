"""Shared dependencies for the BlockSim API.

Provides centralized access to shared state (model store, block registry)
as FastAPI dependency injection points.

Usage::

    from blocksim.api.dependencies import get_model_store, get_registry

    @router.get("/models")
    async def list_models(store: ModelStore = Depends(get_model_store)):
        return store.list_all()
"""

from __future__ import annotations

from blocksim.api.store import ModelStore, model_store
from blocksim.blocks.registry import BlockRegistry, registry


def get_model_store() -> ModelStore:
    """FastAPI dependency that returns the singleton model store.

    This allows routes to declare the store as a dependency, making
    testing easier (the dependency can be overridden in tests).

    Returns
    -------
    ModelStore
        The global in-memory model store instance.
    """
    return model_store


def get_registry() -> BlockRegistry:
    """FastAPI dependency that returns the singleton block registry.

    Returns
    -------
    BlockRegistry
        The global block registry instance.
    """
    return registry
