"""Tests for JSON model persistence (T-5.1) and error UX (T-5.4)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from blocksim.models.persistence import (
    SCHEMA_VERSION,
    ModelFileError,
    SchemaVersionError,
    load_model,
    save_model,
)
from blocksim.models.schemas import (
    BlockSchema,
    ConnectionSchema,
    ModelSchema,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_model() -> ModelSchema:
    """A model with 5 blocks and 4 connections (spec scenario)."""
    return ModelSchema(
        name="Test RLC Circuit",
        blocks=[
            BlockSchema(id="vsrc", type="VoltageSource", params={"voltage": 5.0}, position=(0.0, 100.0)),
            BlockSchema(id="r1", type="Resistor", params={"resistance": 10.0}, position=(200.0, 100.0)),
            BlockSchema(id="l1", type="Inductor", params={"inductance": 0.1}, position=(400.0, 100.0)),
            BlockSchema(id="c1", type="Capacitor", params={"capacitance": 100e-6}, position=(600.0, 100.0)),
            BlockSchema(id="scope", type="Scope", params={}, position=(800.0, 100.0)),
        ],
        connections=[
            ConnectionSchema(source_block="vsrc", source_port="out", target_block="r1", target_port="in"),
            ConnectionSchema(source_block="r1", source_port="out", target_block="l1", target_port="in"),
            ConnectionSchema(source_block="l1", source_port="out", target_block="c1", target_port="in"),
            ConnectionSchema(source_block="c1", source_port="out", target_block="scope", target_port="in"),
        ],
        metadata={"description": "Test circuit for persistence"},
    )


@pytest.fixture
def tmp_model_path(tmp_path: Path) -> Path:
    """Return a temporary file path for model saving."""
    return tmp_path / "test_model.json"


# ---------------------------------------------------------------------------
# save_model tests
# ---------------------------------------------------------------------------


class TestSaveModel:
    """Tests for save_model()."""

    def test_save_creates_file(self, sample_model: ModelSchema, tmp_model_path: Path) -> None:
        result = save_model(sample_model, tmp_model_path)
        assert tmp_model_path.exists()
        assert result == tmp_model_path.resolve()

    def test_save_writes_valid_json(self, sample_model: ModelSchema, tmp_model_path: Path) -> None:
        save_model(sample_model, tmp_model_path)
        data = json.loads(tmp_model_path.read_text())
        assert isinstance(data, dict)

    def test_save_includes_schema_version(self, sample_model: ModelSchema, tmp_model_path: Path) -> None:
        save_model(sample_model, tmp_model_path)
        data = json.loads(tmp_model_path.read_text())
        assert data["schema_version"] == SCHEMA_VERSION

    def test_save_includes_model_data(self, sample_model: ModelSchema, tmp_model_path: Path) -> None:
        save_model(sample_model, tmp_model_path)
        data = json.loads(tmp_model_path.read_text())
        assert "model" in data
        assert data["model"]["name"] == "Test RLC Circuit"
        assert len(data["model"]["blocks"]) == 5
        assert len(data["model"]["connections"]) == 4

    def test_save_creates_parent_directories(self, sample_model: ModelSchema, tmp_path: Path) -> None:
        deep_path = tmp_path / "a" / "b" / "c" / "model.json"
        save_model(sample_model, deep_path)
        assert deep_path.exists()

    def test_save_overwrites_existing_file(self, sample_model: ModelSchema, tmp_model_path: Path) -> None:
        tmp_model_path.write_text("old content")
        save_model(sample_model, tmp_model_path)
        data = json.loads(tmp_model_path.read_text())
        assert data["model"]["name"] == "Test RLC Circuit"

    def test_save_accepts_string_path(self, sample_model: ModelSchema, tmp_model_path: Path) -> None:
        save_model(sample_model, str(tmp_model_path))
        assert tmp_model_path.exists()


# ---------------------------------------------------------------------------
# load_model tests
# ---------------------------------------------------------------------------


class TestLoadModel:
    """Tests for load_model()."""

    def test_load_from_saved_file(self, sample_model: ModelSchema, tmp_model_path: Path) -> None:
        save_model(sample_model, tmp_model_path)
        loaded = load_model(tmp_model_path)
        assert isinstance(loaded, ModelSchema)

    def test_load_preserves_name(self, sample_model: ModelSchema, tmp_model_path: Path) -> None:
        save_model(sample_model, tmp_model_path)
        loaded = load_model(tmp_model_path)
        assert loaded.name == sample_model.name

    def test_load_preserves_blocks(self, sample_model: ModelSchema, tmp_model_path: Path) -> None:
        save_model(sample_model, tmp_model_path)
        loaded = load_model(tmp_model_path)
        assert len(loaded.blocks) == len(sample_model.blocks)
        for orig, loaded_block in zip(sample_model.blocks, loaded.blocks):
            assert orig.id == loaded_block.id
            assert orig.type == loaded_block.type
            assert orig.params == loaded_block.params

    def test_load_preserves_connections(self, sample_model: ModelSchema, tmp_model_path: Path) -> None:
        save_model(sample_model, tmp_model_path)
        loaded = load_model(tmp_model_path)
        assert len(loaded.connections) == len(sample_model.connections)
        for orig, loaded_conn in zip(sample_model.connections, loaded.connections):
            assert orig.source_block == loaded_conn.source_block
            assert orig.source_port == loaded_conn.source_port
            assert orig.target_block == loaded_conn.target_block
            assert orig.target_port == loaded_conn.target_port

    def test_load_preserves_positions(self, sample_model: ModelSchema, tmp_model_path: Path) -> None:
        save_model(sample_model, tmp_model_path)
        loaded = load_model(tmp_model_path)
        for orig, loaded_block in zip(sample_model.blocks, loaded.blocks):
            assert orig.position == loaded_block.position

    def test_load_preserves_metadata(self, sample_model: ModelSchema, tmp_model_path: Path) -> None:
        save_model(sample_model, tmp_model_path)
        loaded = load_model(tmp_model_path)
        assert loaded.metadata == sample_model.metadata

    def test_load_nonexistent_file_raises(self) -> None:
        with pytest.raises(ModelFileError, match="does not exist"):
            load_model("/nonexistent/path/model.json")

    def test_load_invalid_json_raises(self, tmp_model_path: Path) -> None:
        tmp_model_path.write_text("{ not valid json !!!")
        with pytest.raises(ModelFileError, match="Invalid JSON"):
            load_model(tmp_model_path)

    def test_load_non_object_raises(self, tmp_model_path: Path) -> None:
        tmp_model_path.write_text('"just a string"')
        with pytest.raises(ModelFileError, match="Expected a JSON object"):
            load_model(tmp_model_path)

    def test_load_missing_model_key_raises(self, tmp_model_path: Path) -> None:
        tmp_model_path.write_text(json.dumps({"schema_version": "1.0.0"}))
        with pytest.raises(ModelFileError, match="Missing 'model' key"):
            load_model(tmp_model_path)

    def test_load_incompatible_version_raises(self, tmp_model_path: Path) -> None:
        data = {
            "schema_version": "99.0.0",
            "model": {"name": "test", "blocks": [], "connections": []},
        }
        tmp_model_path.write_text(json.dumps(data))
        with pytest.raises(SchemaVersionError, match="99.0.0"):
            load_model(tmp_model_path)

    def test_load_accepts_string_path(self, sample_model: ModelSchema, tmp_model_path: Path) -> None:
        save_model(sample_model, tmp_model_path)
        loaded = load_model(str(tmp_model_path))
        assert loaded.name == sample_model.name


# ---------------------------------------------------------------------------
# Round-trip tests (spec scenario)
# ---------------------------------------------------------------------------


class TestRoundTrip:
    """Validate that save → load → compare produces identical models."""

    def test_roundtrip_identical(self, sample_model: ModelSchema, tmp_model_path: Path) -> None:
        """Spec scenario: save → load → all fields identical."""
        save_model(sample_model, tmp_model_path)
        loaded = load_model(tmp_model_path)
        assert sample_model.model_dump() == loaded.model_dump()

    def test_roundtrip_empty_model(self, tmp_model_path: Path) -> None:
        """Round-trip with a minimal empty model."""
        model = ModelSchema(name="Empty")
        save_model(model, tmp_model_path)
        loaded = load_model(tmp_model_path)
        assert model.model_dump() == loaded.model_dump()

    def test_roundtrip_complex_params(self, tmp_model_path: Path) -> None:
        """Round-trip with nested/complex parameters."""
        model = ModelSchema(
            name="Complex Params",
            blocks=[
                BlockSchema(
                    id="b1",
                    type="Sum",
                    params={"signs": "+-"},
                    position=(123.456, -789.012),
                ),
            ],
            metadata={"author": "test", "tags": ["circuit", "RLC"]},
        )
        save_model(model, tmp_model_path)
        loaded = load_model(tmp_model_path)
        assert model.model_dump() == loaded.model_dump()

    def test_multiple_save_load_cycles(self, sample_model: ModelSchema, tmp_model_path: Path) -> None:
        """Multiple round-trips should be idempotent."""
        for _ in range(3):
            save_model(sample_model, tmp_model_path)
            sample_model = load_model(tmp_model_path)
        assert sample_model.name == "Test RLC Circuit"
        assert len(sample_model.blocks) == 5


# ---------------------------------------------------------------------------
# Schema version compatibility
# ---------------------------------------------------------------------------


class TestSchemaVersioning:
    """Tests for schema version handling."""

    def test_current_version_is_1_0_0(self) -> None:
        assert SCHEMA_VERSION == "1.0.0"

    def test_older_version_loads_ok(self, tmp_model_path: Path) -> None:
        """Files with older versions should load fine."""
        data = {
            "schema_version": "0.9.0",
            "model": {"name": "old model", "blocks": [], "connections": []},
        }
        tmp_model_path.write_text(json.dumps(data))
        loaded = load_model(tmp_model_path)
        assert loaded.name == "old model"

    def test_same_version_loads_ok(self, tmp_model_path: Path) -> None:
        data = {
            "schema_version": SCHEMA_VERSION,
            "model": {"name": "same version", "blocks": [], "connections": []},
        }
        tmp_model_path.write_text(json.dumps(data))
        loaded = load_model(tmp_model_path)
        assert loaded.name == "same version"

    def test_missing_version_loads_ok(self, tmp_model_path: Path) -> None:
        """Files without schema_version default to 0.0.0 and load."""
        data = {
            "model": {"name": "no version", "blocks": [], "connections": []},
        }
        tmp_model_path.write_text(json.dumps(data))
        loaded = load_model(tmp_model_path)
        assert loaded.name == "no version"
