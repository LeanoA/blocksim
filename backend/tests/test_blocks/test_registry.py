"""Tests for BlockRegistry (blocks/registry.py).

Covers:
- Auto-registration of all built-in blocks
- register / get / list_all / create
- Error handling for unknown types and invalid classes
- Singleton instance behavior
"""

from __future__ import annotations

import pytest

from blocksim.blocks.registry import BlockRegistry, registry
from blocksim.core.block import Block


# ---------------------------------------------------------------------------
# Auto-registration
# ---------------------------------------------------------------------------


class TestAutoRegistration:

    def test_registry_has_all_builtin_blocks(self):
        expected = [
            "ConstantSource", "StepSource", "SineSource", "RampSource",
            "Gain", "Sum", "Multiply", "Integrator", "Derivative",
            "Scope", "Display", "Delay",
        ]
        for name in expected:
            assert name in registry, f"{name} not found in registry"

    def test_registry_length(self):
        assert len(registry) >= 12

    def test_list_all_returns_sorted(self):
        names = registry.list_all()
        assert names == sorted(names)


# ---------------------------------------------------------------------------
# Get and create
# ---------------------------------------------------------------------------


class TestRegistryLookup:

    def test_get_returns_class(self):
        cls = registry.get("Gain")
        assert issubclass(cls, Block)

    def test_get_unknown_raises(self):
        with pytest.raises(KeyError, match="Unknown block type"):
            registry.get("NonExistent")

    def test_create_instantiates_block(self):
        block = registry.create("ConstantSource", value=42.0, block_id="c1")
        assert block.id == "c1"
        assert block.params["value"] == 42.0
        block.compute(t=0.0)
        assert block.get_output("out") == pytest.approx(42.0)

    def test_create_integrator(self):
        block = registry.create("Integrator", x0=5.0)
        assert block.state_size == 1
        assert block.params["x0"] == 5.0

    def test_create_sum(self):
        block = registry.create("Sum", signs="+-")
        assert block.params["signs"] == "+-"

    def test_contains(self):
        assert "Gain" in registry
        assert "FakeBlock" not in registry


# ---------------------------------------------------------------------------
# Manual registration
# ---------------------------------------------------------------------------


class TestManualRegistration:

    def test_register_new_block(self):
        reg = BlockRegistry()

        class CustomBlock(Block):
            def compute(self, t: float) -> None:
                pass

        reg.register("Custom", CustomBlock)
        assert "Custom" in reg
        assert reg.get("Custom") is CustomBlock

    def test_register_non_block_raises(self):
        reg = BlockRegistry()
        with pytest.raises(TypeError, match="must be a subclass of Block"):
            reg.register("Bad", int)  # type: ignore

    def test_register_instance_raises(self):
        reg = BlockRegistry()
        from blocksim.blocks.sources import ConstantSource
        with pytest.raises(TypeError):
            reg.register("Bad", ConstantSource())  # type: ignore — instance not class

    def test_empty_registry(self):
        reg = BlockRegistry()
        assert len(reg) == 0
        assert reg.list_all() == []

    def test_repr(self):
        reg = BlockRegistry()
        assert "BlockRegistry" in repr(reg)
        assert "0 blocks" in repr(reg)
