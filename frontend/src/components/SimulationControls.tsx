/**
 * Simulation Controls — toolbar for configuring and running simulations.
 *
 * Provides:
 *  - dt (time step) input
 *  - t_end (end time) input
 *  - Solver dropdown (euler / rk4)
 *  - "Run Simulation" button (REST)
 *  - "Stream" toggle (WebSocket real-time)
 *  - Status indicator (idle / running / complete / error)
 *  - Model name display
 */

import { useCallback, useState } from 'react';

import { useModelStore } from '../store/useModelStore';
import type { SolverType } from '../types';

// ---------------------------------------------------------------------------
// Status badge color mapping
// ---------------------------------------------------------------------------

function statusColor(status: string): string {
  switch (status) {
    case 'running':
      return '#facc15'; // yellow
    case 'complete':
      return '#4ade80'; // green
    case 'error':
      return '#f87171'; // red
    case 'stopped':
      return '#f97316'; // orange
    default:
      return '#94a3b8'; // gray = idle
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function SimulationControls() {
  const model = useModelStore((s) => s.model);
  const simulationConfig = useModelStore((s) => s.simulationConfig);
  const simulationStatus = useModelStore((s) => s.simulationStatus);
  const simulationError = useModelStore((s) => s.simulationError);
  const setSimulationConfig = useModelStore((s) => s.setSimulationConfig);
  const runSimulation = useModelStore((s) => s.runSimulation);
  const startStreamingSimulation = useModelStore((s) => s.startStreamingSimulation);
  const stopStreamingSimulation = useModelStore((s) => s.stopStreamingSimulation);
  const saveModel = useModelStore((s) => s.saveModel);

  const [streaming, setStreaming] = useState(false);

  const isRunning = simulationStatus === 'running';

  // ---- Config handlers ----

  const handleDtChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const val = parseFloat(e.target.value);
      if (!isNaN(val) && val > 0) {
        setSimulationConfig({ dt: val });
      }
    },
    [setSimulationConfig],
  );

  const handleTEndChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const val = parseFloat(e.target.value);
      if (!isNaN(val) && val > 0) {
        setSimulationConfig({ t_end: val });
      }
    },
    [setSimulationConfig],
  );

  const handleSolverChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      setSimulationConfig({ solver: e.target.value as SolverType });
    },
    [setSimulationConfig],
  );

  // ---- Simulation actions ----

  const handleRun = useCallback(async () => {
    if (isRunning) {
      if (streaming) {
        stopStreamingSimulation();
        setStreaming(false);
      }
      return;
    }

    // Save model first to ensure backend has latest params
    try {
      await saveModel();
    } catch {
      // If save fails (e.g. no model loaded), proceed anyway
    }

    if (streaming) {
      startStreamingSimulation();
    } else {
      try {
        await runSimulation();
      } catch {
        // Error is stored in the Zustand store
      }
    }
  }, [isRunning, streaming, saveModel, runSimulation, startStreamingSimulation, stopStreamingSimulation]);

  const toggleStreaming = useCallback(() => {
    setStreaming((s) => !s);
  }, []);

  return (
    <div className="sim-controls">
      {/* Model name */}
      <div className="sim-controls__model-name" title={model.name}>
        {model.name}
      </div>

      <div className="sim-controls__separator" />

      {/* Config inputs */}
      <div className="sim-controls__field">
        <label className="sim-controls__label" htmlFor="sim-dt">dt</label>
        <input
          id="sim-dt"
          className="sim-controls__input"
          type="number"
          step="0.001"
          min="0.0001"
          value={simulationConfig.dt}
          onChange={handleDtChange}
          disabled={isRunning}
        />
      </div>

      <div className="sim-controls__field">
        <label className="sim-controls__label" htmlFor="sim-tend">t_end</label>
        <input
          id="sim-tend"
          className="sim-controls__input"
          type="number"
          step="0.1"
          min="0.001"
          value={simulationConfig.t_end}
          onChange={handleTEndChange}
          disabled={isRunning}
        />
      </div>

      <div className="sim-controls__field">
        <label className="sim-controls__label" htmlFor="sim-solver">Solver</label>
        <select
          id="sim-solver"
          className="sim-controls__select"
          value={simulationConfig.solver}
          onChange={handleSolverChange}
          disabled={isRunning}
        >
          <option value="euler">Euler</option>
          <option value="rk4">RK4</option>
          <option value="radau">Radau</option>
        </select>
      </div>

      <div className="sim-controls__separator" />

      {/* Stream toggle */}
      <button
        className={`sim-controls__toggle ${streaming ? 'sim-controls__toggle--active' : ''}`}
        onClick={toggleStreaming}
        disabled={isRunning}
        title={streaming ? 'WebSocket streaming enabled' : 'Click to enable WebSocket streaming'}
      >
        Stream
      </button>

      {/* Run / Stop button */}
      <button
        className={`sim-controls__run-btn ${isRunning ? 'sim-controls__run-btn--stop' : ''}`}
        onClick={handleRun}
      >
        {isRunning ? 'Stop' : 'Run Simulation'}
      </button>

      <div className="sim-controls__separator" />

      {/* Status indicator */}
      <div className="sim-controls__status">
        <span
          className="sim-controls__status-dot"
          style={{ backgroundColor: statusColor(simulationStatus) }}
        />
        <span className="sim-controls__status-text">{simulationStatus}</span>
      </div>

      {/* Error message (if any) */}
      {simulationError && (
        <div className="sim-controls__error" title={simulationError}>
          {simulationError.length > 50
            ? simulationError.slice(0, 50) + '...'
            : simulationError}
        </div>
      )}
    </div>
  );
}
