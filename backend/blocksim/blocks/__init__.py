"""Block library: sources, math, continuous, delays, sinks, electrical, and registry.

Import the registry singleton for block discovery::

    from blocksim.blocks import registry
    registry.list_all()
"""

from blocksim.blocks.delays import Delay
from blocksim.blocks.electrical import Capacitor, Inductor, Resistor, VoltageSource
from blocksim.blocks.math_ops import Derivative, Gain, Integrator, Multiply, Sum
from blocksim.blocks.registry import BlockRegistry, registry
from blocksim.blocks.sinks import Display, Scope
from blocksim.blocks.sources import ConstantSource, RampSource, SineSource, StepSource

__all__ = [
    # Sources
    "ConstantSource",
    "StepSource",
    "SineSource",
    "RampSource",
    # Math & continuous
    "Gain",
    "Sum",
    "Multiply",
    "Integrator",
    "Derivative",
    # Sinks
    "Scope",
    "Display",
    # Utility
    "Delay",
    # Electrical
    "VoltageSource",
    "Resistor",
    "Inductor",
    "Capacitor",
    # Registry
    "BlockRegistry",
    "registry",
]
