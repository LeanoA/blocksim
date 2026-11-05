"""Tests for error UX improvements (T-5.4).

Validates that all simulation errors return descriptive, user-friendly messages
and that the API error handlers produce proper JSON responses (not raw stack traces).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from blocksim.api.app import create_app
from blocksim.api.store import model_store
from blocksim.core.graph import AlgebraicLoopError
from blocksim.core.system import (
    DynamicSystem,
    InvalidConnectionError,
    SimulationDivergenceError,
)


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    model_store.clear()
    return TestClient(app)


# ---------------------------------------------------------------------------
# Port validation tests
# ---------------------------------------------------------------------------


class TestPortValidation:
    """Validate that compile() checks all required ports are connected."""

    def test_unconnected_input_port_raises(self) -> None:
        """A block with unconnected input ports should fail validation."""
        from blocksim.blocks.math_ops import Gain
        from blocksim.blocks.sources import ConstantSource

        sys = DynamicSystem()
        sys.add_block(ConstantSource(value=1.0, block_id="src"))
        sys.add_block(Gain(k=2.0, block_id="gain1"))
        sys.add_block(Gain(k=3.0, block_id="gain2"))  # Not connected!
        sys.connect("src", "out", "gain1", "in")

        with pytest.raises(InvalidConnectionError, match="not connected"):
            sys.compile()

    def test_error_lists_missing_ports(self) -> None:
        """The error message should list which ports are missing."""
        from blocksim.blocks.math_ops import Sum
        from blocksim.blocks.sources import ConstantSource

        sys = DynamicSystem()
        sys.add_block(ConstantSource(value=1.0, block_id="src"))
        sys.add_block(Sum(block_id="sum1"))  # 2 inputs, 0 connected

        with pytest.raises(InvalidConnectionError, match="sum1") as exc_info:
            sys.compile()
        assert "in1" in str(exc_info.value)
        assert "in2" in str(exc_info.value)

    def test_fully_connected_compiles_ok(self) -> None:
        """A fully-connected model should compile without errors."""
        from blocksim.blocks.math_ops import Gain
        from blocksim.blocks.sources import ConstantSource

        sys = DynamicSystem()
        sys.add_block(ConstantSource(value=1.0, block_id="src"))
        sys.add_block(Gain(k=2.0, block_id="gain"))
        sys.connect("src", "out", "gain", "in")
        sys.compile()  # Should not raise


# ---------------------------------------------------------------------------
# API error response tests
# ---------------------------------------------------------------------------


class TestAPIErrorResponses:
    """Validate that API endpoints return structured error JSON."""

    def test_404_model_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/models/nonexistent")
        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data
        assert "nonexistent" in data["detail"]

    def test_400_invalid_block_type(self, client: TestClient) -> None:
        """Creating a model with an unknown block type should return 400."""
        model = {
            "name": "Bad Model",
            "blocks": [
                {"id": "b1", "type": "NonExistentBlock", "params": {}, "position": [0, 0]}
            ],
            "connections": [],
        }
        resp = client.post("/api/models", json=model)
        assert resp.status_code == 201  # Model creation succeeds (no validation at creation)

        model_id = resp.json()["id"]
        # But simulation should fail with a descriptive error
        resp = client.post(f"/api/simulate/{model_id}")
        assert resp.status_code == 400
        data = resp.json()
        assert "detail" in data

    def test_400_duplicate_block_in_model(self, client: TestClient) -> None:
        """Adding a duplicate block ID should return 400."""
        model = {"name": "Test", "blocks": [], "connections": []}
        resp = client.post("/api/models", json=model)
        model_id = resp.json()["id"]

        block = {"id": "b1", "type": "ConstantSource", "params": {"value": 1.0}, "position": [0, 0]}
        client.post(f"/api/models/{model_id}/blocks", json=block)
        # Second add should fail
        resp = client.post(f"/api/models/{model_id}/blocks", json=block)
        assert resp.status_code == 400
        assert "already exists" in resp.json()["detail"]

    def test_422_divergence_error(self, client: TestClient) -> None:
        """A divergent simulation should return 422 with diagnostic info."""
        # Create a system designed to overflow to Inf:
        # Integrating 1e308 with dt=1.0 will exceed float64 max (~1.8e308)
        model = {
            "name": "Divergent",
            "blocks": [
                {"id": "src", "type": "ConstantSource", "params": {"value": 1e308}, "position": [0, 0]},
                {"id": "int1", "type": "Integrator", "params": {"x0": 1e308}, "position": [100, 0]},
            ],
            "connections": [
                {"source_block": "src", "source_port": "out", "target_block": "int1", "target_port": "in"}
            ],
        }
        resp = client.post("/api/models", json=model)
        model_id = resp.json()["id"]

        # Large dt causes state to overflow to Inf
        config = {"t_start": 0, "t_end": 10.0, "dt": 1.0, "solver": "euler"}
        resp = client.post(f"/api/simulate/{model_id}", json=config)
        assert resp.status_code == 422
        data = resp.json()
        assert "detail" in data
        assert "diverg" in data["detail"].lower()

    def test_400_invalid_connection_in_model(self, client: TestClient) -> None:
        """Adding a connection to non-existent blocks should return 400."""
        model = {"name": "Test", "blocks": [], "connections": []}
        resp = client.post("/api/models", json=model)
        model_id = resp.json()["id"]

        conn = {
            "source_block": "nonexistent",
            "source_port": "out",
            "target_block": "also_nonexistent",
            "target_port": "in",
        }
        resp = client.post(f"/api/models/{model_id}/connections", json=conn)
        assert resp.status_code == 400
        assert "not found" in resp.json()["detail"]

    def test_422_algebraic_loop_error(self, client: TestClient) -> None:
        """Simulating a model with an algebraic loop should return 422."""
        model = {
            "name": "Loop",
            "blocks": [
                {"id": "g1", "type": "Gain", "params": {"k": 1.0}, "position": [0, 0]},
                {"id": "g2", "type": "Gain", "params": {"k": 1.0}, "position": [100, 0]},
            ],
            "connections": [
                {"source_block": "g1", "source_port": "out", "target_block": "g2", "target_port": "in"},
                {"source_block": "g2", "source_port": "out", "target_block": "g1", "target_port": "in"},
            ],
        }
        resp = client.post("/api/models", json=model)
        model_id = resp.json()["id"]

        resp = client.post(f"/api/simulate/{model_id}")
        assert resp.status_code == 422
        data = resp.json()
        assert "detail" in data
        assert "loop" in data["detail"].lower()

    def test_400_unconnected_ports_error(self, client: TestClient) -> None:
        """Simulating model with unconnected ports returns descriptive error."""
        model = {
            "name": "Unconnected",
            "blocks": [
                {"id": "g1", "type": "Gain", "params": {"k": 1.0}, "position": [0, 0]},
            ],
            "connections": [],
        }
        resp = client.post("/api/models", json=model)
        model_id = resp.json()["id"]

        resp = client.post(f"/api/simulate/{model_id}")
        assert resp.status_code == 400
        data = resp.json()
        assert "detail" in data
        assert "not connected" in data["detail"]


# ---------------------------------------------------------------------------
# Descriptive error message tests
# ---------------------------------------------------------------------------


class TestDescriptiveErrors:
    """Validate that domain errors contain helpful context."""

    def test_divergence_error_includes_time(self) -> None:
        err = SimulationDivergenceError(time=0.5, step=500, block_id="cap1")
        assert "t=0.5" in str(err)
        assert "step=500" in str(err)
        assert "cap1" in str(err)
        assert "reducing dt" in str(err)

    def test_algebraic_loop_error_includes_path(self) -> None:
        err = AlgebraicLoopError(cycle=["A", "B", "C"])
        msg = str(err)
        assert "A" in msg and "B" in msg and "C" in msg
        assert "Delay" in msg  # Suggests fix

    def test_invalid_connection_error_message(self) -> None:
        err = InvalidConnectionError(
            "Source block 'foo' not found in system."
        )
        assert "foo" in str(err)
        assert "not found" in str(err)
