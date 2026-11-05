---
paths:
  - "frontend/**"
---

# Frontend Rules (`frontend/`)

- **State & API Architecture**:
  - Keep HTTP and WebSocket calls inside `frontend/src/api/client.ts`.
  - Keep diagram and simulation state transitions inside `frontend/src/store/useModelStore.ts`.
  - Avoid exporting non-component helpers directly from React component files (`frontend/src/components/*.tsx`) to satisfy `react-refresh/only-export-components`.
- **Verification**:
  - Always verify with `cd frontend && npm test -- --run && npm run lint && npm run build`.
