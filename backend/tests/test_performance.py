"""Performance validation tests (T-5.2).

Verifies non-functional requirements:
- NFR: 100-block model simulates 1000 steps in < 5 seconds
- NFR: New block type requires < 50 lines of code (measured from existing blocks)
- Benchmark: RK4 vs Euler performance comparison
"""

from __future__ import annotations

import inspect
import time

import pytest

from blocksim.blocks.delays import Delay
from blocksim.blocks.electrical import Capacitor, Inductor, Resistor, VoltageSource
from blocksim.blocks.math_ops import Derivative, Gain, Integrator, Multiply, Sum
from blocksim.blocks.sinks import Display, Scope
from blocksim.blocks.sources import ConstantSource, RampSource, SineSource, StepSource
from blocksim.core.solver import EulerSolver, RK4Solver
from blocksim.core.system import DynamicSystem


# ---------------------------------------------------------------------------
# NFR: 100-block model simulates 1000 steps in < 5 seconds
# ---------------------------------------------------------------------------


class TestPerformance100Block:
    """Validate that a 100-block model simulates 1000 steps in < 5 seconds."""

    def _build_100_block_system(self) -> DynamicSystem:
        """Build a 100-block model: source → chain of 98 Gain(1.0) → Scope.

        This creates a 100-block system with 99 connections, exercising
        the full simulation pipeline.
        """
        sys = DynamicSystem()

        # 1 source
        source = ConstantSource(value=1.0, block_id="source_0")
        sys.add_block(source)

        # 98 gain blocks (algebraic, no state)
        for i in range(1, 99):
            gain = Gain(k=1.0, block_id=f"gain_{i}")
            sys.add_block(gain)

        # 1 scope at the end
        scope = Scope(block_id="scope_99")
        sys.add_block(scope)

        # Wire: source → gain_1 → gain_2 → ... → gain_98 → scope
        sys.connect("source_0", "out", "gain_1", "in")
        for i in range(1, 98):
            sys.connect(f"gain_{i}", "out", f"gain_{i + 1}", "in")
        sys.connect("gain_98", "out", "scope_99", "in")

        sys.compile()
        return sys

    def test_100_block_simulation_under_5_seconds(self) -> None:
        """NFR: 100-block model, 1000 steps must complete in < 5 seconds."""
        sys = self._build_100_block_system()

        dt = 0.001
        t_end = dt * 1000  # 1000 steps

        start = time.perf_counter()
        result = sys.simulate(t_span=(0.0, t_end), dt=dt, solver="rk4")
        elapsed = time.perf_counter() - start

        assert elapsed < 5.0, (
            f"100-block model with 1000 steps took {elapsed:.2f}s "
            f"(must be < 5.0s)"
        )
        # Verify result is valid
        assert len(result.time) == 1001  # 1000 steps + 1 initial
        # Check last gain block output (scope has no output ports)
        assert result.outputs["gain_98.out"][-1] == pytest.approx(1.0)

    def test_100_block_with_stateful_blocks(self) -> None:
        """Performance test with a mix of stateful + stateless blocks."""
        sys = DynamicSystem()

        # 10 constant sources
        for i in range(10):
            sys.add_block(ConstantSource(value=1.0, block_id=f"src_{i}"))

        # 10 integrators (stateful)
        for i in range(10):
            sys.add_block(Integrator(x0=0.0, block_id=f"int_{i}"))
            sys.connect(f"src_{i}", "out", f"int_{i}", "in")

        # 80 gain blocks, chained pairs off each integrator
        gain_idx = 0
        for i in range(10):
            prev = f"int_{i}"
            for j in range(8):
                gid = f"gain_{gain_idx}"
                sys.add_block(Gain(k=1.0, block_id=gid))
                sys.connect(prev, "out", gid, "in")
                prev = gid
                gain_idx += 1

        sys.compile()
        assert len(sys.blocks) == 100

        dt = 0.001
        t_end = dt * 1000

        start = time.perf_counter()
        result = sys.simulate(t_span=(0.0, t_end), dt=dt, solver="rk4")
        elapsed = time.perf_counter() - start

        assert elapsed < 5.0, (
            f"100-block mixed model with 1000 steps took {elapsed:.2f}s "
            f"(must be < 5.0s)"
        )


# ---------------------------------------------------------------------------
# NFR: New block type requires < 50 lines of code
# ---------------------------------------------------------------------------


class TestExtensibilityLOC:
    """Verify that existing block implementations are < 50 lines each,
    proving the extensibility requirement is achievable."""

    @pytest.mark.parametrize(
        "cls",
        [
            ConstantSource,
            StepSource,
            SineSource,
            RampSource,
            Gain,
            Sum,
            Multiply,
            Integrator,
            Derivative,
            Scope,
            Display,
            Delay,
            VoltageSource,
            Resistor,
            Inductor,
            Capacitor,
        ],
    )
    def test_block_under_50_lines(self, cls: type) -> None:
        """Each block class must be implementable in < 50 lines of code."""
        source = inspect.getsource(cls)
        lines = [
            line for line in source.split("\n")
            if line.strip() and not line.strip().startswith("#")
        ]
        # We count non-empty, non-comment lines (code + docstrings)
        assert len(lines) < 50, (
            f"{cls.__name__} has {len(lines)} non-empty lines "
            f"(must be < 50 for extensibility)"
        )

    def test_median_block_size(self) -> None:
        """Verify the median block size is well under 50 lines."""
        all_blocks = [
            ConstantSource, StepSource, SineSource, RampSource,
            Gain, Sum, Multiply, Integrator, Derivative,
            Scope, Display, Delay, VoltageSource, Resistor,
            Inductor, Capacitor,
        ]
        sizes = []
        for cls in all_blocks:
            source = inspect.getsource(cls)
            lines = [
                line for line in source.split("\n")
                if line.strip() and not line.strip().startswith("#")
            ]
            sizes.append(len(lines))

        sizes.sort()
        median = sizes[len(sizes) // 2]
        assert median < 30, f"Median block size is {median} lines (should be < 30)"


# ---------------------------------------------------------------------------
# Benchmark: RK4 vs Euler performance
# ---------------------------------------------------------------------------


class TestSolverBenchmark:
    """Compare RK4 vs Euler performance for the same model."""

    def _build_integrator_chain(self) -> DynamicSystem:
        """Build a simple integrator chain for benchmarking."""
        sys = DynamicSystem()
        sys.add_block(ConstantSource(value=1.0, block_id="src"))
        sys.add_block(Integrator(x0=0.0, block_id="int1"))
        sys.add_block(Integrator(x0=0.0, block_id="int2"))
        sys.add_block(Scope(block_id="scope"))
        sys.connect("src", "out", "int1", "in")
        sys.connect("int1", "out", "int2", "in")
        sys.connect("int2", "out", "scope", "in")
        sys.compile()
        return sys

    def test_euler_vs_rk4_both_complete(self) -> None:
        """Both solvers should complete without error."""
        for solver_name in ["euler", "rk4"]:
            sys = self._build_integrator_chain()
            result = sys.simulate(
                t_span=(0.0, 1.0), dt=0.001, solver=solver_name
            )
            assert len(result.time) == 1001

    def test_rk4_more_accurate_than_euler(self) -> None:
        """RK4 should produce more accurate results than Euler for same dt.

        For dy/dt = 1, ∫∫1 dt dt = t²/2.
        At t=1.0, int2 should output 0.5.
        """
        dt = 0.01  # Relatively large to show accuracy difference

        # Euler
        sys_euler = self._build_integrator_chain()
        result_euler = sys_euler.simulate(
            t_span=(0.0, 1.0), dt=dt, solver="euler"
        )
        euler_final = result_euler.outputs["int2.out"][-1]

        # RK4
        sys_rk4 = self._build_integrator_chain()
        result_rk4 = sys_rk4.simulate(
            t_span=(0.0, 1.0), dt=dt, solver="rk4"
        )
        rk4_final = result_rk4.outputs["int2.out"][-1]

        analytical = 0.5  # t²/2 at t=1

        euler_error = abs(euler_final - analytical)
        rk4_error = abs(rk4_final - analytical)

        # RK4 should be significantly more accurate
        assert rk4_error < euler_error, (
            f"RK4 error ({rk4_error:.6e}) should be less than "
            f"Euler error ({euler_error:.6e})"
        )

    def test_benchmark_timing(self) -> None:
        """Benchmark: time both solvers for the same simulation."""
        n_steps = 10000
        dt = 0.0001
        t_end = dt * n_steps

        # Euler
        sys_euler = self._build_integrator_chain()
        start = time.perf_counter()
        sys_euler.simulate(t_span=(0.0, t_end), dt=dt, solver="euler")
        euler_time = time.perf_counter() - start

        # RK4
        sys_rk4 = self._build_integrator_chain()
        start = time.perf_counter()
        sys_rk4.simulate(t_span=(0.0, t_end), dt=dt, solver="rk4")
        rk4_time = time.perf_counter() - start

        # RK4 is typically 3-4x slower than Euler (4 derivative evals vs 1)
        # But both should complete in reasonable time
        assert euler_time < 10.0, f"Euler took {euler_time:.2f}s"
        assert rk4_time < 10.0, f"RK4 took {rk4_time:.2f}s"

        # RK4 is expected to be slower, but not catastrophically so
        if rk4_time > 0 and euler_time > 0:
            ratio = rk4_time / euler_time
            # Sanity check: RK4 shouldn't be more than 10x slower
            assert ratio < 10.0, (
                f"RK4 is {ratio:.1f}x slower than Euler (should be < 10x)"
            )
