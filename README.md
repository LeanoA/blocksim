# BlockSim

![CI](https://github.com/LeanoA/blocksim/actions/workflows/ci.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)

A Simulink-like block-diagram simulation framework for modeling and solving dynamic systems. Build circuit models (RLC, etc.) visually, connect blocks, and run ODE-based simulations with real-time results streamed via WebSocket.

## Prerequisites / Tested Versions

| Tool / Dependency | Tested Version | Notes |
|-------------------|----------------|-------|
| Python            | **3.13.9**     | **Must use `python3.13`** — see warning below |
| Node.js           | 16.15.0        | |
| npm               | 8.18.0         | |

> **Python 3.14.1 warning:** NetworkX 3.6 is **incompatible** with CPython 3.14.1 due to a known `dataclasses.__annotate__` bug (`AttributeError: 'wrapper_descriptor' object has no attribute '__annotations__'`). Always create the venv with `python3.13`, **not** `python3` (which may resolve to 3.14 on your system).

### Key Backend Dependencies (installed versions)

| Package         | Version |
|-----------------|---------|
| FastAPI         | 0.135.1 |
| Uvicorn         | 0.42.0  |
| Pydantic        | 2.12.5  |
| NumPy           | 2.4.3   |
| SciPy           | 1.17.1  |
| NetworkX        | 3.6.1   |
| pytest          | 9.0.2   |
| httpx           | 0.28.1  |
| pytest-asyncio  | 1.3.0   |

### Key Frontend Dependencies

| Package         | Version |
|-----------------|---------|
| React           | ^18.3.1 |
| @xyflow/react   | ^12.10.1 |
| Recharts        | ^3.8.0  |
| Zustand         | ^5.0.12 |
| Vite            | ^4.5.3  |
| TypeScript      | ^5.5.3  |

## Setup

### Backend

```bash
cd backend

# Create venv — MUST use python3.13 explicitly
python3.13 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install the package with dev dependencies
pip install -e ".[dev]"
```

### Frontend

```bash
cd frontend
npm install
```

## Running the Application

### Start the API Server

```bash
cd backend
source .venv/bin/activate
uvicorn blocksim.api.app:create_app --factory --reload
```

The API will be available at `http://localhost:8000`. Key endpoints:

- `GET  /health` — Health check
- `GET  /api/...` — REST API routes
- `WS   /ws/...` — WebSocket endpoints for real-time simulation streaming
- `GET  /docs` — Interactive Swagger API documentation

### Start the Frontend Dev Server

```bash
cd frontend
npm run dev
```

The frontend will be available at `http://localhost:5173` (Vite default).

## Running Tests

### Backend Tests

```bash
cd backend
source .venv/bin/activate
python -m pytest tests/ -v
```

### Frontend

```bash
cd frontend
npm run lint     # ESLint checks
npm run build    # TypeScript compilation + Vite build
```

## Project Structure

```
blocksim/
├── backend/                    # Python simulation engine + REST/WebSocket API
│   ├── pyproject.toml          # Python project config & dependencies
│   ├── blocksim/
│   │   ├── core/               # Engine core
│   │   │   ├── block.py        # Block ABC — base class for all blocks
│   │   │   ├── solver.py       # ODE solvers (Euler, RK4, SciPy RK45, Radau)
│   │   │   ├── graph.py        # Dependency graph & topological sorting
│   │   │   └── system.py       # System assembly, connection wiring, simulation loop
│   │   ├── blocks/             # Built-in block library
│   │   │   ├── sources.py      # Signal sources (Step, Sine, Constant, Ramp)
│   │   │   ├── sinks.py        # Signal sinks (Scope, Logger)
│   │   │   ├── electrical.py   # RLC components (Resistor, Inductor, Capacitor)
│   │   │   ├── math_ops.py     # Math operations (Gain, Sum, Integrator)
│   │   │   ├── delays.py       # Delay blocks (UnitDelay, TransportDelay)
│   │   │   ├── registry.py     # Block type registry (auto-discovery)
│   │   │   └── EXTENDING.md    # Guide for adding custom blocks
│   │   ├── models/             # Pydantic schemas
│   │   │   ├── schemas.py      # API request/response models
│   │   │   └── persistence.py  # Model file save/load with versioning
│   │   └── api/                # FastAPI application
│   │       ├── app.py          # Application factory (create_app)
│   │       ├── routes.py       # REST API endpoints
│   │       ├── ws.py           # WebSocket endpoints
│   │       ├── store.py        # In-memory model store
│   │       └── dependencies.py # FastAPI dependency injection
│   └── tests/                  # pytest test suite
│       ├── test_block.py       # Block ABC tests
│       ├── test_solver.py      # Solver accuracy tests
│       ├── test_graph.py       # Graph & topological sort tests
│       ├── test_system.py      # System integration tests
│       ├── test_api.py         # API endpoint tests (httpx)
│       ├── test_schemas.py     # Pydantic schema validation
│       ├── test_persistence.py # Model save/load tests
│       ├── test_error_ux.py    # Error handling UX tests
│       ├── test_performance.py # Performance benchmarks
│       └── test_blocks/        # Per-block-type tests
├── frontend/                   # React UI — block-diagram editor
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── App.tsx             # Root component
│       ├── api/                # API client (fetch/WebSocket)
│       ├── components/
│       │   ├── BlockCanvas.tsx       # React Flow diagram canvas
│       │   ├── BlockNode.tsx         # Custom block node renderer
│       │   ├── BlockPalette.tsx      # Drag-and-drop block palette
│       │   ├── PropertyPanel.tsx     # Block parameter editor
│       │   ├── SimulationChart.tsx   # Recharts real-time plot
│       │   └── SimulationControls.tsx # Run/stop/configure controls
│       ├── store/
│       │   └── useModelStore.ts     # Zustand state management
│       └── types/              # TypeScript type definitions
└── examples/                   # Example simulation configurations
    ├── rlc_series.json         # RLC series circuit (JSON model)
    └── rlc_series.py           # RLC series circuit (Python script)
```

## Solvers

| Solver        | Type              | Best For                        |
|---------------|-------------------|---------------------------------|
| `euler`       | Fixed-step        | Testing, simple systems         |
| `rk4`         | Fixed-step        | General-purpose (default)       |
| `scipy_rk45`  | Adaptive          | Smooth non-stiff ODEs           |
| `radau`       | Implicit adaptive | Stiff systems (RLC circuits)    |

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! To get started:

1. **Fork** this repository
2. **Create a feature branch**: `git checkout -b feature/my-feature`
3. **Commit your changes**: `git commit -m "Add my feature"`
4. **Push to the branch**: `git push origin feature/my-feature`
5. **Open a Pull Request** against `main`

Please make sure all tests pass before submitting your PR:

```bash
# Backend
cd backend && python -m pytest tests/ -v

# Frontend
cd frontend && npm run lint && npm run build
```
