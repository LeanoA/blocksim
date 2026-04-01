"""Tests for Block ABC, Port system, and Connection model.

Covers:
- Port creation (InputPort / OutputPort factories)
- Block subclassing and compute()
- State management for stateful blocks
- PortAlreadyConnectedError on duplicate connections
- Block self-description (describe())
"""

from __future__ import annotations

import numpy as np
import pytest

from blocksim.core.block import (
    Block,
    Connection,
    InputPort,
    OutputPort,
    Port,
    PortAlreadyConnectedError,
    PortDirection,
)


# ---------------------------------------------------------------------------
# Concrete test blocks
# ---------------------------------------------------------------------------


class GainBlock(Block):
    """A simple stateless block: out = k * in."""

    _input_port_defs = [InputPort("in")]
    _output_port_defs = [OutputPort("out")]

    def __init__(self, k: float = 1.0, **kwargs):
        super().__init__(params={"k": k}, **kwargs)

    def compute(self, t: float) -> None:
        self.set_output("out", self.params["k"] * self.get_input("in"))


class IntegratorBlock(Block):
    """A stateful block with state_size=1: state tracks integral of input."""

    _input_port_defs = [InputPort("in")]
    _output_port_defs = [OutputPort("out")]

    def __init__(self, x0: float = 0.0, **kwargs):
        super().__init__(params={"x0": x0}, **kwargs)

    @property
    def state_size(self) -> int:
        return 1

    def initialize(self, t0: float) -> np.ndarray:
        return np.array([self.params["x0"]], dtype=np.float64)

    def compute(self, t: float) -> None:
        self.set_output("out", self._state[0])

    def derivatives(self, t: float, state: np.ndarray) -> np.ndarray:
        return np.array([self.get_input("in")], dtype=np.float64)


# ---------------------------------------------------------------------------
# Port tests
# ---------------------------------------------------------------------------


class TestPort:
    """Tests for Port, InputPort, and OutputPort."""

    def test_input_port_factory(self):
        p = InputPort("x")
        assert p.name == "x"
        assert p.direction is PortDirection.IN
        assert p.dtype is float

    def test_output_port_factory(self):
        p = OutputPort("y")
        assert p.name == "y"
        assert p.direction is PortDirection.OUT
        assert p.dtype is float

    def test_port_custom_dtype(self):
        p = Port(name="z", direction=PortDirection.IN, dtype=complex)
        assert p.dtype is complex


# ---------------------------------------------------------------------------
# Connection tests
# ---------------------------------------------------------------------------


class TestConnection:
    """Tests for Connection dataclass."""

    def test_connection_fields(self):
        c = Connection("blk1", "out", "blk2", "in")
        assert c.source_block_id == "blk1"
        assert c.source_port == "out"
        assert c.target_block_id == "blk2"
        assert c.target_port == "in"

    def test_connection_immutable(self):
        c = Connection("a", "out", "b", "in")
        with pytest.raises(AttributeError):
            c.source_block_id = "changed"  # type: ignore[misc]

    def test_connection_equality(self):
        c1 = Connection("a", "out", "b", "in")
        c2 = Connection("a", "out", "b", "in")
        assert c1 == c2


# ---------------------------------------------------------------------------
# Block ABC tests
# ---------------------------------------------------------------------------


class TestBlockABC:
    """Tests for the Block abstract base class via concrete subclasses."""

    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            Block()  # type: ignore[abstract]

    def test_gain_block_creation(self):
        g = GainBlock(k=2.5, block_id="gain1")
        assert g.id == "gain1"
        assert g.params == {"k": 2.5}
        assert "in" in g.input_ports
        assert "out" in g.output_ports
        assert g.state_size == 0

    def test_gain_block_compute(self):
        g = GainBlock(k=3.0)
        g.set_input("in", 4.0)
        g.compute(t=0.0)
        assert g.get_output("out") == pytest.approx(12.0)

    def test_auto_generated_id(self):
        g = GainBlock()
        assert len(g.id) == 12  # UUID hex[:12]

    def test_block_type_property(self):
        g = GainBlock()
        assert g.block_type == "GainBlock"


# ---------------------------------------------------------------------------
# Stateful block tests
# ---------------------------------------------------------------------------


class TestStatefulBlock:
    """Tests for stateful block (Integrator-like)."""

    def test_state_size(self):
        integ = IntegratorBlock(x0=1.0)
        assert integ.state_size == 1

    def test_initialize(self):
        integ = IntegratorBlock(x0=5.0)
        state = integ.initialize(t0=0.0)
        np.testing.assert_array_equal(state, [5.0])

    def test_get_set_state(self):
        integ = IntegratorBlock()
        integ.set_state(np.array([42.0]))
        np.testing.assert_array_equal(integ.get_state(), [42.0])

    def test_state_is_copy(self):
        integ = IntegratorBlock()
        integ.set_state(np.array([1.0]))
        s = integ.get_state()
        s[0] = 999.0  # mutate the copy
        assert integ.get_state()[0] == pytest.approx(1.0)

    def test_derivatives(self):
        integ = IntegratorBlock()
        integ.set_input("in", 7.0)
        dy = integ.derivatives(t=0.0, state=np.array([0.0]))
        np.testing.assert_array_equal(dy, [7.0])

    def test_compute_outputs_state(self):
        integ = IntegratorBlock()
        integ.set_state(np.array([3.14]))
        integ.compute(t=0.0)
        assert integ.get_output("out") == pytest.approx(3.14)


# ---------------------------------------------------------------------------
# Port connection / error tests
# ---------------------------------------------------------------------------


class TestPortConnection:
    """Tests for port connection tracking and PortAlreadyConnectedError."""

    def test_mark_input_connected(self):
        g = GainBlock()
        g.mark_input_connected("in")
        assert "in" in g._connected_inputs

    def test_duplicate_connection_raises(self):
        g = GainBlock(block_id="gain1")
        g.mark_input_connected("in")
        with pytest.raises(PortAlreadyConnectedError) as exc_info:
            g.mark_input_connected("in")
        assert "gain1" in str(exc_info.value)
        assert "'in'" in str(exc_info.value)

    def test_port_already_connected_error_attributes(self):
        err = PortAlreadyConnectedError("blk", "port_x")
        assert err.block_id == "blk"
        assert err.port_name == "port_x"

    def test_invalid_port_name_raises_key_error(self):
        g = GainBlock()
        with pytest.raises(KeyError, match="nonexistent"):
            g.mark_input_connected("nonexistent")

    def test_unmark_connected(self):
        g = GainBlock()
        g.mark_input_connected("in")
        g.unmark_input_connected("in")
        # Now we can connect again without error.
        g.mark_input_connected("in")


# ---------------------------------------------------------------------------
# Describe / introspection tests
# ---------------------------------------------------------------------------


class TestBlockDescribe:
    """Tests for Block.describe() introspection."""

    def test_describe_contains_expected_keys(self):
        g = GainBlock(k=2.0, block_id="g1")
        desc = g.describe()
        assert desc["id"] == "g1"
        assert desc["type"] == "GainBlock"
        assert desc["params"] == {"k": 2.0}
        assert desc["state_size"] == 0
        assert len(desc["input_ports"]) == 1
        assert len(desc["output_ports"]) == 1

    def test_describe_port_dtypes(self):
        g = GainBlock()
        desc = g.describe()
        assert desc["input_ports"][0]["dtype"] == "float"
        assert desc["output_ports"][0]["dtype"] == "float"


# ---------------------------------------------------------------------------
# Default implementations for stateless blocks
# ---------------------------------------------------------------------------


class TestDefaultStatelessBehaviour:
    """Ensure stateless blocks have sensible defaults for state methods."""

    def test_default_initialize_returns_empty(self):
        g = GainBlock()
        state = g.initialize(t0=0.0)
        assert len(state) == 0

    def test_default_derivatives_returns_empty(self):
        g = GainBlock()
        dy = g.derivatives(t=0.0, state=np.array([]))
        assert len(dy) == 0
