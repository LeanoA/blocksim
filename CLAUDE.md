# CLAUDE.md — Operational Manifest for BlockSim

BlockSim is a modular block-diagram simulation framework combining a decoupled Python ODE engine (`backend/blocksim/`), a deterministic CLI (`blocksim`), a FastAPI REST/WebSocket backend, and a React/TypeScript visual editor (`frontend/`).

## 1. System Architecture & Module Boundaries

| Layer | Path | Responsibility & Boundaries |
| :--- | :--- | :--- |
| **Core Engine** | `backend/blocksim/core/` | `Block` ABC (`block.py`), NetworkX DAG & algebraic loop detection (`graph.py`), ODE solvers (`solver.py`), and `DynamicSystem` (`system.py`). **Zero FastAPI or Pydantic imports.** |
| **Block Library** | `backend/blocksim/blocks/` | Built-in sources, sinks, math ops, delays, electrical blocks, and `BlockRegistry` (`registry.py`). Depends only on `core/`. |
| **Models & Validation** | `backend/blocksim/models/` | Pydantic v2 schemas (`schemas.py`), 3-tier validator (`validator.py`), and `.blocksim.json` SHA-256 envelope persistence (`persistence.py`). |
| **CLI Utility** | `backend/blocksim/cli.py` | Terminal entrypoint (`blocksim`) for `blocks`, `validate`, `inspect`, and `run`. |
| **HTTP / WS API** | `backend/blocksim/api/` | FastAPI app factory (`app.py`), REST routes (`routes.py`), WebSocket streaming (`ws.py`), and thread-safe in-memory `ModelStore` (`store.py`). |
| **Frontend UI** | `frontend/src/` | React 18 + TypeScript 5.5 + `@xyflow/react` canvas, Recharts plots, and Zustand store (`store/useModelStore.ts`). |

## 2. Terminal Invocations (Fast & Deterministic)

> **Python Version Constraint**: Always use **Python 3.13** via `uv run` (NetworkX 3.6 has a known CPython 3.14 `dataclasses.__annotate__` incompatibility).

```bash
# Sync Python workspace & dev tools
uv sync --dev

# Fast Backend Unit/API/CLI Suite (~1.7s, 432 tests — default)
uv run pytest -q --maxfail=1

# Targeted Backend Test File
uv run pytest backend/tests/test_cli.py -v

# Slow Analytical RLC & 100-Block Benchmarks (~28s, 39 tests)
uv run pytest -m slow -q

# Backend Static Verification (Linter + Typechecker)
uv run ruff check backend/blocksim backend/tests
uv run mypy backend/blocksim

# CLI Execution
uv run blocksim blocks
uv run blocksim validate examples/rlc_series.json
uv run blocksim inspect examples/rlc_series.json
uv run blocksim run examples/rlc_series.json --solver rk4 --t-end 0.05 --dt 0.001 --json

# Frontend Verification (~0.9s Vitest + ESLint + TypeScript build)
cd frontend && npm test -- --run && npm run lint && npm run build
```

## 3. Testing Invariants

- Run `uv run pytest -q --maxfail=1` and `uv run ruff check` / `uv run mypy` before and after every backend change.
- Run `cd frontend && npm test -- --run && npm run lint` before and after every frontend change.
- All tests must remain 100% self-contained in-process (`fastapi.testclient.TestClient`, `tmp_path`, `jsdom` mocks) with zero external database or network calls.
- Reset `model_store.clear()` in API test fixtures to prevent cross-test state leakage.

## 4. Code Conventions

- **Python**: Strict type annotations on all function signatures; `from __future__ import annotations`; keep `core/` free of transport/API concerns.
- **TypeScript / React**: Strict TypeScript (`tsc -b`), functional components, state mutations centralized in `useModelStore.ts`.
- **Language**: All code, comments, identifiers, CLI output, UI labels, and documentation must be in English.

## 5. Data Hygiene & Security

- Never introduce hardcoded API keys, credentials, `.env` files, or PII.
- Use synthetic circuit/control models and `tmp_path` fixtures exclusively.
