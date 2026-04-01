"""Tests for sink blocks (blocks/sinks.py).

Covers:
- Scope: records time-series history
- Display: stores last value only
- Both are pure sinks (no output ports)
"""

from __future__ import annotations

import pytest

from blocksim.blocks.sinks import Display, Scope


# ---------------------------------------------------------------------------
# Scope
# ---------------------------------------------------------------------------


class TestScope:

    def test_scope_records_values(self):
        s = Scope()
        s.set_input("in", 1.0)
        s.compute(t=0.0)
        s.set_input("in", 2.0)
        s.compute(t=0.1)
        s.set_input("in", 3.0)
        s.compute(t=0.2)
        assert len(s.history) == 3
        assert s.history[0] == (0.0, 1.0)
        assert s.history[1] == (0.1, 2.0)
        assert s.history[2] == (0.2, 3.0)

    def test_scope_times_property(self):
        s = Scope()
        s.set_input("in", 5.0)
        s.compute(t=0.0)
        s.set_input("in", 10.0)
        s.compute(t=0.5)
        assert s.times == [0.0, 0.5]

    def test_scope_values_property(self):
        s = Scope()
        s.set_input("in", 5.0)
        s.compute(t=0.0)
        s.set_input("in", 10.0)
        s.compute(t=0.5)
        assert s.values == [5.0, 10.0]

    def test_scope_clear(self):
        s = Scope()
        s.set_input("in", 1.0)
        s.compute(t=0.0)
        assert len(s.history) == 1
        s.clear()
        assert len(s.history) == 0

    def test_scope_no_output_ports(self):
        s = Scope()
        assert len(s.output_ports) == 0

    def test_scope_has_input_port(self):
        s = Scope()
        assert "in" in s.input_ports

    def test_scope_stateless(self):
        s = Scope()
        assert s.state_size == 0

    def test_scope_empty_history(self):
        s = Scope()
        assert s.history == []
        assert s.times == []
        assert s.values == []


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------


class TestDisplay:

    def test_display_stores_last_value(self):
        d = Display()
        d.set_input("in", 42.0)
        d.compute(t=1.0)
        assert d.last_value == pytest.approx(42.0)
        assert d.last_time == pytest.approx(1.0)

    def test_display_overwrites_previous(self):
        d = Display()
        d.set_input("in", 1.0)
        d.compute(t=0.0)
        d.set_input("in", 2.0)
        d.compute(t=0.1)
        assert d.last_value == pytest.approx(2.0)
        assert d.last_time == pytest.approx(0.1)

    def test_display_initial_state(self):
        d = Display()
        assert d.last_value is None
        assert d.last_time is None

    def test_display_no_output_ports(self):
        d = Display()
        assert len(d.output_ports) == 0

    def test_display_has_input_port(self):
        d = Display()
        assert "in" in d.input_ports
