"""Tests for ModelValidator — 3-level validation pipeline (Task 6.2).

Covers:
- Level 1 (Schema): Pydantic structural validation
- Level 2 (Referential): block IDs, port names, block types
- Level 3 (Semantic): algebraic loops, compilation checks
- Valid model passes all levels
- Validator never raises exceptions
"""

from __future__ import annotations

import pytest

from blocksim.blocks.registry import registry
from blocksim.models.schemas import (
    ModelSchema,
    ValidationResult,
)
from blocksim.models.validator import ModelValidator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def validator() -> ModelValidator:
    """A ModelValidator using the real block registry."""
    return ModelValidator(registry)


def _valid_model_data() -> dict:
    """A well-formed model with valid blocks and connections."""
    return {
        "name": "Valid Model",
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


# ===========================================================================
# Valid model — all levels pass
# ===========================================================================


class TestValidModel:
    """A valid model should pass all 3 validation levels."""

    def test_valid_model_returns_valid(self, validator: ModelValidator) -> None:
        model, result = validator.validate(_valid_model_data())
        assert model is not None
        assert result.valid is True

    def test_valid_model_no_errors(self, validator: ModelValidator) -> None:
        _, result = validator.validate(_valid_model_data())
        errors = [i for i in result.issues if i.severity == "error"]
        assert len(errors) == 0

    def test_valid_model_returns_parsed_model(self, validator: ModelValidator) -> None:
        model, _ = validator.validate(_valid_model_data())
        assert isinstance(model, ModelSchema)
        assert model.name == "Valid Model"
        assert len(model.blocks) == 3


# ===========================================================================
# Level 1: Schema validation
# ===========================================================================


class TestSchemaValidation:
    """Level 1 — Pydantic structural checks."""

    def test_invalid_block_schema_missing_type(self, validator: ModelValidator) -> None:
        """A block missing the required 'type' field should produce a schema error."""
        data = {
            "name": "Bad Schema",
            "blocks": [
                {"id": "src", "params": {}, "position": [0, 0]},  # no 'type'
            ],
            "connections": [],
        }
        model, result = validator.validate(data)
        assert model is None  # Schema validation failed
        assert result.valid is False
        schema_errors = [i for i in result.issues if i.category == "schema"]
        assert len(schema_errors) > 0

    def test_invalid_block_schema_missing_id(self, validator: ModelValidator) -> None:
        """A block missing the required 'id' field should produce a schema error."""
        data = {
            "name": "Bad Schema",
            "blocks": [
                {"type": "Gain", "params": {}, "position": [0, 0]},  # no 'id'
            ],
            "connections": [],
        }
        model, result = validator.validate(data)
        assert model is None
        assert result.valid is False

    def test_completely_invalid_data(self, validator: ModelValidator) -> None:
        """Totally invalid data should produce schema errors, not raise."""
        model, result = validator.validate({"garbage": True})
        # Should return some result without raising
        assert isinstance(result, ValidationResult)

    def test_empty_model_passes_schema(self, validator: ModelValidator) -> None:
        """An empty model with just a name should pass schema validation."""
        model, result = validator.validate({"name": "Empty"})
        assert model is not None
        assert model.name == "Empty"


# ===========================================================================
# Level 2: Referential integrity
# ===========================================================================


class TestReferentialValidation:
    """Level 2 — cross-reference checks."""

    def test_unknown_block_type(self, validator: ModelValidator) -> None:
        """Block with a type not in the registry should produce a referential error."""
        data = {
            "name": "Unknown Type",
            "blocks": [
                {"id": "foo", "type": "FooBlock", "params": {}, "position": [0, 0]},
            ],
            "connections": [],
        }
        model, result = validator.validate(data)
        assert model is not None  # Schema is valid
        assert result.valid is False
        ref_errors = [i for i in result.issues if i.category == "referential"]
        assert any("FooBlock" in e.message for e in ref_errors)

    def test_dangling_connection_source(self, validator: ModelValidator) -> None:
        """Connection referencing a nonexistent source block should be an error."""
        data = {
            "name": "Dangling Source",
            "blocks": [
                {"id": "gain", "type": "Gain", "params": {"k": 1.0}, "position": [0, 0]},
            ],
            "connections": [
                {
                    "source_block": "nonexistent",
                    "source_port": "out",
                    "target_block": "gain",
                    "target_port": "in",
                },
            ],
        }
        model, result = validator.validate(data)
        assert result.valid is False
        ref_errors = [i for i in result.issues if i.category == "referential"]
        assert any("nonexistent" in e.message for e in ref_errors)

    def test_dangling_connection_target(self, validator: ModelValidator) -> None:
        """Connection referencing a nonexistent target block should be an error."""
        data = {
            "name": "Dangling Target",
            "blocks": [
                {"id": "src", "type": "ConstantSource", "params": {"value": 1.0}, "position": [0, 0]},
            ],
            "connections": [
                {
                    "source_block": "src",
                    "source_port": "out",
                    "target_block": "missing",
                    "target_port": "in",
                },
            ],
        }
        model, result = validator.validate(data)
        assert result.valid is False
        ref_errors = [i for i in result.issues if i.category == "referential"]
        assert any("missing" in e.message for e in ref_errors)

    def test_invalid_port_name(self, validator: ModelValidator) -> None:
        """Connection with an invalid port name should produce a referential error."""
        data = {
            "name": "Bad Port",
            "blocks": [
                {"id": "src", "type": "ConstantSource", "params": {"value": 1.0}, "position": [0, 0]},
                {"id": "gain", "type": "Gain", "params": {"k": 1.0}, "position": [100, 0]},
            ],
            "connections": [
                {
                    "source_block": "src",
                    "source_port": "nonexistent_port",
                    "target_block": "gain",
                    "target_port": "in",
                },
            ],
        }
        model, result = validator.validate(data)
        assert result.valid is False
        ref_errors = [i for i in result.issues if i.category == "referential"]
        assert any("nonexistent_port" in e.message for e in ref_errors)

    def test_multiple_unknown_block_types(self, validator: ModelValidator) -> None:
        """Multiple unknown block types should each produce an error."""
        data = {
            "name": "Multi Unknown",
            "blocks": [
                {"id": "a", "type": "AlphaBlock", "params": {}, "position": [0, 0]},
                {"id": "b", "type": "BetaBlock", "params": {}, "position": [100, 0]},
            ],
            "connections": [],
        }
        model, result = validator.validate(data)
        assert result.valid is False
        ref_errors = [i for i in result.issues if i.category == "referential"]
        assert any("AlphaBlock" in e.message for e in ref_errors)
        assert any("BetaBlock" in e.message for e in ref_errors)


# ===========================================================================
# Level 3: Semantic validation
# ===========================================================================


class TestSemanticValidation:
    """Level 3 — compile-based checks (algebraic loops, unconnected ports)."""

    def test_unconnected_input_port_warning(self, validator: ModelValidator) -> None:
        """A block with an unconnected required input should produce a semantic warning."""
        data = {
            "name": "Unconnected Port",
            "blocks": [
                {"id": "gain", "type": "Gain", "params": {"k": 1.0}, "position": [0, 0]},
            ],
            "connections": [],
        }
        model, result = validator.validate(data)
        # Unconnected port is a warning, not an error, so model may still be "valid"
        # But the semantic check should produce a warning.
        semantic_issues = [i for i in result.issues if i.category == "semantic"]
        assert len(semantic_issues) > 0
        assert any(i.severity == "warning" for i in semantic_issues)

    def test_algebraic_loop_warning(self, validator: ModelValidator) -> None:
        """A model with an algebraic loop should produce a semantic warning."""
        data = {
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
        model, result = validator.validate(data)
        semantic_issues = [i for i in result.issues if i.category == "semantic"]
        assert len(semantic_issues) > 0

    def test_semantic_skipped_for_unknown_types(self, validator: ModelValidator) -> None:
        """When block types are unknown, semantic validation should be skipped."""
        data = {
            "name": "Unknown Skip",
            "blocks": [
                {"id": "x", "type": "UnknownBlock", "params": {}, "position": [0, 0]},
            ],
            "connections": [],
        }
        model, result = validator.validate(data)
        # Should have referential errors (unknown type) but no semantic issues.
        semantic_issues = [i for i in result.issues if i.category == "semantic"]
        assert len(semantic_issues) == 0


# ===========================================================================
# Never-raises guarantee
# ===========================================================================


class TestNeverRaises:
    """The validator should never raise exceptions — all issues are collected."""

    def test_none_data(self, validator: ModelValidator) -> None:
        """Passing really bad data shouldn't raise."""
        # This will fail Pydantic validation (not a dict).
        # Actually validate expects a dict, so let's give it a dict with bad structure.
        model, result = validator.validate({})
        assert isinstance(result, ValidationResult)

    def test_blocks_with_weird_params(self, validator: ModelValidator) -> None:
        """Blocks with unusual params shouldn't crash the validator."""
        data = {
            "name": "Weird Params",
            "blocks": [
                {"id": "src", "type": "ConstantSource", "params": {"value": "not_a_number"}, "position": [0, 0]},
            ],
            "connections": [],
        }
        # Should not raise — the validator should catch the error.
        model, result = validator.validate(data)
        assert isinstance(result, ValidationResult)

    def test_valid_model_with_no_connections(self, validator: ModelValidator) -> None:
        """A model with blocks but no connections should not raise."""
        data = {
            "name": "No Connections",
            "blocks": [
                {"id": "src", "type": "ConstantSource", "params": {"value": 1.0}, "position": [0, 0]},
            ],
            "connections": [],
        }
        model, result = validator.validate(data)
        assert isinstance(result, ValidationResult)
        # ConstantSource has no input ports, so no unconnected-port warning expected.
        assert model is not None
