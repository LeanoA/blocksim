"""REST and WebSocket API layer.

Usage::

    from blocksim.api.app import create_app

    app = create_app()
"""

from blocksim.api.app import create_app
from blocksim.api.dependencies import get_model_store, get_registry
from blocksim.api.store import ModelNotFoundError, ModelStore, model_store

__all__ = [
    "create_app",
    "get_model_store",
    "get_registry",
    "ModelNotFoundError",
    "ModelStore",
    "model_store",
]
