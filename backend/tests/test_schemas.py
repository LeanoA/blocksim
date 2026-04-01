"""Tests for Pydantic schemas (models/schemas.py).

Covers:
- PortSchema creation and serialization
- BlockSchema with defaults and custom values
- ConnectionSchema fields
- ModelSchema with blocks and connections
- SimulationConfigSchema defaults and custom
- SimulationResultSchema
- SimFrameSchema
- Round-trip JSON serialization/deserialization
"""

from __future__ import annotations

import pytest

from blocksim.models.schemas import (
    BlockSchema,
    ConnectionSchema,
    ModelSchema,
    PortSchema,
    SimFrameSchema,
    SimulationConfigSchema,
    SimulationResultSchema,
)


# ---------------------------------------------------------------------------
# PortSchema
# ---------------------------------------------------------------------------


class TestPortSchema:

    def test_create_input_port(self):
        p = PortSchema(name="in", direction="in")
        assert p.name == "in"
        assert p.direction == "in"
        assert p.dtype == "float"

    def test_create_output_port(self):
        p = PortSchema(name="out", direction="out", dtype="complex")
        assert p.direction == "out"
        assert p.dtype == "complex"

    def test_invalid_direction_raises(self):
        with pytest.raises(Exception):
            PortSchema(name="x", direction="sideways")

    def test_port_to_dict(self):
        p = PortSchema(name="in1", direction="in")
        d = p.model_dump()
        assert d == {"name": "in1", "direction": "in", "dtype": "float"}


# ---------------------------------------------------------------------------
# BlockSchema
# ---------------------------------------------------------------------------


class TestBlockSchema:

    def test_create_with_defaults(self):
        b = BlockSchema(id="b1", type="Gain")
        assert b.id == "b1"
        assert b.type == "Gain"
        assert b.params == {}
        assert b.position == (0.0, 0.0)

    def test_create_with_params(self):
        b = BlockSchema(id="b2", type="Sum", params={"signs": "++"}, position=(10.0, 20.0))
        assert b.params == {"signs": "++"}
        assert b.position == (10.0, 20.0)

    def test_block_to_json_roundtrip(self):
        b = BlockSchema(id="g1", type="Gain", params={"k": 2.5}, position=(100.0, 50.0))
        json_str = b.model_dump_json()
        b2 = BlockSchema.model_validate_json(json_str)
        assert b2.id == b.id
        assert b2.type == b.type
        assert b2.params == b.params
        assert b2.position == b.position


# ---------------------------------------------------------------------------
# ConnectionSchema
# ---------------------------------------------------------------------------


class TestConnectionSchema:

    def test_create_connection(self):
        c = ConnectionSchema(
            source_block="b1", source_port="out",
            target_block="b2", target_port="in",
        )
        assert c.source_block == "b1"
        assert c.source_port == "out"
        assert c.target_block == "b2"
        assert c.target_port == "in"

    def test_connection_to_dict(self):
        c = ConnectionSchema(
            source_block="a", source_port="out",
            target_block="b", target_port="in1",
        )
        d = c.model_dump()
        assert d["source_block"] == "a"
        assert d["target_port"] == "in1"


# ---------------------------------------------------------------------------
# ModelSchema
# ---------------------------------------------------------------------------


class TestModelSchema:

    def test_empty_model(self):
        m = ModelSchema()
        assert m.name == "Untitled"
        assert m.blocks == []
        assert m.connections == []
        assert m.metadata == {}

    def test_model_with_blocks_and_connections(self):
        m = ModelSchema(
            name="Test Model",
            blocks=[
                BlockSchema(id="s1", type="ConstantSource", params={"value": 5.0}),
                BlockSchema(id="g1", type="Gain", params={"k": 2.0}),
            ],
            connections=[
                ConnectionSchema(
                    source_block="s1", source_port="out",
                    target_block="g1", target_port="in",
                ),
            ],
            metadata={"version": "1.0"},
        )
        assert m.name == "Test Model"
        assert len(m.blocks) == 2
        assert len(m.connections) == 1
        assert m.metadata["version"] == "1.0"

    def test_model_json_roundtrip(self):
        m = ModelSchema(
            name="RLC",
            blocks=[BlockSchema(id="v1", type="VoltageSource")],
            connections=[],
        )
        json_str = m.model_dump_json()
        m2 = ModelSchema.model_validate_json(json_str)
        assert m2.name == m.name
        assert len(m2.blocks) == 1


# ---------------------------------------------------------------------------
# SimulationConfigSchema
# ---------------------------------------------------------------------------


class TestSimulationConfigSchema:

    def test_defaults(self):
        cfg = SimulationConfigSchema()
        assert cfg.t_start == 0.0
        assert cfg.t_end == 1.0
        assert cfg.dt == 0.001
        assert cfg.solver == "rk4"

    def test_custom_config(self):
        cfg = SimulationConfigSchema(t_start=0.5, t_end=2.0, dt=0.01, solver="euler")
        assert cfg.t_start == 0.5
        assert cfg.t_end == 2.0
        assert cfg.dt == 0.01
        assert cfg.solver == "euler"

    def test_invalid_solver_raises(self):
        with pytest.raises(Exception):
            SimulationConfigSchema(solver="bogus")


# ---------------------------------------------------------------------------
# SimulationResultSchema
# ---------------------------------------------------------------------------


class TestSimulationResultSchema:

    def test_create_result(self):
        r = SimulationResultSchema(
            time=[0.0, 0.1, 0.2],
            signals={"scope.in": [1.0, 2.0, 3.0]},
        )
        assert len(r.time) == 3
        assert "scope.in" in r.signals

    def test_empty_signals(self):
        r = SimulationResultSchema(time=[0.0], signals={})
        assert r.signals == {}


# ---------------------------------------------------------------------------
# SimFrameSchema
# ---------------------------------------------------------------------------


class TestSimFrameSchema:

    def test_create_frame(self):
        f = SimFrameSchema(t=0.5, signals={"v_cap": 3.14})
        assert f.t == 0.5
        assert f.signals["v_cap"] == 3.14

    def test_frame_json(self):
        f = SimFrameSchema(t=1.0, signals={"a": 1.0, "b": 2.0})
        json_str = f.model_dump_json()
        f2 = SimFrameSchema.model_validate_json(json_str)
        assert f2.t == 1.0
        assert f2.signals == {"a": 1.0, "b": 2.0}
