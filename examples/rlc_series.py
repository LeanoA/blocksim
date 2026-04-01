#!/usr/bin/env python3
"""Series RLC Circuit — Build & Simulate with BlockSim.

This example demonstrates how to:
1. Programmatically build a series RLC circuit using BlockSim blocks
2. Run a simulation with the RK4 solver
3. Print summary statistics of the results

Circuit topology (signal-flow):

    VoltageSource ──→ Sum1(+-) ──→ Sum2(+-) ──→ Inductor
                        ↑                          ↓  (I)
                        │                    ┌─────┤
                        │                    ↓     ↓
                    Resistor ←───────── I   Capacitor
                     (V_R)                   (V_C)

KVL: V_source = V_R + V_L + V_C
  ⇒  V_L = V_source - V_R - V_C  (inductor sees the remaining voltage)

Parameters:
  V_s = 10 V (DC step), R = 10 Ω, L = 1 H, C = 100 μF
  → Underdamped response with oscillatory ringing on the capacitor voltage.

Usage:
    cd backend && .venv/bin/python -m examples.rlc_series
  or:
    cd backend && .venv/bin/python ../examples/rlc_series.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

# Ensure the backend package is importable when running as a script.
_backend_dir = Path(__file__).resolve().parent.parent / "backend"
if _backend_dir.exists() and str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from blocksim.blocks.electrical import Capacitor, Inductor, Resistor, VoltageSource
from blocksim.blocks.math_ops import Sum
from blocksim.blocks.sinks import Scope
from blocksim.core.system import DynamicSystem

# ── Circuit parameters ─────────────────────────────────────────────────────
VS = 10.0      # Source voltage (V)
R = 10.0       # Resistance (Ω)
L = 1.0        # Inductance (H)
C = 100e-6     # Capacitance (F) — 100 μF

# ── Derived analytical quantities ──────────────────────────────────────────
alpha = R / (2 * L)                          # Damping coefficient
omega_0 = 1.0 / math.sqrt(L * C)            # Natural frequency
omega_d = math.sqrt(omega_0**2 - alpha**2)   # Damped frequency (if underdamped)

print("=" * 60)
print("  BlockSim — Series RLC Circuit Example")
print("=" * 60)
print(f"  V_s = {VS} V,  R = {R} Ω,  L = {L} H,  C = {C*1e6:.0f} μF")
print(f"  α   = {alpha:.2f} rad/s  (damping coefficient)")
print(f"  ω₀  = {omega_0:.2f} rad/s  (natural frequency)")
if alpha < omega_0:
    print(f"  ω_d = {omega_d:.2f} rad/s  (damped frequency)")
    print(f"  Mode: UNDERDAMPED (oscillatory)")
elif alpha == omega_0:
    print(f"  Mode: CRITICALLY DAMPED")
else:
    print(f"  Mode: OVERDAMPED")
print()

# ── Build the system ───────────────────────────────────────────────────────
sys = DynamicSystem()

# Create blocks
vsrc = VoltageSource(voltage=VS, block_id="vsrc")
sum1 = Sum(signs="+-", block_id="sum1")       # V_s - V_R
sum2 = Sum(signs="+-", block_id="sum2")       # (V_s - V_R) - V_C = V_L
inductor = Inductor(inductance=L, i0=0.0, block_id="inductor")
resistor = Resistor(resistance=R, block_id="resistor")
capacitor = Capacitor(capacitance=C, v0=0.0, block_id="capacitor")
scope_vc = Scope(block_id="scope_vc")
scope_i = Scope(block_id="scope_i")

# Add blocks to the system
for block in [vsrc, sum1, sum2, inductor, resistor, capacitor, scope_vc, scope_i]:
    sys.add_block(block)

# Wire connections (KVL signal-flow)
sys.connect("vsrc", "out", "sum1", "in1")        # V_s → Sum1
sys.connect("resistor", "out", "sum1", "in2")     # V_R → Sum1 (subtracted)
sys.connect("sum1", "out", "sum2", "in1")          # (V_s - V_R) → Sum2
sys.connect("capacitor", "out", "sum2", "in2")     # V_C → Sum2 (subtracted)
sys.connect("sum2", "out", "inductor", "in")        # V_L → Inductor
sys.connect("inductor", "out", "resistor", "in")    # I → Resistor
sys.connect("inductor", "out", "capacitor", "in")   # I → Capacitor
sys.connect("capacitor", "out", "scope_vc", "in")   # V_C → Scope
sys.connect("inductor", "out", "scope_i", "in")     # I → Scope

# Compile (topological sort + validation)
sys.compile()
print("✓ System compiled successfully")
print(f"  Blocks: {len(sys.blocks)}")
print(f"  Connections: {len(sys.connections)}")
print(f"  Execution order: {[b.id for b in sys.sorted_blocks]}")
print()

# ── Run simulation ─────────────────────────────────────────────────────────
T_END = 2.0   # 2 seconds — enough for ringing to decay to steady-state
DT = 0.0001   # 100 μs time step

print(f"Running simulation: t ∈ [0, {T_END}] s, dt = {DT*1e6:.0f} μs, solver = RK4")
result = sys.simulate(t_span=(0.0, T_END), dt=DT, solver="rk4")
print(f"✓ Simulation complete — {len(result.time)} time steps")
print()

# ── Summarize results ──────────────────────────────────────────────────────
import numpy as np

# Capacitor voltage
vc = np.array(result.outputs["capacitor.out"])
vc_final = vc[-1]
vc_max = float(np.max(vc))
vc_max_time = float(result.time[np.argmax(vc)])

# Inductor current
i_l = np.array(result.outputs["inductor.out"])
i_max = float(np.max(np.abs(i_l)))
i_max_time = float(result.time[np.argmax(np.abs(i_l))])
i_final = i_l[-1]

print("── Results Summary ──")
print(f"  Capacitor voltage (V_C):")
print(f"    Final value:   {vc_final:.4f} V  (expected: {VS:.1f} V)")
print(f"    Peak value:    {vc_max:.4f} V  at t = {vc_max_time*1e3:.2f} ms")
print(f"    Overshoot:     {(vc_max/VS - 1)*100:.1f}%")
print()
print(f"  Inductor current (I_L):")
print(f"    Peak |I|:      {i_max:.4f} A  at t = {i_max_time*1e3:.2f} ms")
print(f"    Final value:   {i_final:.6f} A  (expected: ~0 A)")
print()

# Verify against analytical steady-state
assert abs(vc_final - VS) < 0.5, f"V_C should converge to {VS}V, got {vc_final:.4f}V"
assert abs(i_final) < 0.01, f"Current should decay to ~0, got {i_final:.6f}A"
print("✓ Steady-state assertions passed")
print()

# ── Optionally save the model to JSON ──────────────────────────────────────
from blocksim.models.persistence import save_model
from blocksim.models.schemas import BlockSchema, ConnectionSchema, ModelSchema

# Re-create the model schema (same circuit, expressed as JSON-serializable data)
model = ModelSchema(
    name="Series RLC Circuit — Underdamped Step Response",
    blocks=[
        BlockSchema(id="vsrc", type="VoltageSource", params={"voltage": VS}, position=(0, 100)),
        BlockSchema(id="sum1", type="Sum", params={"signs": "+-"}, position=(150, 100)),
        BlockSchema(id="sum2", type="Sum", params={"signs": "+-"}, position=(300, 100)),
        BlockSchema(id="inductor", type="Inductor", params={"inductance": L, "i0": 0.0}, position=(450, 100)),
        BlockSchema(id="resistor", type="Resistor", params={"resistance": R}, position=(450, 250)),
        BlockSchema(id="capacitor", type="Capacitor", params={"capacitance": C, "v0": 0.0}, position=(600, 100)),
        BlockSchema(id="scope_vc", type="Scope", params={}, position=(750, 100)),
        BlockSchema(id="scope_i", type="Scope", params={}, position=(750, 250)),
    ],
    connections=[
        ConnectionSchema(source_block="vsrc", source_port="out", target_block="sum1", target_port="in1"),
        ConnectionSchema(source_block="resistor", source_port="out", target_block="sum1", target_port="in2"),
        ConnectionSchema(source_block="sum1", source_port="out", target_block="sum2", target_port="in1"),
        ConnectionSchema(source_block="capacitor", source_port="out", target_block="sum2", target_port="in2"),
        ConnectionSchema(source_block="sum2", source_port="out", target_block="inductor", target_port="in"),
        ConnectionSchema(source_block="inductor", source_port="out", target_block="resistor", target_port="in"),
        ConnectionSchema(source_block="inductor", source_port="out", target_block="capacitor", target_port="in"),
        ConnectionSchema(source_block="capacitor", source_port="out", target_block="scope_vc", target_port="in"),
        ConnectionSchema(source_block="inductor", source_port="out", target_block="scope_i", target_port="in"),
    ],
    metadata={
        "description": "Series RLC circuit with step voltage input",
        "tags": ["electrical", "RLC", "underdamped", "step-response"],
    },
)

# Save alongside this script
output_path = Path(__file__).parent / "rlc_series_output.json"
resolved = save_model(model, output_path)
print(f"✓ Model saved to: {resolved}")
print()
print("Done!")
