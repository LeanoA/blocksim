/**
 * Simulation Output Chart — bottom panel showing time-series results.
 *
 * Uses Recharts LineChart with ResponsiveContainer to plot simulation
 * signal data from Scope blocks. Supports multiple signals overlaid
 * on the same chart with legend, tooltip, and dark theme styling.
 */

import { useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

import { useModelStore } from '../store/useModelStore';

// ---------------------------------------------------------------------------
// Signal colors — cycle through these for each signal line
// ---------------------------------------------------------------------------

const SIGNAL_COLORS = [
  '#7c9df5', // blue
  '#4ade80', // green
  '#f87171', // red
  '#facc15', // yellow
  '#c084fc', // purple
  '#f97316', // orange
  '#06b6d4', // cyan
  '#ec4899', // pink
  '#a3e635', // lime
  '#94a3b8', // gray
];

// ---------------------------------------------------------------------------
// Custom Tooltip (dark-themed)
// ---------------------------------------------------------------------------

interface TooltipPayloadItem {
  name: string;
  value: number;
  color: string;
  dataKey: string;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadItem[];
  label?: number;
}

function ChartTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className="sim-chart__tooltip">
      <div className="sim-chart__tooltip-label">t = {typeof label === 'number' ? label.toFixed(4) : label}</div>
      {payload.map((entry) => (
        <div key={entry.dataKey} className="sim-chart__tooltip-item" style={{ color: entry.color }}>
          <span className="sim-chart__tooltip-dot" style={{ backgroundColor: entry.color }} />
          {entry.name}: {typeof entry.value === 'number' ? entry.value.toPrecision(5) : entry.value}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function SimulationChart() {
  const simulationResult = useModelStore((s) => s.simulationResult);
  const simulationStatus = useModelStore((s) => s.simulationStatus);

  // Transform simulation result into Recharts data format:
  // [{ time: 0.0, signal1: 1.23, signal2: 4.56 }, ...]
  const { chartData, signalKeys } = useMemo(() => {
    if (!simulationResult || simulationResult.time.length === 0) {
      return { chartData: [], signalKeys: [] };
    }

    const keys = Object.keys(simulationResult.signals);
    const data = simulationResult.time.map((t, i) => {
      const point: Record<string, number> = { time: t };
      for (const key of keys) {
        point[key] = simulationResult.signals[key][i] ?? 0;
      }
      return point;
    });

    // Downsample for performance if too many points
    const maxPoints = 2000;
    let sampled = data;
    if (data.length > maxPoints) {
      const step = Math.ceil(data.length / maxPoints);
      sampled = data.filter((_, i) => i % step === 0);
      // Always include the last point
      if (sampled[sampled.length - 1] !== data[data.length - 1]) {
        sampled.push(data[data.length - 1]);
      }
    }

    return { chartData: sampled, signalKeys: keys };
  }, [simulationResult]);

  // ---- Placeholder when no data ----
  if (!simulationResult || chartData.length === 0) {
    return (
      <div className="sim-chart">
        <div className="sim-chart__header">
          <span className="sim-chart__title">Simulation Output</span>
        </div>
        <div className="sim-chart__empty">
          <div className="sim-chart__empty-icon">
            {simulationStatus === 'running' ? '...' : '~'}
          </div>
          <div className="sim-chart__empty-text">
            {simulationStatus === 'running'
              ? 'Simulation running...'
              : 'Run simulation to see results'}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="sim-chart">
      <div className="sim-chart__header">
        <span className="sim-chart__title">Simulation Output</span>
        <span className="sim-chart__info">
          {chartData.length} points | {signalKeys.length} signal{signalKeys.length !== 1 ? 's' : ''}
        </span>
      </div>
      <div className="sim-chart__body">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={chartData}
            margin={{ top: 8, right: 16, left: 8, bottom: 4 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#333" />
            <XAxis
              dataKey="time"
              type="number"
              domain={['dataMin', 'dataMax']}
              tick={{ fill: '#888', fontSize: 11 }}
              axisLine={{ stroke: '#555' }}
              tickLine={{ stroke: '#555' }}
              tickFormatter={(v: number) => v.toFixed(3)}
              label={{ value: 'Time (s)', position: 'insideBottomRight', offset: -4, fill: '#777', fontSize: 11 }}
            />
            <YAxis
              tick={{ fill: '#888', fontSize: 11 }}
              axisLine={{ stroke: '#555' }}
              tickLine={{ stroke: '#555' }}
              tickFormatter={(v: number) => v.toPrecision(3)}
              width={60}
            />
            <Tooltip content={<ChartTooltip />} />
            <Legend
              wrapperStyle={{ color: '#ccc', fontSize: '0.75rem', paddingTop: '4px' }}
            />
            {signalKeys.map((key, i) => (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                name={key}
                stroke={SIGNAL_COLORS[i % SIGNAL_COLORS.length]}
                strokeWidth={1.5}
                dot={false}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
