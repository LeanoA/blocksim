/**
 * Block Palette sidebar — lists available block types grouped by category.
 *
 * Each block is draggable onto the canvas (React Flow drop target).
 * Drag data is encoded via dataTransfer so BlockCanvas can read the block type.
 */

import { useState, useMemo, useCallback, DragEvent } from 'react';

import type { BlockTypeInfo } from '../types';
import { useModelStore } from '../store/useModelStore';

// ---------------------------------------------------------------------------
// Category definitions — order matters for rendering
// ---------------------------------------------------------------------------

interface CategoryDef {
  key: string;
  label: string;
  emoji: string;
  types: string[];
}

const CATEGORIES: CategoryDef[] = [
  {
    key: 'sources',
    label: 'Sources',
    emoji: '⚡',
    types: ['ConstantSource', 'StepSource', 'SineSource', 'RampSource'],
  },
  {
    key: 'math',
    label: 'Math',
    emoji: '➗',
    types: ['Gain', 'Sum', 'Multiply'],
  },
  {
    key: 'continuous',
    label: 'Continuous',
    emoji: '∫',
    types: ['Integrator', 'Derivative'],
  },
  {
    key: 'electrical',
    label: 'Electrical',
    emoji: '🔌',
    types: ['VoltageSource', 'Resistor', 'Inductor', 'Capacitor'],
  },
  {
    key: 'sinks',
    label: 'Sinks',
    emoji: '📊',
    types: ['Scope', 'Display'],
  },
  {
    key: 'utility',
    label: 'Utility',
    emoji: '🔧',
    types: ['Delay'],
  },
];

/** Map block type name → category key for lookup */
const TYPE_TO_CATEGORY: Record<string, string> = {};
for (const cat of CATEGORIES) {
  for (const t of cat.types) {
    TYPE_TO_CATEGORY[t] = cat.key;
  }
}

/** Get the category colour used for node tinting */
export function getCategoryColor(blockType: string): string {
  const cat = TYPE_TO_CATEGORY[blockType];
  switch (cat) {
    case 'sources':
      return '#4ade80'; // green
    case 'math':
      return '#60a5fa'; // blue
    case 'continuous':
      return '#c084fc'; // purple
    case 'electrical':
      return '#facc15'; // yellow
    case 'sinks':
      return '#f87171'; // red
    case 'utility':
      return '#94a3b8'; // gray
    default:
      return '#94a3b8';
  }
}

export function getCategoryForType(blockType: string): string {
  return TYPE_TO_CATEGORY[blockType] ?? 'utility';
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function BlockPalette() {
  const blockLibrary = useModelStore((s) => s.blockLibrary);
  const [search, setSearch] = useState('');

  // Index library by type name for quick lookup
  const libraryMap = useMemo(() => {
    const map = new Map<string, BlockTypeInfo>();
    for (const b of blockLibrary) {
      map.set(b.type, b);
    }
    return map;
  }, [blockLibrary]);

  // Filter categories by search term
  const filteredCategories = useMemo(() => {
    const q = search.toLowerCase().trim();
    if (!q) return CATEGORIES;
    return CATEGORIES.map((cat) => ({
      ...cat,
      types: cat.types.filter(
        (t) =>
          t.toLowerCase().includes(q) ||
          cat.label.toLowerCase().includes(q),
      ),
    })).filter((cat) => cat.types.length > 0);
  }, [search]);

  const onDragStart = useCallback(
    (event: DragEvent<HTMLDivElement>, blockType: string) => {
      // Encode data for the canvas drop handler
      event.dataTransfer.setData('application/blocksim-block-type', blockType);
      event.dataTransfer.effectAllowed = 'move';
    },
    [],
  );

  return (
    <aside className="block-palette">
      <div className="palette-header">
        <span className="palette-title">Blocks</span>
      </div>

      <input
        className="palette-search"
        type="text"
        placeholder="Search blocks…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />

      <div className="palette-list">
        {filteredCategories.map((cat) => (
          <div key={cat.key} className="palette-category">
            <div className="palette-category-header">
              <span className="palette-category-emoji">{cat.emoji}</span>
              <span className="palette-category-label">{cat.label}</span>
            </div>

            {cat.types.map((typeName) => {
              const info = libraryMap.get(typeName);
              const portSummary = info
                ? `${info.input_ports.length}→${info.output_ports.length}`
                : '';

              return (
                <div
                  key={typeName}
                  className="palette-block-item"
                  draggable
                  onDragStart={(e) => onDragStart(e, typeName)}
                  style={{
                    borderLeftColor: getCategoryColor(typeName),
                  }}
                >
                  <span className="palette-block-name">{typeName}</span>
                  {portSummary && (
                    <span className="palette-block-ports">{portSummary}</span>
                  )}
                </div>
              );
            })}
          </div>
        ))}

        {filteredCategories.length === 0 && (
          <div className="palette-empty">No blocks match "{search}"</div>
        )}
      </div>
    </aside>
  );
}
