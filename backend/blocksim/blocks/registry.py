"""Block registry: central catalogue of available block types.

The :class:`BlockRegistry` provides a singleton-style registry that maps
block type names (strings) to their implementing classes.  All built-in
blocks are auto-registered on import.

Usage::

    from blocksim.blocks.registry import registry

    # List available blocks
    registry.list_all()  # ['ConstantSource', 'StepSource', ...]

    # Instantiate a block by name
    cls = registry.get("Gain")
    block = cls(k=2.0, block_id="g1")
"""

from __future__ import annotations

from typing import Any

from blocksim.core.block import Block


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class BlockRegistry:
    """Central registry mapping block type names to classes.

    The registry supports:
    - ``register(name, cls)`` — register a block class under a name
    - ``get(name)`` — retrieve a block class by name
    - ``list_all()`` — list all registered block names
    - ``create(name, **kwargs)`` — instantiate a block by name
    """

    def __init__(self) -> None:
        self._registry: dict[str, type[Block]] = {}

    def register(self, name: str, cls: type[Block]) -> None:
        """Register a block class under *name*.

        Parameters
        ----------
        name:
            The type name string (typically the class name).
        cls:
            The block class (must be a subclass of :class:`Block`).

        Raises
        ------
        TypeError
            If *cls* is not a subclass of :class:`Block`.
        """
        if not (isinstance(cls, type) and issubclass(cls, Block)):
            raise TypeError(
                f"Cannot register {cls!r}: must be a subclass of Block."
            )
        self._registry[name] = cls

    def get(self, name: str) -> type[Block]:
        """Retrieve a block class by *name*.

        Parameters
        ----------
        name:
            The registered type name.

        Returns
        -------
        type[Block]
            The block class.

        Raises
        ------
        KeyError
            If *name* is not registered.
        """
        if name not in self._registry:
            available = ", ".join(sorted(self._registry.keys()))
            raise KeyError(
                f"Unknown block type '{name}'. Available: {available}"
            )
        return self._registry[name]

    def list_all(self) -> list[str]:
        """Return a sorted list of all registered block type names."""
        return sorted(self._registry.keys())

    def create(self, name: str, **kwargs: Any) -> Block:
        """Instantiate a block by type name.

        Parameters
        ----------
        name:
            The registered type name.
        **kwargs:
            Arguments forwarded to the block constructor.

        Returns
        -------
        Block
            A new block instance.
        """
        cls = self.get(name)
        return cls(**kwargs)

    def __contains__(self, name: str) -> bool:
        return name in self._registry

    def __len__(self) -> int:
        return len(self._registry)

    def __repr__(self) -> str:
        return f"BlockRegistry({len(self._registry)} blocks: {self.list_all()})"


# ---------------------------------------------------------------------------
# Singleton instance
# ---------------------------------------------------------------------------

registry = BlockRegistry()


# ---------------------------------------------------------------------------
# Auto-register all built-in blocks
# ---------------------------------------------------------------------------

def _auto_register() -> None:
    """Import and register all built-in block types."""
    from blocksim.blocks.sources import (
        ConstantSource,
        StepSource,
        SineSource,
        RampSource,
    )
    from blocksim.blocks.math_ops import (
        Gain,
        Sum,
        Multiply,
        Integrator,
        Derivative,
    )
    from blocksim.blocks.sinks import Scope, Display
    from blocksim.blocks.delays import Delay
    from blocksim.blocks.electrical import (
        VoltageSource,
        Resistor,
        Inductor,
        Capacitor,
    )

    block_classes: list[type[Block]] = [
        # Sources
        ConstantSource,
        StepSource,
        SineSource,
        RampSource,
        # Math & continuous
        Gain,
        Sum,
        Multiply,
        Integrator,
        Derivative,
        # Sinks
        Scope,
        Display,
        # Utility
        Delay,
        # Electrical
        VoltageSource,
        Resistor,
        Inductor,
        Capacitor,
    ]
    for cls in block_classes:
        registry.register(cls.__name__, cls)


_auto_register()
