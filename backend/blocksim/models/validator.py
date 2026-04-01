"""Model validation: structural, referential, and semantic checks.

The :class:`ModelValidator` runs a 3-level validation pipeline on model data
and returns a :class:`ValidationResult` with all issues collected — it never
raises exceptions.

Levels:
1. **Schema** — Pydantic structural validation (``ModelSchema.model_validate()``)
2. **Referential** — block IDs in connections exist, port names are valid
3. **Semantic** — attempt ``compile()`` to detect algebraic loops, unconnected ports

Usage::

    from blocksim.blocks.registry import registry
    from blocksim.models.validator import ModelValidator

    validator = ModelValidator(registry)
    model, result = validator.validate(data)
    if result.valid:
        print("Model is valid!")
    else:
        for issue in result.issues:
            print(f"[{issue.severity}] {issue.message}")
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from blocksim.blocks.registry import BlockRegistry
from blocksim.models.schemas import (
    ModelSchema,
    ValidationIssue,
    ValidationResult,
)


class ModelValidator:
    """Validate model data through a 3-level pipeline.

    The validator **never raises exceptions**. All problems are collected
    as :class:`ValidationIssue` entries in the returned
    :class:`ValidationResult`.

    Parameters
    ----------
    registry:
        The block registry used to check block types and port names.
    """

    def __init__(self, registry: BlockRegistry) -> None:
        self._registry = registry

    def validate(self, data: dict[str, Any]) -> tuple[ModelSchema | None, ValidationResult]:
        """Run all 3 validation levels on *data*.

        Parameters
        ----------
        data:
            Raw model data dictionary (e.g. from JSON import).

        Returns
        -------
        tuple[ModelSchema | None, ValidationResult]
            ``(parsed_model, result)`` — the parsed model is ``None``
            when schema validation fails.
        """
        issues: list[ValidationIssue] = []

        # Level 1: Schema validation
        model = self._validate_schema(data, issues)

        if model is not None:
            # Level 2: Referential integrity
            self._validate_referential(model, issues)

            # Level 3: Semantic checks
            self._validate_semantic(model, issues)

        # Determine overall validity (no errors means valid).
        has_errors = any(i.severity == "error" for i in issues)
        result = ValidationResult(valid=not has_errors, issues=issues)
        return model, result

    # -- Level 1: Schema validation ----------------------------------------

    def _validate_schema(
        self, data: dict[str, Any], issues: list[ValidationIssue]
    ) -> ModelSchema | None:
        """Validate *data* against the Pydantic ``ModelSchema``.

        Returns the parsed model on success, or ``None`` on failure.
        """
        try:
            return ModelSchema.model_validate(data)
        except ValidationError as exc:
            for error in exc.errors():
                loc = ".".join(str(part) for part in error["loc"])
                issues.append(
                    ValidationIssue(
                        severity="error",
                        category="schema",
                        message=f"{loc}: {error['msg']}",
                        field=loc or None,
                    )
                )
            return None

    # -- Level 2: Referential integrity ------------------------------------

    def _validate_referential(
        self, model: ModelSchema, issues: list[ValidationIssue]
    ) -> None:
        """Check cross-references: block IDs in connections, port names."""
        # Build a set of block IDs for fast lookup.
        block_ids = {block.id for block in model.blocks}
        block_by_id = {block.id: block for block in model.blocks}

        # Check block types against the registry.
        for block in model.blocks:
            if block.type not in self._registry:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        category="referential",
                        message=f"Unknown block type '{block.type}'.",
                        block_id=block.id,
                        field="type",
                    )
                )

        # Check connections.
        for conn in model.connections:
            # Source block exists?
            if conn.source_block not in block_ids:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        category="referential",
                        message=(
                            f"Connection references source block "
                            f"'{conn.source_block}' which does not exist."
                        ),
                        block_id=conn.source_block,
                        field="source_block",
                    )
                )
            else:
                # Source port valid?
                src_block_schema = block_by_id[conn.source_block]
                self._check_port(
                    src_block_schema, conn.source_port, "output", issues
                )

            # Target block exists?
            if conn.target_block not in block_ids:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        category="referential",
                        message=(
                            f"Connection references target block "
                            f"'{conn.target_block}' which does not exist."
                        ),
                        block_id=conn.target_block,
                        field="target_block",
                    )
                )
            else:
                # Target port valid?
                tgt_block_schema = block_by_id[conn.target_block]
                self._check_port(
                    tgt_block_schema, conn.target_port, "input", issues
                )

    def _check_port(
        self,
        block_schema: Any,
        port_name: str,
        direction: str,
        issues: list[ValidationIssue],
    ) -> None:
        """Verify that *port_name* is a valid port on the given block type.

        Uses the registry to inspect port definitions on the block class.
        If the block type is unknown (already flagged), skip silently.
        """
        if block_schema.type not in self._registry:
            return  # Already flagged as unknown type.

        try:
            block_cls = self._registry.get(block_schema.type)
        except KeyError:
            return

        if direction == "output":
            port_defs = {p.name for p in block_cls._output_port_defs}
        else:
            port_defs = {p.name for p in block_cls._input_port_defs}

        if port_name not in port_defs:
            issues.append(
                ValidationIssue(
                    severity="error",
                    category="referential",
                    message=(
                        f"Block '{block_schema.id}' (type '{block_schema.type}') "
                        f"has no {direction} port '{port_name}'. "
                        f"Available: {sorted(port_defs)}."
                    ),
                    block_id=block_schema.id,
                    field=f"{direction}_port",
                )
            )

    # -- Level 3: Semantic checks ------------------------------------------

    def _validate_semantic(
        self, model: ModelSchema, issues: list[ValidationIssue]
    ) -> None:
        """Attempt to compile the model, catching domain errors as issues.

        This check verifies:
        - Unconnected input ports (raised as warnings, not errors)
        - Algebraic loops (raised as warnings)
        """
        # Only attempt semantic validation if all block types are known.
        # If there are unknown types, compilation would fail anyway.
        for block in model.blocks:
            if block.type not in self._registry:
                return

        try:
            from blocksim.core.system import (
                DynamicSystem,
                InvalidConnectionError,
            )
            from blocksim.core.graph import AlgebraicLoopError

            system = DynamicSystem()

            # Instantiate blocks.
            for block_schema in model.blocks:
                try:
                    block_instance = self._registry.create(
                        block_schema.type,
                        block_id=block_schema.id,
                        **block_schema.params,
                    )
                    system.add_block(block_instance)
                except Exception as exc:
                    issues.append(
                        ValidationIssue(
                            severity="warning",
                            category="semantic",
                            message=(
                                f"Failed to instantiate block '{block_schema.id}' "
                                f"(type '{block_schema.type}'): {exc}"
                            ),
                            block_id=block_schema.id,
                        )
                    )
                    return  # Can't continue if a block can't be created.

            # Wire connections.
            for conn in model.connections:
                try:
                    system.connect(
                        conn.source_block,
                        conn.source_port,
                        conn.target_block,
                        conn.target_port,
                    )
                except Exception:
                    pass  # Connection errors already caught at referential level.

            # Try compile — catches algebraic loops and unconnected ports.
            try:
                system.compile()
            except AlgebraicLoopError as exc:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        category="semantic",
                        message=str(exc),
                    )
                )
            except InvalidConnectionError as exc:
                # Unconnected ports — report as warnings.
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        category="semantic",
                        message=str(exc),
                    )
                )

        except Exception as exc:
            # Catch-all: semantic validation should never crash the validator.
            issues.append(
                ValidationIssue(
                    severity="warning",
                    category="semantic",
                    message=f"Unexpected error during semantic validation: {exc}",
                )
            )
