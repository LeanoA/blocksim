"""Tests for the BlockSim REST and WebSocket API.

Covers:
- Block library endpoint
- Model CRUD (create, read, list, update, delete)
- Simulation endpoint (sync)
- WebSocket simulation streaming
- Error handling (404, 400, 422)
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from blocksim.api.app import create_app
from blocksim.api.store import model_store


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def app():
    """Create a fresh app for each test."""
    return create_app()


@pytest.fixture()
def client(app):
    """Synchronous test client with clean model store."""
    model_store.clear()
    with TestClient(app) as c:
        yield c
    model_store.clear()


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------


def _constant_to_gain_model() -> dict:
    """A simple model: ConstantSource(value=5) → Gain(k=2) → Scope."""
    return {
        "name": "Constant to Gain",
        "blocks": [
            {"id": "src", "type": "ConstantSource", "params": {"value": 5.0}, "position": [0, 0]},
            {"id": "gain", "type": "Gain", "params": {"k": 2.0}, "position": [100, 0]},
            {"id": "scope", "type": "Scope", "params": {}, "position": [200, 0]},
        ],
        "connections": [
            {"source_block": "src", "source_port": "out", "target_block": "gain", "target_port": "in"},
            {"source_block": "gain", "source_port": "out", "target_block": "scope", "target_port": "in"},
        ],
    }


def _integrator_model() -> dict:
    """ConstantSource(1.0) → Integrator(x0=0) — output grows linearly."""
    return {
        "name": "Integrator Test",
        "blocks": [
            {"id": "src", "type": "ConstantSource", "params": {"value": 1.0}, "position": [0, 0]},
            {"id": "integ", "type": "Integrator", "params": {"x0": 0.0}, "position": [100, 0]},
        ],
        "connections": [
            {"source_block": "src", "source_port": "out", "target_block": "integ", "target_port": "in"},
        ],
    }


# ===========================================================================
# Health Check
# ===========================================================================


class TestHealthCheck:
    """Tests for GET /health."""

    def test_health_check(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


# ===========================================================================
# Block Library
# ===========================================================================


class TestBlockLibrary:
    """Tests for GET /api/blocks/library."""

    def test_list_blocks(self, client):
        resp = client.get("/api/blocks/library")
        assert resp.status_code == 200
        data = resp.json()
        assert "blocks" in data
        blocks = data["blocks"]
        assert len(blocks) >= 16  # 12 original + 4 electrical

    def test_block_metadata_contains_ports(self, client):
        resp = client.get("/api/blocks/library")
        blocks = resp.json()["blocks"]
        # Find ConstantSource.
        constant = next(b for b in blocks if b["type"] == "ConstantSource")
        assert "output_ports" in constant
        assert any(p["name"] == "out" for p in constant["output_ports"])

    def test_block_metadata_contains_state_size(self, client):
        resp = client.get("/api/blocks/library")
        blocks = resp.json()["blocks"]
        # Find Integrator — should have state_size=1.
        integ = next(b for b in blocks if b["type"] == "Integrator")
        assert integ["state_size"] == 1

    def test_electrical_blocks_in_library(self, client):
        resp = client.get("/api/blocks/library")
        block_types = {b["type"] for b in resp.json()["blocks"]}
        for expected in ["VoltageSource", "Resistor", "Inductor", "Capacitor"]:
            assert expected in block_types


# ===========================================================================
# Model CRUD
# ===========================================================================


class TestModelCreate:
    """Tests for POST /api/models."""

    def test_create_model(self, client):
        resp = client.post("/api/models", json=_constant_to_gain_model())
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert "model" in data
        assert data["model"]["name"] == "Constant to Gain"

    def test_create_model_returns_id(self, client):
        resp = client.post("/api/models", json=_constant_to_gain_model())
        assert len(resp.json()["id"]) == 12  # UUID hex[:12]

    def test_create_minimal_model(self, client):
        resp = client.post("/api/models", json={"name": "Empty"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["model"]["name"] == "Empty"
        assert data["model"]["blocks"] == []


class TestModelGet:
    """Tests for GET /api/models/{model_id}."""

    def test_get_existing_model(self, client):
        create_resp = client.post("/api/models", json=_constant_to_gain_model())
        model_id = create_resp.json()["id"]

        resp = client.get(f"/api/models/{model_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == model_id
        assert resp.json()["model"]["name"] == "Constant to Gain"

    def test_get_nonexistent_model_404(self, client):
        resp = client.get("/api/models/nonexistent")
        assert resp.status_code == 404


class TestModelList:
    """Tests for GET /api/models."""

    def test_list_empty(self, client):
        resp = client.get("/api/models")
        assert resp.status_code == 200
        assert resp.json()["models"] == []

    def test_list_after_create(self, client):
        client.post("/api/models", json=_constant_to_gain_model())
        client.post("/api/models", json=_integrator_model())

        resp = client.get("/api/models")
        assert resp.status_code == 200
        assert len(resp.json()["models"]) == 2


class TestModelUpdate:
    """Tests for PUT /api/models/{model_id}."""

    def test_update_model(self, client):
        create_resp = client.post("/api/models", json=_constant_to_gain_model())
        model_id = create_resp.json()["id"]

        updated = _constant_to_gain_model()
        updated["name"] = "Updated Name"
        resp = client.put(f"/api/models/{model_id}", json=updated)
        assert resp.status_code == 200
        assert resp.json()["model"]["name"] == "Updated Name"

    def test_update_nonexistent_model_404(self, client):
        resp = client.put("/api/models/nonexistent", json=_constant_to_gain_model())
        assert resp.status_code == 404


class TestModelDelete:
    """Tests for DELETE /api/models/{model_id}."""

    def test_delete_model(self, client):
        create_resp = client.post("/api/models", json=_constant_to_gain_model())
        model_id = create_resp.json()["id"]

        resp = client.delete(f"/api/models/{model_id}")
        assert resp.status_code == 204

        # Verify it's gone.
        get_resp = client.get(f"/api/models/{model_id}")
        assert get_resp.status_code == 404

    def test_delete_nonexistent_model_404(self, client):
        resp = client.delete("/api/models/nonexistent")
        assert resp.status_code == 404


# ===========================================================================
# Model Sub-resources: Blocks
# ===========================================================================


class TestAddBlock:
    """Tests for POST /api/models/{model_id}/blocks."""

    def test_add_block_to_model(self, client):
        """Add a new block to an existing model."""
        create_resp = client.post("/api/models", json={"name": "Empty"})
        model_id = create_resp.json()["id"]

        block = {"id": "src", "type": "ConstantSource", "params": {"value": 5.0}, "position": [0, 0]}
        resp = client.post(f"/api/models/{model_id}/blocks", json=block)
        assert resp.status_code == 201
        model_data = resp.json()["model"]
        assert len(model_data["blocks"]) == 1
        assert model_data["blocks"][0]["id"] == "src"

    def test_add_block_duplicate_id_400(self, client):
        """Adding a block with a duplicate ID should fail."""
        create_resp = client.post("/api/models", json=_constant_to_gain_model())
        model_id = create_resp.json()["id"]

        # Try to add a block with ID "src" which already exists.
        block = {"id": "src", "type": "Gain", "params": {"k": 1.0}, "position": [0, 0]}
        resp = client.post(f"/api/models/{model_id}/blocks", json=block)
        assert resp.status_code == 400

    def test_add_block_nonexistent_model_404(self, client):
        block = {"id": "x", "type": "Gain", "params": {"k": 1.0}, "position": [0, 0]}
        resp = client.post("/api/models/nonexistent/blocks", json=block)
        assert resp.status_code == 404

    def test_add_multiple_blocks_incrementally(self, client):
        """Add multiple blocks one at a time."""
        create_resp = client.post("/api/models", json={"name": "Incremental"})
        model_id = create_resp.json()["id"]

        client.post(f"/api/models/{model_id}/blocks", json={
            "id": "src", "type": "ConstantSource", "params": {"value": 1.0}, "position": [0, 0],
        })
        client.post(f"/api/models/{model_id}/blocks", json={
            "id": "gain", "type": "Gain", "params": {"k": 3.0}, "position": [100, 0],
        })

        resp = client.get(f"/api/models/{model_id}")
        assert len(resp.json()["model"]["blocks"]) == 2


class TestRemoveBlock:
    """Tests for DELETE /api/models/{model_id}/blocks/{block_id}."""

    def test_remove_block_from_model(self, client):
        """Remove a block and verify it's gone."""
        create_resp = client.post("/api/models", json=_constant_to_gain_model())
        model_id = create_resp.json()["id"]

        resp = client.delete(f"/api/models/{model_id}/blocks/scope")
        assert resp.status_code == 200
        model_data = resp.json()["model"]
        block_ids = {b["id"] for b in model_data["blocks"]}
        assert "scope" not in block_ids

    def test_remove_block_cascades_connections(self, client):
        """Removing a block should also remove its connections."""
        create_resp = client.post("/api/models", json=_constant_to_gain_model())
        model_id = create_resp.json()["id"]

        # Remove "gain" block — connections to/from it should also go.
        resp = client.delete(f"/api/models/{model_id}/blocks/gain")
        model_data = resp.json()["model"]

        # Only src→gain and gain→scope connections existed; both should be gone.
        for conn in model_data["connections"]:
            assert conn["source_block"] != "gain"
            assert conn["target_block"] != "gain"

    def test_remove_nonexistent_block_400(self, client):
        create_resp = client.post("/api/models", json=_constant_to_gain_model())
        model_id = create_resp.json()["id"]

        resp = client.delete(f"/api/models/{model_id}/blocks/nonexistent")
        assert resp.status_code == 400

    def test_remove_block_nonexistent_model_404(self, client):
        resp = client.delete("/api/models/nonexistent/blocks/foo")
        assert resp.status_code == 404


# ===========================================================================
# Model Sub-resources: Connections
# ===========================================================================


class TestAddConnection:
    """Tests for POST /api/models/{model_id}/connections."""

    def test_add_connection(self, client):
        """Add a connection between two blocks."""
        # Create model with two disconnected blocks.
        model = {
            "name": "Disconnected",
            "blocks": [
                {"id": "src", "type": "ConstantSource", "params": {"value": 1.0}, "position": [0, 0]},
                {"id": "gain", "type": "Gain", "params": {"k": 2.0}, "position": [100, 0]},
            ],
            "connections": [],
        }
        create_resp = client.post("/api/models", json=model)
        model_id = create_resp.json()["id"]

        conn = {
            "source_block": "src", "source_port": "out",
            "target_block": "gain", "target_port": "in",
        }
        resp = client.post(f"/api/models/{model_id}/connections", json=conn)
        assert resp.status_code == 201
        model_data = resp.json()["model"]
        assert len(model_data["connections"]) == 1
        assert model_data["connections"][0]["source_block"] == "src"

    def test_add_connection_invalid_source_block_400(self, client):
        """Connection referencing a nonexistent source block should fail."""
        model = {
            "name": "One Block",
            "blocks": [
                {"id": "gain", "type": "Gain", "params": {"k": 1.0}, "position": [0, 0]},
            ],
            "connections": [],
        }
        create_resp = client.post("/api/models", json=model)
        model_id = create_resp.json()["id"]

        conn = {
            "source_block": "missing", "source_port": "out",
            "target_block": "gain", "target_port": "in",
        }
        resp = client.post(f"/api/models/{model_id}/connections", json=conn)
        assert resp.status_code == 400

    def test_add_connection_duplicate_target_port_400(self, client):
        """Connecting to an already-connected target port should fail."""
        create_resp = client.post("/api/models", json=_constant_to_gain_model())
        model_id = create_resp.json()["id"]

        # gain.in is already connected from src.out — try adding another.
        conn = {
            "source_block": "scope", "source_port": "out",
            "target_block": "gain", "target_port": "in",
        }
        resp = client.post(f"/api/models/{model_id}/connections", json=conn)
        assert resp.status_code == 400

    def test_add_connection_nonexistent_model_404(self, client):
        conn = {
            "source_block": "a", "source_port": "out",
            "target_block": "b", "target_port": "in",
        }
        resp = client.post("/api/models/nonexistent/connections", json=conn)
        assert resp.status_code == 404


class TestRemoveConnection:
    """Tests for DELETE /api/models/{model_id}/connections."""

    def test_remove_connection(self, client):
        """Remove an existing connection."""
        create_resp = client.post("/api/models", json=_constant_to_gain_model())
        model_id = create_resp.json()["id"]

        conn = {
            "source_block": "src", "source_port": "out",
            "target_block": "gain", "target_port": "in",
        }
        resp = client.request("DELETE", f"/api/models/{model_id}/connections", json=conn)
        assert resp.status_code == 200
        model_data = resp.json()["model"]
        # Only the gain→scope connection should remain.
        assert len(model_data["connections"]) == 1
        assert model_data["connections"][0]["source_block"] == "gain"

    def test_remove_nonexistent_connection_400(self, client):
        """Removing a connection that doesn't exist should fail."""
        create_resp = client.post("/api/models", json=_constant_to_gain_model())
        model_id = create_resp.json()["id"]

        conn = {
            "source_block": "scope", "source_port": "out",
            "target_block": "src", "target_port": "in",
        }
        resp = client.request("DELETE", f"/api/models/{model_id}/connections", json=conn)
        assert resp.status_code == 400

    def test_remove_connection_nonexistent_model_404(self, client):
        conn = {
            "source_block": "a", "source_port": "out",
            "target_block": "b", "target_port": "in",
        }
        resp = client.request("DELETE", "/api/models/nonexistent/connections", json=conn)
        assert resp.status_code == 404


# ===========================================================================
# Full CRUD Flow: Build Model via Sub-resources, then Simulate
# ===========================================================================


class TestFullCRUDFlow:
    """Integration test: build a model incrementally via sub-resource routes,
    then simulate it and verify results."""

    def test_build_and_simulate_incrementally(self, client):
        """Create an empty model, add blocks & connections via sub-routes,
        then simulate and verify output values."""
        # 1. Create empty model.
        create_resp = client.post("/api/models", json={"name": "Incremental Build"})
        model_id = create_resp.json()["id"]

        # 2. Add blocks one at a time.
        client.post(f"/api/models/{model_id}/blocks", json={
            "id": "src", "type": "ConstantSource", "params": {"value": 3.0}, "position": [0, 0],
        })
        client.post(f"/api/models/{model_id}/blocks", json={
            "id": "gain", "type": "Gain", "params": {"k": 4.0}, "position": [100, 0],
        })
        client.post(f"/api/models/{model_id}/blocks", json={
            "id": "scope", "type": "Scope", "params": {}, "position": [200, 0],
        })

        # 3. Add connections.
        client.post(f"/api/models/{model_id}/connections", json={
            "source_block": "src", "source_port": "out",
            "target_block": "gain", "target_port": "in",
        })
        client.post(f"/api/models/{model_id}/connections", json={
            "source_block": "gain", "source_port": "out",
            "target_block": "scope", "target_port": "in",
        })

        # 4. Verify model structure.
        model_resp = client.get(f"/api/models/{model_id}")
        assert model_resp.status_code == 200
        model_data = model_resp.json()["model"]
        assert len(model_data["blocks"]) == 3
        assert len(model_data["connections"]) == 2

        # 5. Simulate.
        sim_resp = client.post(
            f"/api/simulate/{model_id}",
            json={"t_end": 0.01, "dt": 0.001, "solver": "rk4"},
        )
        assert sim_resp.status_code == 200
        signals = sim_resp.json()["signals"]

        # ConstantSource(3) * Gain(4) = 12.
        assert all(abs(v - 12.0) < 1e-10 for v in signals["gain.out"])


# ===========================================================================
# Simulation
# ===========================================================================


class TestSimulate:
    """Tests for POST /api/simulate/{model_id}."""

    def test_simulate_constant_to_gain(self, client):
        create_resp = client.post("/api/models", json=_constant_to_gain_model())
        model_id = create_resp.json()["id"]

        resp = client.post(
            f"/api/simulate/{model_id}",
            json={"t_end": 0.1, "dt": 0.01, "solver": "rk4"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "time" in data
        assert "signals" in data

        # ConstantSource(5) → Gain(2) → output should be 10.
        gain_signal = data["signals"]["gain.out"]
        assert all(abs(v - 10.0) < 1e-10 for v in gain_signal)

    def test_simulate_integrator(self, client):
        create_resp = client.post("/api/models", json=_integrator_model())
        model_id = create_resp.json()["id"]

        resp = client.post(
            f"/api/simulate/{model_id}",
            json={"t_end": 1.0, "dt": 0.001, "solver": "rk4"},
        )
        assert resp.status_code == 200
        data = resp.json()

        # Integrating constant 1.0 for 1.0s should give ~1.0 at the end.
        integ_signal = data["signals"]["integ.out"]
        final_value = integ_signal[-1]
        assert abs(final_value - 1.0) < 0.01

    def test_simulate_with_default_config(self, client):
        """Simulate without specifying config — uses defaults."""
        create_resp = client.post("/api/models", json=_constant_to_gain_model())
        model_id = create_resp.json()["id"]

        resp = client.post(f"/api/simulate/{model_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["time"]) > 0

    def test_simulate_nonexistent_model_404(self, client):
        resp = client.post(
            "/api/simulate/nonexistent",
            json={"t_end": 0.1, "dt": 0.01},
        )
        assert resp.status_code == 404

    def test_simulate_invalid_block_type_400(self, client):
        """Model with unknown block type should return 400."""
        bad_model = {
            "name": "Bad",
            "blocks": [{"id": "x", "type": "NonexistentBlock", "params": {}, "position": [0, 0]}],
            "connections": [],
        }
        create_resp = client.post("/api/models", json=bad_model)
        model_id = create_resp.json()["id"]

        resp = client.post(f"/api/simulate/{model_id}", json={"t_end": 0.1, "dt": 0.01})
        assert resp.status_code == 400

    def test_simulate_time_array_correct(self, client):
        """Time array should span from t_start to t_end."""
        create_resp = client.post("/api/models", json=_constant_to_gain_model())
        model_id = create_resp.json()["id"]

        resp = client.post(
            f"/api/simulate/{model_id}",
            json={"t_start": 0.0, "t_end": 0.5, "dt": 0.1},
        )
        assert resp.status_code == 200
        data = resp.json()
        time = data["time"]
        assert abs(time[0]) < 1e-10  # starts at 0
        assert abs(time[-1] - 0.5) < 0.01  # ends near 0.5


# ===========================================================================
# WebSocket Simulation Streaming
# ===========================================================================


class TestWebSocketSimulation:
    """Tests for WS /ws/simulate/{model_id}."""

    def test_ws_basic_streaming(self, client):
        """WebSocket should stream frames and send complete message."""
        create_resp = client.post("/api/models", json=_constant_to_gain_model())
        model_id = create_resp.json()["id"]

        with client.websocket_connect(f"/ws/simulate/{model_id}") as ws:
            ws.send_json({
                "action": "start",
                "config": {"t_end": 0.01, "dt": 0.001, "solver": "rk4"},
            })

            frames = []
            while True:
                msg = ws.receive_json()
                if msg["type"] == "frame":
                    frames.append(msg["data"])
                elif msg["type"] == "complete":
                    break
                elif msg["type"] == "error":
                    pytest.fail(f"Unexpected error: {msg['message']}")

            # Should have received at least 2 frames (initial + final).
            assert len(frames) >= 2

            # First frame should be at t=0.
            assert frames[0]["t"] == 0.0

            # Each frame should have signals.
            for frame in frames:
                assert "signals" in frame
                assert "gain.out" in frame["signals"]

    def test_ws_gain_output_values(self, client):
        """Verify that streamed values are physically correct."""
        create_resp = client.post("/api/models", json=_constant_to_gain_model())
        model_id = create_resp.json()["id"]

        with client.websocket_connect(f"/ws/simulate/{model_id}") as ws:
            ws.send_json({
                "action": "start",
                "config": {"t_end": 0.01, "dt": 0.001, "solver": "rk4"},
            })

            while True:
                msg = ws.receive_json()
                if msg["type"] == "frame":
                    # ConstantSource(5) → Gain(2) → output = 10.
                    assert abs(msg["data"]["signals"]["gain.out"] - 10.0) < 1e-10
                elif msg["type"] in ("complete", "error"):
                    break

    def test_ws_complete_summary(self, client):
        """Complete message should include summary stats."""
        create_resp = client.post("/api/models", json=_constant_to_gain_model())
        model_id = create_resp.json()["id"]

        with client.websocket_connect(f"/ws/simulate/{model_id}") as ws:
            ws.send_json({
                "action": "start",
                "config": {"t_end": 0.01, "dt": 0.001, "solver": "rk4"},
            })

            complete_msg = None
            while True:
                msg = ws.receive_json()
                if msg["type"] == "complete":
                    complete_msg = msg
                    break
                elif msg["type"] == "error":
                    pytest.fail(f"Unexpected error: {msg['message']}")

            assert complete_msg is not None
            assert "summary" in complete_msg
            assert "steps" in complete_msg["summary"]
            assert complete_msg["summary"]["steps"] == 10  # 0.01 / 0.001

    def test_ws_nonexistent_model(self, client):
        """WebSocket with invalid model_id should send error."""
        with client.websocket_connect("/ws/simulate/nonexistent") as ws:
            ws.send_json({"action": "start", "config": {"t_end": 0.01}})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "not found" in msg["message"].lower()

    def test_ws_invalid_action(self, client):
        """WebSocket with wrong action should send error."""
        create_resp = client.post("/api/models", json=_constant_to_gain_model())
        model_id = create_resp.json()["id"]

        with client.websocket_connect(f"/ws/simulate/{model_id}") as ws:
            ws.send_json({"action": "invalid"})
            msg = ws.receive_json()
            assert msg["type"] == "error"

    def test_ws_integrator_streaming(self, client):
        """Stream an integrator simulation — values should grow over time."""
        create_resp = client.post("/api/models", json=_integrator_model())
        model_id = create_resp.json()["id"]

        with client.websocket_connect(f"/ws/simulate/{model_id}") as ws:
            ws.send_json({
                "action": "start",
                "config": {"t_end": 0.1, "dt": 0.01, "solver": "rk4"},
            })

            prev_value = -1.0
            while True:
                msg = ws.receive_json()
                if msg["type"] == "frame":
                    integ_val = msg["data"]["signals"]["integ.out"]
                    # Integrator output should be monotonically increasing.
                    assert integ_val >= prev_value - 1e-10
                    prev_value = integ_val
                elif msg["type"] in ("complete", "error"):
                    break


# ===========================================================================
# Error handling
# ===========================================================================


class TestErrorHandling:
    """Tests for API error handling."""

    def test_invalid_connection_in_simulation(self, client):
        """Model with bad connections should fail during simulation."""
        bad_model = {
            "name": "Bad Connections",
            "blocks": [
                {"id": "src", "type": "ConstantSource", "params": {"value": 1.0}, "position": [0, 0]},
            ],
            "connections": [
                {"source_block": "src", "source_port": "out", "target_block": "missing", "target_port": "in"},
            ],
        }
        create_resp = client.post("/api/models", json=bad_model)
        model_id = create_resp.json()["id"]

        resp = client.post(f"/api/simulate/{model_id}", json={"t_end": 0.1, "dt": 0.01})
        # Should return an error (400 for connection error).
        assert resp.status_code in (400, 422, 500)

    def test_simulate_empty_model(self, client):
        """Empty model should simulate successfully (no blocks = no output)."""
        create_resp = client.post("/api/models", json={"name": "Empty"})
        model_id = create_resp.json()["id"]

        resp = client.post(f"/api/simulate/{model_id}", json={"t_end": 0.1, "dt": 0.01})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["time"]) > 0
        assert data["signals"] == {}
