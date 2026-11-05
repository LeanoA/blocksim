"""Command-line interface for the BlockSim simulation engine.

Provides deterministic terminal subcommands for inspecting registered block
types, validating model JSON files, inspecting topological execution order,
and running ODE simulations from the command line.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from blocksim.blocks.registry import registry
from blocksim.core.block import PortAlreadyConnectedError
from blocksim.core.graph import AlgebraicLoopError
from blocksim.core.system import (
    DuplicateBlockIdError,
    DynamicSystem,
    InvalidConnectionError,
    SimulationDivergenceError,
)
from blocksim.models.persistence import (
    ModelFileError,
    SchemaVersionError,
    load_model,
)
from blocksim.models.schemas import ModelSchema, SimulationConfigSchema
from blocksim.models.validator import ModelValidator


def _load_model_any(path_str: str) -> ModelSchema:
    """Load a ModelSchema from either an envelope file or a raw ModelSchema JSON."""
    path = Path(path_str)
    try:
        return load_model(path)
    except ModelFileError:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and "model" in raw and isinstance(raw["model"], dict):
                return ModelSchema.model_validate(raw["model"])
            return ModelSchema.model_validate(raw)
        except (OSError, json.JSONDecodeError, ValidationError) as inner_exc:
            raise ModelFileError(str(path), str(inner_exc)) from inner_exc


def _compile_system(model: ModelSchema) -> DynamicSystem:
    """Instantiate blocks, wire connections, and compile a DynamicSystem."""
    system = DynamicSystem()
    for block_def in model.blocks:
        block_cls = registry.get(block_def.type)
        block = block_cls(block_id=block_def.id, **block_def.params)
        system.add_block(block)
    for conn in model.connections:
        system.connect(
            conn.source_block,
            conn.source_port,
            conn.target_block,
            conn.target_port,
        )
    system.compile()
    return system


def _cmd_blocks(args: argparse.Namespace) -> int:
    """List all registered block types and their port metadata."""
    items: list[dict[str, Any]] = []
    for name in registry.list_all():
        cls = registry.get(name)
        instance = cls(block_id="__cli__")
        info = instance.describe()
        info.pop("id", None)
        items.append(info)

    if args.json:
        print(json.dumps({"blocks": items}, indent=2))
        return 0

    print(f"Registered blocks ({len(items)}):")
    for item in items:
        inputs = ", ".join(item.get("inputs", {}).keys()) or "-"
        outputs = ", ".join(item.get("outputs", {}).keys()) or "-"
        print(f"  {item['type']:<16} inputs: [{inputs}] -> outputs: [{outputs}]")
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    """Validate a model JSON file through the 3-tier ModelValidator."""
    try:
        model = _load_model_any(args.file)
    except (ModelFileError, SchemaVersionError) as exc:
        if args.json:
            print(json.dumps({"valid": False, "error": str(exc)}, indent=2))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 2

    validator = ModelValidator(registry)
    _, result = validator.validate(model.model_dump())

    if args.json:
        print(result.model_dump_json(indent=2))
        return 0 if result.valid else 1

    status_label = "VALID" if result.valid else "INVALID"
    print(f"Model '{model.name}': {status_label} ({len(result.issues)} issue(s))")
    for issue in result.issues:
        target = f" [{issue.block_id}]" if issue.block_id else ""
        print(f"  - [{issue.severity.upper()}]{target} {issue.message}")
    return 0 if result.valid else 1


def _cmd_inspect(args: argparse.Namespace) -> int:
    """Compile a model and inspect its topological order and state vector size."""
    try:
        model = _load_model_any(args.file)
    except (ModelFileError, SchemaVersionError) as exc:
        if args.json:
            print(json.dumps({"error": str(exc)}, indent=2))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 2

    try:
        system = _compile_system(model)
    except (
        KeyError,
        ValueError,
        TypeError,
        DuplicateBlockIdError,
        InvalidConnectionError,
        PortAlreadyConnectedError,
        AlgebraicLoopError,
    ) as exc:
        if args.json:
            print(json.dumps({"error": str(exc)}, indent=2))
        else:
            print(f"Compilation error: {exc}", file=sys.stderr)
        return 1

    order = [b.id for b in system.sorted_blocks]
    payload = {
        "name": model.name,
        "block_count": len(model.blocks),
        "connection_count": len(model.connections),
        "state_size": system._total_state_size,
        "execution_order": order,
    }
    if args.json:
        print(json.dumps(payload, indent=2))
        return 0

    print(f"Model: {model.name}")
    print(f"Blocks: {payload['block_count']} | Connections: {payload['connection_count']}")
    print(f"State vector dimension: {payload['state_size']}")
    print(f"Execution order: {' -> '.join(order) if order else '(empty)'}")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    """Validate, compile, and simulate a model from the command line."""
    try:
        model = _load_model_any(args.file)
    except (ModelFileError, SchemaVersionError) as exc:
        if args.json:
            print(json.dumps({"error": str(exc)}, indent=2))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 2

    validator = ModelValidator(registry)
    _, validation = validator.validate(model.model_dump())
    if not validation.valid:
        if args.json:
            print(validation.model_dump_json(indent=2))
        else:
            print(f"Validation failed for '{model.name}':", file=sys.stderr)
            for issue in validation.issues:
                if issue.severity == "error":
                    print(f"  - {issue.message}", file=sys.stderr)
        return 1

    defaults = SimulationConfigSchema()
    solver_name = args.solver or defaults.solver
    t_start = args.t_start if args.t_start is not None else defaults.t_start
    t_end = args.t_end if args.t_end is not None else defaults.t_end
    dt = args.dt if args.dt is not None else defaults.dt

    try:
        system = _compile_system(model)
        result = system.simulate(t_span=(t_start, t_end), dt=dt, solver=solver_name)
    except (
        KeyError,
        ValueError,
        TypeError,
        DuplicateBlockIdError,
        InvalidConnectionError,
        PortAlreadyConnectedError,
        AlgebraicLoopError,
        SimulationDivergenceError,
        RuntimeError,
    ) as exc:
        if args.json:
            print(json.dumps({"error": str(exc)}, indent=2))
        else:
            print(f"Simulation error: {exc}", file=sys.stderr)
        return 1

    final_values = {
        key: float(vals[-1]) for key, vals in result.outputs.items() if len(vals) > 0
    }
    summary = {
        "model": model.name,
        "solver": solver_name,
        "steps": len(result.time) - 1,
        "t_start": float(result.time[0]),
        "t_end": float(result.time[-1]),
        "final_signals": final_values,
    }

    if args.output:
        out_path = Path(args.output)
        full_output = {
            **summary,
            "time": result.time.tolist(),
            "signals": {k: v.tolist() for k, v in result.outputs.items()},
        }
        out_path.write_text(json.dumps(full_output, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(summary, indent=2))
        return 0

    print(
        f"Simulated '{model.name}' ({summary['steps']} steps, "
        f"solver={solver_name}, t=[{summary['t_start']}, {summary['t_end']}])"
    )
    for sig, val in sorted(final_values.items()):
        print(f"  {sig:<24} = {val:.6g}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser for the blocksim CLI."""
    parser = argparse.ArgumentParser(
        prog="blocksim",
        description="BlockSim command-line interface for model validation and ODE simulation.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_blocks = subparsers.add_parser("blocks", help="List registered block types.")
    p_blocks.add_argument("--json", action="store_true", help="Emit JSON output.")
    p_blocks.set_defaults(func=_cmd_blocks)

    p_val = subparsers.add_parser("validate", help="Validate a model JSON file.")
    p_val.add_argument("file", help="Path to the model JSON file.")
    p_val.add_argument("--json", action="store_true", help="Emit JSON output.")
    p_val.set_defaults(func=_cmd_validate)

    p_ins = subparsers.add_parser("inspect", help="Compile and inspect model topology.")
    p_ins.add_argument("file", help="Path to the model JSON file.")
    p_ins.add_argument("--json", action="store_true", help="Emit JSON output.")
    p_ins.set_defaults(func=_cmd_inspect)

    p_run = subparsers.add_parser("run", help="Simulate a model JSON file.")
    p_run.add_argument("file", help="Path to the model JSON file.")
    p_run.add_argument("--solver", choices=["euler", "rk4", "scipy_rk45", "radau"])
    p_run.add_argument("--t-start", type=float, dest="t_start")
    p_run.add_argument("--t-end", type=float, dest="t_end")
    p_run.add_argument("--dt", type=float)
    p_run.add_argument("--output", help="Write full time-series JSON to file.")
    p_run.add_argument("--json", action="store_true", help="Emit summary as JSON.")
    p_run.set_defaults(func=_cmd_run)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the BlockSim CLI and return an integer exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "func", None)
    if handler is None:
        parser.print_help()
        return 2
    return int(handler(args))


def cli_entrypoint() -> None:
    """Console script entrypoint registered in pyproject.toml."""
    raise SystemExit(main())


if __name__ == "__main__":
    cli_entrypoint()
