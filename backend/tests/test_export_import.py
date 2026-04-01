"""Tests for export/import persistence functions (Task 6.1).

Covers:
- compute_checksum() — deterministic SHA-256 of canonical JSON
- build_export_envelope() — envelope structure and round-trip
- parse_import_file() — valid data, corrupted checksum, invalid JSON,
  missing fields, legacy format without checksum
"""

from __future__ import annotations

import hashlib
import json

import pytest

from blocksim.models.persistence import (
    SCHEMA_VERSION,
    build_export_envelope,
    compute_checksum,
    parse_import_file,
)
from blocksim.models.schemas import (
    BlockSchema,
    ConnectionSchema,
    ExportEnvelope,
    ModelSchema,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_model() -> ModelSchema:
    """A simple model for export/import testing."""
    return ModelSchema(
        name="Test Circuit",
        blocks=[
            BlockSchema(id="src", type="ConstantSource", params={"value": 5.0}, position=(0.0, 0.0)),
            BlockSchema(id="gain", type="Gain", params={"k": 2.0}, position=(100.0, 0.0)),
        ],
        connections=[
            ConnectionSchema(
                source_block="src", source_port="out",
                target_block="gain", target_port="in",
            ),
        ],
    )


@pytest.fixture
def sample_model_dict(sample_model: ModelSchema) -> dict:
    """The model dumped to a dict."""
    return sample_model.model_dump()


# ===========================================================================
# compute_checksum tests
# ===========================================================================


class TestComputeChecksum:
    """Tests for compute_checksum()."""

    def test_returns_hex_string(self, sample_model_dict: dict) -> None:
        result = compute_checksum(sample_model_dict)
        assert isinstance(result, str)
        # SHA-256 hex digest is 64 characters.
        assert len(result) == 64
        # Must be valid hex.
        int(result, 16)

    def test_deterministic(self, sample_model_dict: dict) -> None:
        """Calling twice on the same data produces the same result."""
        c1 = compute_checksum(sample_model_dict)
        c2 = compute_checksum(sample_model_dict)
        assert c1 == c2

    def test_key_order_independent(self) -> None:
        """Different insertion order of keys produces the same checksum."""
        d1 = {"a": 1, "b": 2, "c": 3}
        d2 = {"c": 3, "a": 1, "b": 2}
        assert compute_checksum(d1) == compute_checksum(d2)

    def test_different_data_different_checksum(self) -> None:
        d1 = {"name": "alpha"}
        d2 = {"name": "beta"}
        assert compute_checksum(d1) != compute_checksum(d2)

    def test_matches_manual_sha256(self) -> None:
        """Verify against a manual SHA-256 computation."""
        data = {"x": 42}
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
        expected = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        assert compute_checksum(data) == expected


# ===========================================================================
# build_export_envelope tests
# ===========================================================================


class TestBuildExportEnvelope:
    """Tests for build_export_envelope()."""

    def test_returns_export_envelope(self, sample_model: ModelSchema) -> None:
        envelope = build_export_envelope(sample_model)
        assert isinstance(envelope, ExportEnvelope)

    def test_envelope_schema_version(self, sample_model: ModelSchema) -> None:
        envelope = build_export_envelope(sample_model)
        assert envelope.schema_version == SCHEMA_VERSION

    def test_envelope_has_exported_at(self, sample_model: ModelSchema) -> None:
        envelope = build_export_envelope(sample_model)
        # Should be an ISO-8601 string.
        assert "T" in envelope.exported_at  # basic ISO-8601 check

    def test_envelope_has_blocksim_version(self, sample_model: ModelSchema) -> None:
        envelope = build_export_envelope(sample_model)
        assert envelope.blocksim_version == "0.1.0"

    def test_envelope_checksum_matches_model(self, sample_model: ModelSchema) -> None:
        """Checksum in envelope matches recomputed checksum of the model."""
        envelope = build_export_envelope(sample_model)
        recomputed = compute_checksum(sample_model.model_dump())
        assert envelope.checksum == recomputed

    def test_envelope_contains_model(self, sample_model: ModelSchema) -> None:
        envelope = build_export_envelope(sample_model)
        assert envelope.model.name == sample_model.name
        assert len(envelope.model.blocks) == len(sample_model.blocks)

    def test_round_trip_export_reimport(self, sample_model: ModelSchema) -> None:
        """Export → serialize → parse_import_file → checksum still matches."""
        envelope = build_export_envelope(sample_model)
        envelope_json = json.dumps(envelope.model_dump(), indent=2)
        file_bytes = envelope_json.encode("utf-8")

        data, checksum_match = parse_import_file(file_bytes)
        assert checksum_match is True
        assert data["model"]["name"] == "Test Circuit"


# ===========================================================================
# parse_import_file tests
# ===========================================================================


class TestParseImportFile:
    """Tests for parse_import_file()."""

    def test_valid_file_with_matching_checksum(self, sample_model: ModelSchema) -> None:
        """A correctly exported file should have checksum_match=True."""
        envelope = build_export_envelope(sample_model)
        file_bytes = json.dumps(envelope.model_dump()).encode("utf-8")

        data, checksum_match = parse_import_file(file_bytes)
        assert checksum_match is True
        assert data["model"]["name"] == "Test Circuit"

    def test_corrupted_checksum_returns_false(self, sample_model: ModelSchema) -> None:
        """If the checksum doesn't match the model, checksum_match=False."""
        envelope = build_export_envelope(sample_model)
        raw = envelope.model_dump()
        raw["checksum"] = "0" * 64  # corrupt the checksum

        file_bytes = json.dumps(raw).encode("utf-8")
        data, checksum_match = parse_import_file(file_bytes)
        assert checksum_match is False
        assert data["model"]["name"] == "Test Circuit"

    def test_legacy_format_no_checksum(self) -> None:
        """A file without a checksum field should return checksum_match=None."""
        legacy_data = {
            "schema_version": "1.0.0",
            "model": {"name": "Old Model", "blocks": [], "connections": []},
        }
        file_bytes = json.dumps(legacy_data).encode("utf-8")

        data, checksum_match = parse_import_file(file_bytes)
        assert checksum_match is None
        assert data["model"]["name"] == "Old Model"

    def test_invalid_json_raises(self) -> None:
        """Malformed JSON should raise json.JSONDecodeError."""
        with pytest.raises(json.JSONDecodeError):
            parse_import_file(b"{ not valid json !!!")

    def test_non_dict_raises(self) -> None:
        """A JSON array or string at top level should raise ValueError."""
        with pytest.raises(ValueError, match="Expected a JSON object"):
            parse_import_file(b'"just a string"')

    def test_missing_model_key_raises(self) -> None:
        """A JSON object without a 'model' key should raise ValueError."""
        data = {"schema_version": "1.0.0"}
        with pytest.raises(ValueError, match="Missing 'model' key"):
            parse_import_file(json.dumps(data).encode("utf-8"))

    def test_returns_full_data_dict(self, sample_model: ModelSchema) -> None:
        """The returned data dict should contain all top-level keys."""
        envelope = build_export_envelope(sample_model)
        raw = envelope.model_dump()
        file_bytes = json.dumps(raw).encode("utf-8")

        data, _ = parse_import_file(file_bytes)
        assert "schema_version" in data
        assert "exported_at" in data
        assert "blocksim_version" in data
        assert "checksum" in data
        assert "model" in data

    def test_model_data_tampered_but_still_parses(self) -> None:
        """If model data is changed after export, checksum_match=False but parse succeeds."""
        data = {
            "schema_version": "1.0.0",
            "checksum": "abc123",  # bogus but present
            "model": {"name": "Tampered", "blocks": [], "connections": []},
        }
        file_bytes = json.dumps(data).encode("utf-8")

        result_data, checksum_match = parse_import_file(file_bytes)
        assert checksum_match is False
        assert result_data["model"]["name"] == "Tampered"
