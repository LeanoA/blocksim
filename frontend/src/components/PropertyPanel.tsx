/**
 * Property Panel — right sidebar showing properties of the selected block.
 *
 * Displays:
 *  - Block type and ID
 *  - Editable parameters (input fields for each param)
 *  - Port information (inputs/outputs with connection status)
 *  - Delete block button
 *
 * Shows a "No block selected" placeholder when nothing is selected.
 */

import { useCallback, useMemo } from 'react';

import { useModelStore } from '../store/useModelStore';
import { getCategoryColor, getCategoryForType } from './BlockPalette';
import type { BlockTypeInfo, ConnectionSchema } from '../types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Check if a specific port on a block is connected */
function isPortConnected(
  connections: ConnectionSchema[],
  blockId: string,
  portName: string,
  direction: 'in' | 'out',
): boolean {
  if (direction === 'in') {
    return connections.some(
      (c) => c.target_block === blockId && c.target_port === portName,
    );
  }
  return connections.some(
    (c) => c.source_block === blockId && c.source_port === portName,
  );
}

/** Parse a parameter value to the appropriate type for the store */
function parseParamValue(current: unknown, raw: string): unknown {
  if (typeof current === 'number') {
    const n = Number(raw);
    return isNaN(n) ? raw : n;
  }
  if (typeof current === 'boolean') {
    return raw === 'true' || raw === '1';
  }
  // Arrays like signs: ["+", "-"]
  if (Array.isArray(current)) {
    try {
      return JSON.parse(raw);
    } catch {
      return raw.split(',').map((s) => s.trim());
    }
  }
  return raw;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function PropertyPanel() {
  const selectedBlockId = useModelStore((s) => s.selectedBlockId);
  const model = useModelStore((s) => s.model);
  const blockLibrary = useModelStore((s) => s.blockLibrary);
  const updateBlockParams = useModelStore((s) => s.updateBlockParams);
  const removeBlock = useModelStore((s) => s.removeBlock);

  // Find the selected block
  const block = useMemo(
    () => model.blocks.find((b) => b.id === selectedBlockId) ?? null,
    [model.blocks, selectedBlockId],
  );

  // Library info for the selected block type
  const libraryMap = useMemo(() => {
    const map = new Map<string, BlockTypeInfo>();
    for (const b of blockLibrary) {
      map.set(b.type, b);
    }
    return map;
  }, [blockLibrary]);

  const info = block ? libraryMap.get(block.type) ?? null : null;
  const categoryColor = block ? getCategoryColor(block.type) : '#888';
  const category = block ? getCategoryForType(block.type) : '';

  const handleParamChange = useCallback(
    (key: string, value: string) => {
      if (!block) return;
      const currentVal = block.params[key];
      const parsed = parseParamValue(currentVal, value);
      updateBlockParams(block.id, { [key]: parsed });
    },
    [block, updateBlockParams],
  );

  const handleDelete = useCallback(() => {
    if (!block) return;
    removeBlock(block.id).catch(console.error);
  }, [block, removeBlock]);

  // ---- No block selected placeholder ----
  if (!block) {
    return (
      <aside className="property-panel">
        <div className="property-panel__header">
          <span className="property-panel__title">Properties</span>
        </div>
        <div className="property-panel__empty">
          <div className="property-panel__empty-icon">⬚</div>
          <div className="property-panel__empty-text">No block selected</div>
          <div className="property-panel__empty-hint">
            Click a block on the canvas to view its properties
          </div>
        </div>
      </aside>
    );
  }

  const paramEntries = Object.entries(block.params);

  return (
    <aside className="property-panel">
      {/* Header */}
      <div className="property-panel__header">
        <span className="property-panel__title">Properties</span>
      </div>

      <div className="property-panel__content">
        {/* Block identity */}
        <section className="property-panel__section">
          <div className="property-panel__block-type" style={{ borderLeftColor: categoryColor }}>
            <span className="property-panel__type-name">{block.type}</span>
            <span className="property-panel__category-badge">{category}</span>
          </div>
          <div className="property-panel__block-id">
            <span className="property-panel__label">ID</span>
            <span className="property-panel__value">{block.id}</span>
          </div>
        </section>

        {/* Parameters */}
        {paramEntries.length > 0 && (
          <section className="property-panel__section">
            <div className="property-panel__section-title">Parameters</div>
            {paramEntries.map(([key, val]) => (
              <div key={key} className="property-panel__field">
                <label className="property-panel__field-label">{key}</label>
                <input
                  className="property-panel__field-input"
                  type="text"
                  value={formatDisplayValue(val)}
                  onChange={(e) => handleParamChange(key, e.target.value)}
                />
              </div>
            ))}
          </section>
        )}

        {/* Ports */}
        {info && (
          <section className="property-panel__section">
            <div className="property-panel__section-title">Ports</div>

            {info.input_ports.length > 0 && (
              <div className="property-panel__port-group">
                <div className="property-panel__port-group-label">Inputs</div>
                {info.input_ports.map((port) => {
                  const connected = isPortConnected(
                    model.connections,
                    block.id,
                    port.name,
                    'in',
                  );
                  return (
                    <div key={port.name} className="property-panel__port">
                      <span className={`property-panel__port-dot ${connected ? 'property-panel__port-dot--connected' : ''}`} />
                      <span className="property-panel__port-name">{port.name}</span>
                      <span className="property-panel__port-status">
                        {connected ? 'connected' : 'open'}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}

            {info.output_ports.length > 0 && (
              <div className="property-panel__port-group">
                <div className="property-panel__port-group-label">Outputs</div>
                {info.output_ports.map((port) => {
                  const connected = isPortConnected(
                    model.connections,
                    block.id,
                    port.name,
                    'out',
                  );
                  return (
                    <div key={port.name} className="property-panel__port">
                      <span className={`property-panel__port-dot ${connected ? 'property-panel__port-dot--connected' : ''}`} />
                      <span className="property-panel__port-name">{port.name}</span>
                      <span className="property-panel__port-status">
                        {connected ? 'connected' : 'open'}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        )}

        {/* Delete button */}
        <section className="property-panel__section property-panel__section--actions">
          <button
            className="property-panel__delete-btn"
            onClick={handleDelete}
            title="Delete this block and its connections"
          >
            Delete Block
          </button>
        </section>
      </div>
    </aside>
  );
}

/** Format a value for display in the input field */
function formatDisplayValue(val: unknown): string {
  if (val === null || val === undefined) return '';
  if (typeof val === 'number') return String(val);
  if (typeof val === 'string') return val;
  if (Array.isArray(val)) return JSON.stringify(val);
  return String(val);
}
