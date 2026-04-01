import { useState, useCallback } from 'react';
import { ReactFlowProvider } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import './App.css';

import { BlockPalette } from './components/BlockPalette';
import { BlockCanvas } from './components/BlockCanvas';
import { PropertyPanel } from './components/PropertyPanel';
import { SimulationControls } from './components/SimulationControls';
import { SimulationChart } from './components/SimulationChart';
import { ValidationPanel } from './components/ValidationPanel';

/**
 * Root application component.
 *
 * Layout:
 *  - SimulationControls (top toolbar)
 *  - BlockPalette (left sidebar)
 *  - BlockCanvas (center)
 *  - PropertyPanel (right sidebar)
 *  - SimulationChart (bottom panel, collapsible)
 *
 * Wraps in ReactFlowProvider so child components can use useReactFlow().
 */
function App() {
  const [chartOpen, setChartOpen] = useState(true);

  const toggleChart = useCallback(() => {
    setChartOpen((prev) => !prev);
  }, []);

  return (
    <ReactFlowProvider>
      <div className="app-container">
        <header className="app-header">
          <div className="app-header__brand">
            <h1>BlockSim</h1>
            <span className="app-subtitle">Block-Diagram Simulation</span>
          </div>
          <SimulationControls />
        </header>

        <main className="app-main">
          <BlockPalette />
          <div className="app-center">
            <div className="app-canvas-area">
              <BlockCanvas />
            </div>
            {/* Collapsible chart panel */}
            <div className={`app-chart-area ${chartOpen ? 'app-chart-area--open' : 'app-chart-area--closed'}`}>
              <button
                className="app-chart-toggle"
                onClick={toggleChart}
                title={chartOpen ? 'Collapse chart panel' : 'Expand chart panel'}
              >
                {chartOpen ? 'Output' : 'Output'}
                <span className={`app-chart-toggle__arrow ${chartOpen ? '' : 'app-chart-toggle__arrow--collapsed'}`}>
                  {chartOpen ? '\u25BE' : '\u25B4'}
                </span>
              </button>
              {chartOpen && <SimulationChart />}
            </div>
            <ValidationPanel />
          </div>
          <PropertyPanel />
        </main>
      </div>
    </ReactFlowProvider>
  );
}

export default App;
