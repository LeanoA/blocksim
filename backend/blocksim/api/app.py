"""FastAPI application factory for the BlockSim API.

Creates and configures the FastAPI app with:
- CORS middleware (permissive for local development)
- Error handlers for domain exceptions
- Lifespan events for startup/shutdown
- Route registration

Usage::

    from blocksim.api.app import create_app

    app = create_app()
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from blocksim.api.store import ModelNotFoundError, model_store
from blocksim.core.block import PortAlreadyConnectedError
from blocksim.core.graph import AlgebraicLoopError
from blocksim.core.system import (
    DuplicateBlockIdError,
    InvalidConnectionError,
    SimulationDivergenceError,
)
from blocksim.models.persistence import ModelFileError, SchemaVersionError


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown events."""
    # Startup: ensure the block registry is loaded.
    from blocksim.blocks.registry import registry  # noqa: F401

    yield

    # Shutdown: clear the model store.
    model_store.clear()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns
    -------
    FastAPI
        A fully configured FastAPI app with routes and error handlers.
    """
    app = FastAPI(
        title="BlockSim API",
        description="Block-diagram simulation engine — REST + WebSocket API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # -- CORS middleware (permissive for local dev) --------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -- Error handlers -----------------------------------------------------

    @app.exception_handler(ModelNotFoundError)
    async def model_not_found_handler(
        request: Request, exc: ModelNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"detail": str(exc)},
        )

    @app.exception_handler(SimulationDivergenceError)
    async def divergence_handler(
        request: Request, exc: SimulationDivergenceError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "detail": str(exc),
                "time": exc.time,
                "step": exc.step,
                "block_id": exc.block_id,
            },
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(
        request: Request, exc: ValueError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc)},
        )

    @app.exception_handler(KeyError)
    async def key_error_handler(
        request: Request, exc: KeyError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc)},
        )

    @app.exception_handler(InvalidConnectionError)
    async def invalid_connection_handler(
        request: Request, exc: InvalidConnectionError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc)},
        )

    @app.exception_handler(DuplicateBlockIdError)
    async def duplicate_block_handler(
        request: Request, exc: DuplicateBlockIdError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc)},
        )

    @app.exception_handler(AlgebraicLoopError)
    async def algebraic_loop_handler(
        request: Request, exc: AlgebraicLoopError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"detail": str(exc)},
        )

    @app.exception_handler(PortAlreadyConnectedError)
    async def port_already_connected_handler(
        request: Request, exc: PortAlreadyConnectedError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc)},
        )

    @app.exception_handler(ModelFileError)
    async def model_file_error_handler(
        request: Request, exc: ModelFileError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc), "path": exc.path},
        )

    @app.exception_handler(SchemaVersionError)
    async def schema_version_error_handler(
        request: Request, exc: SchemaVersionError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "detail": str(exc),
                "file_version": exc.file_version,
                "supported_version": exc.supported,
            },
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Catch-all handler to prevent raw stack traces in responses."""
        return JSONResponse(
            status_code=500,
            content={
                "detail": f"Internal server error: {type(exc).__name__}: {exc}",
            },
        )

    # -- Health check -------------------------------------------------------

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """Health check endpoint.

        Returns a simple status response to verify the API is running.
        """
        return {"status": "ok"}

    # -- Register routes ----------------------------------------------------

    from blocksim.api.routes import router
    from blocksim.api.ws import ws_router

    app.include_router(router, prefix="/api")
    app.include_router(ws_router)

    return app
