---
paths:
  - "backend/**"
---

# Backend Rules (`backend/`)

- **Layer Isolation**:
  - `blocksim/core/` must never import `fastapi`, `pydantic`, or `blocksim.api`.
  - `blocksim/blocks/` must only depend on `blocksim.core` and standard scientific libraries (`numpy`, `scipy`). New blocks must subclass `Block`, define ports in `__init__`, and register in `blocksim/blocks/registry.py` (see `backend/blocksim/blocks/EXTENDING.md`).
- **Domain Exceptions**:
  - Raise typed domain exceptions (`AlgebraicLoopError`, `SimulationDivergenceError`, `DuplicateBlockIdError`, `InvalidConnectionError`, `PortAlreadyConnectedError`, `ModelNotFoundError`, `ModelFileError`, `SchemaVersionError`) rather than generic `Exception` in core/model layers; map them to structured JSON responses in `blocksim/api/app.py`.
- **Verification**:
  - Always verify with `uv run ruff check backend/blocksim backend/tests`, `uv run mypy backend/blocksim`, and `uv run pytest -q --maxfail=1`.
