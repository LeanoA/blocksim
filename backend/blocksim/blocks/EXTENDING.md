# Extending BlockSim: Creating Custom Blocks

This guide explains how to create a new block type for BlockSim. Each block follows the same pattern: extend the `Block` ABC, define ports, implement `compute()`, and register it.

## Quick Start — Template Block

Here's a minimal template you can copy-paste to create a new block:

```python
"""My custom block module."""
from blocksim.core.block import Block, InputPort, OutputPort

class MyCustomBlock(Block):
    """One-line description of what this block does.

    Parameters
    ----------
    my_param:
        Description of the parameter.
    """

    _input_port_defs = [InputPort("in")]
    _output_port_defs = [OutputPort("out")]

    def __init__(self, my_param: float = 1.0, **kwargs) -> None:
        super().__init__(params={"my_param": my_param}, **kwargs)

    def compute(self, t: float) -> None:
        value = self.get_input("in")
        result = value * self.params["my_param"]
        self.set_output("out", result)
```

That's it! A basic block in ~15 lines of code.

## Step-by-Step Guide

### Step 1: Extend the Block ABC

All blocks inherit from `blocksim.core.block.Block`:

```python
from blocksim.core.block import Block, InputPort, OutputPort
import numpy as np  # only needed for stateful blocks

class MyBlock(Block):
    ...
```

### Step 2: Define Ports

Declare ports as class-level lists using the `InputPort()` and `OutputPort()` factories:

```python
class MyBlock(Block):
    # A block with two inputs and one output:
    _input_port_defs = [InputPort("in1"), InputPort("in2")]
    _output_port_defs = [OutputPort("out")]
```

Port rules:
- Each input port can receive **exactly one** connection
- Output ports can fan out to multiple connections
- Port names must be unique within the block
- Use descriptive names (`"voltage"`, `"current"`, not `"x"`, `"y"`)

### Step 3: Implement `__init__`

Store parameters in `self.params` dict via the base class:

```python
def __init__(self, gain: float = 1.0, offset: float = 0.0, **kwargs) -> None:
    super().__init__(params={"gain": gain, "offset": offset}, **kwargs)
```

**Important**: Always accept `**kwargs` and forward to `super().__init__()`. This lets the system pass `block_id` and other metadata.

### Step 4: Implement `compute(t)`

This is the core logic. Read inputs, compute, write outputs:

```python
def compute(self, t: float) -> None:
    # Read inputs
    x = self.get_input("in1")
    y = self.get_input("in2")

    # Compute
    result = self.params["gain"] * x + self.params["offset"] * y

    # Write output
    self.set_output("out", result)
```

### Step 5 (Optional): Add State for ODE Blocks

If your block has continuous-time dynamics (like an integrator or capacitor), override three additional methods:

```python
import numpy as np

class LeakyIntegrator(Block):
    """Leaky integrator: dx/dt = input - leak_rate * x."""

    _input_port_defs = [InputPort("in")]
    _output_port_defs = [OutputPort("out")]

    def __init__(self, x0: float = 0.0, leak_rate: float = 0.1, **kwargs) -> None:
        super().__init__(params={"x0": x0, "leak_rate": leak_rate}, **kwargs)

    @property
    def state_size(self) -> int:
        """Number of ODE state variables (1 for this block)."""
        return 1

    def initialize(self, t0: float) -> np.ndarray:
        """Return initial state vector."""
        return np.array([self.params["x0"]], dtype=np.float64)

    def compute(self, t: float) -> None:
        """Output is the current state value."""
        self.set_output("out", self._state[0])

    def derivatives(self, t: float, state: np.ndarray) -> np.ndarray:
        """dx/dt = input - leak_rate * x."""
        x = state[0]
        u = self.get_input("in")
        leak = self.params["leak_rate"]
        return np.array([u - leak * x], dtype=np.float64)
```

### Step 6: Register in BlockRegistry

Add your block to the registry so the API and frontend can discover it:

```python
from blocksim.blocks.registry import registry
from my_module import MyBlock

registry.register("MyBlock", MyBlock)
```

For built-in blocks, add to the `_auto_register()` function in `blocksim/blocks/registry.py`.

## Block Categories

| Category | Has Inputs? | Has Outputs? | Has State? | Examples |
|----------|:-----------:|:------------:|:----------:|----------|
| Source | ✗ | ✓ | ✗ | ConstantSource, SineSource, StepSource |
| Math | ✓ | ✓ | ✗ | Gain, Sum, Multiply |
| Continuous | ✓ | ✓ | ✓ | Integrator, Derivative |
| Electrical | ✓ | ✓ | ✓/✗ | Resistor (✗), Inductor (✓), Capacitor (✓) |
| Sink | ✓ | ✗ | ✗ | Scope, Display |
| Utility | ✓ | ✓ | ✗ | Delay |

## Complete Example: Saturation Block

Here's a real-world example — a block that clamps its output:

```python
from blocksim.core.block import Block, InputPort, OutputPort


class Saturation(Block):
    """Clamps the input signal to [lower, upper] bounds.

    Parameters
    ----------
    lower:
        Lower saturation limit.
    upper:
        Upper saturation limit.
    """

    _input_port_defs = [InputPort("in")]
    _output_port_defs = [OutputPort("out")]

    def __init__(
        self,
        lower: float = -1.0,
        upper: float = 1.0,
        **kwargs,
    ) -> None:
        if lower >= upper:
            raise ValueError(f"lower ({lower}) must be < upper ({upper})")
        super().__init__(params={"lower": lower, "upper": upper}, **kwargs)

    def compute(self, t: float) -> None:
        value = self.get_input("in")
        clamped = max(self.params["lower"], min(self.params["upper"], value))
        self.set_output("out", clamped)
```

## Testing Your Block

Create a test in `tests/test_blocks/`:

```python
import pytest
from my_module import Saturation

class TestSaturation:
    def test_pass_through(self):
        b = Saturation(lower=-10, upper=10, block_id="sat1")
        b.set_input("in", 5.0)
        b.compute(0.0)
        assert b.get_output("out") == 5.0

    def test_upper_clamp(self):
        b = Saturation(lower=-10, upper=10, block_id="sat1")
        b.set_input("in", 15.0)
        b.compute(0.0)
        assert b.get_output("out") == 10.0

    def test_lower_clamp(self):
        b = Saturation(lower=-10, upper=10, block_id="sat1")
        b.set_input("in", -15.0)
        b.compute(0.0)
        assert b.get_output("out") == -10.0
```

## Checklist

- [ ] Extend `Block` ABC
- [ ] Define `_input_port_defs` and `_output_port_defs`
- [ ] Implement `__init__` with params and `**kwargs`
- [ ] Implement `compute(t)` method
- [ ] (If stateful) Override `state_size`, `initialize()`, `derivatives()`
- [ ] Register in `BlockRegistry`
- [ ] Write tests
