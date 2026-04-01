/**
 * Custom React Flow node component for a simulation block.
 *
 * Renders:
 *  - Block title (type name)
 *  - Input ports as Handles (type="target") on the left
 *  - Output ports as Handles (type="source") on the right
 *  - Category colour indicator (top border)
 *  - Key parameter values on the face
 *  - Selected state styling
 */

import { memo, useMemo } from 'react';
import { Handle, Position } from '@xyflow/react';
import type { NodeProps, Node } from '@xyflow/react';

import { getCategoryColor } from './BlockPalette';
import type { PortSchema } from '../types';

// ---------------------------------------------------------------------------
// Node data shape — this is what each React Flow node.data contains
// ---------------------------------------------------------------------------

export interface BlockNodeData {
  blockType: string;
  label: string;
  params: Record<string, unknown>;
  inputPorts: PortSchema[];
  outputPorts: PortSchema[];
  [key: string]: unknown; // React Flow requires index signature
}

export type BlockFlowNode = Node<BlockNodeData, 'block'>;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Format a parameter value for display on the node face. */
function formatParamValue(value: unknown): string {
  if (typeof value === 'number') {
    // Show up to 4 significant digits
    return Number.isInteger(value) ? String(value) : value.toPrecision(4);
  }
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return `[${value.join(',')}]`;
  return String(value);
}

/** Compute vertical offset (%) for port handles so they are evenly distributed. */
function portOffsets(count: number): string[] {
  if (count === 0) return [];
  if (count === 1) return ['50%'];
  // Distribute between 20% and 80% of the node height
  const start = 25;
  const end = 75;
  const step = (end - start) / (count - 1);
  return Array.from({ length: count }, (_, i) => `${start + i * step}%`);
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

function BlockNodeComponent({ data, selected }: NodeProps<BlockFlowNode>) {
  const color = getCategoryColor(data.blockType);

  // Build handles
  const inputHandles = useMemo(() => {
    const offsets = portOffsets(data.inputPorts.length);
    return data.inputPorts.map((port, i) => (
      <Handle
        key={`in-${port.name}`}
        type="target"
        position={Position.Left}
        id={port.name}
        style={{ top: offsets[i], background: color }}
        title={port.name}
      />
    ));
  }, [data.inputPorts, color]);

  const outputHandles = useMemo(() => {
    const offsets = portOffsets(data.outputPorts.length);
    return data.outputPorts.map((port, i) => (
      <Handle
        key={`out-${port.name}`}
        type="source"
        position={Position.Right}
        id={port.name}
        style={{ top: offsets[i], background: color }}
        title={port.name}
      />
    ));
  }, [data.outputPorts, color]);

  // Show key params (up to 3) on node face
  const paramEntries = useMemo(() => {
    const entries = Object.entries(data.params);
    return entries.slice(0, 3);
  }, [data.params]);

  return (
    <div
      className={`block-node ${selected ? 'block-node--selected' : ''}`}
      style={{ borderTopColor: color }}
    >
      {/* Port labels — left side */}
      <div className="block-node__port-labels block-node__port-labels--left">
        {data.inputPorts.map((p) => (
          <span key={p.name} className="block-node__port-label">{p.name}</span>
        ))}
      </div>

      {/* Center content */}
      <div className="block-node__body">
        <div className="block-node__title">{data.label}</div>
        {paramEntries.length > 0 && (
          <div className="block-node__params">
            {paramEntries.map(([key, val]) => (
              <div key={key} className="block-node__param">
                <span className="block-node__param-key">{key}:</span>{' '}
                <span className="block-node__param-val">
                  {formatParamValue(val)}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Port labels — right side */}
      <div className="block-node__port-labels block-node__port-labels--right">
        {data.outputPorts.map((p) => (
          <span key={p.name} className="block-node__port-label">{p.name}</span>
        ))}
      </div>

      {inputHandles}
      {outputHandles}
    </div>
  );
}

export default memo(BlockNodeComponent);
