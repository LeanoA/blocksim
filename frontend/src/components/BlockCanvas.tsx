/**
 * Block Canvas — main React Flow canvas component.
 *
 * Responsibilities:
 *  - Converts Zustand store blocks/connections → React Flow nodes/edges
 *  - Handles node position changes → store.updateBlockPosition
 *  - Handles new connections → store.addConnection
 *  - Handles deletion of nodes/edges → store.removeBlock / removeConnection
 *  - Drop handler: accepts dragged block types from BlockPalette → creates new block
 *  - Dark theme background (dots), Controls, MiniMap
 */

import { useCallback, useMemo, useEffect, DragEvent } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  BackgroundVariant,
  useReactFlow,
  type Node,
  type Edge,
  type OnNodesChange,
  type OnEdgesChange,
  type OnConnect,
  type NodeTypes,
  type Connection,
} from '@xyflow/react';

import BlockNodeComponent from './BlockNode';
import type { BlockNodeData } from './BlockNode';
import { useModelStore } from '../store/useModelStore';
import type { BlockSchema, BlockTypeInfo, ConnectionSchema } from '../types';

// ---------------------------------------------------------------------------
// Custom node types — defined OUTSIDE component to avoid re-creation
// ---------------------------------------------------------------------------

const nodeTypes: NodeTypes = {
  block: BlockNodeComponent,
};

// ---------------------------------------------------------------------------
// Conversion helpers
// ---------------------------------------------------------------------------

/** Convert a BlockSchema (store) → React Flow Node */
function blockToNode(
  block: BlockSchema,
  libraryMap: Map<string, BlockTypeInfo>,
): Node<BlockNodeData> {
  const info = libraryMap.get(block.type);
  return {
    id: block.id,
    type: 'block',
    position: { x: block.position[0], y: block.position[1] },
    data: {
      blockId: block.id,
      blockType: block.type,
      label: block.type,
      params: block.params,
      inputPorts: info?.input_ports ?? [],
      outputPorts: info?.output_ports ?? [],
    },
  };
}

/** Convert a ConnectionSchema → React Flow Edge */
function connectionToEdge(conn: ConnectionSchema, index: number): Edge {
  return {
    id: `e-${conn.source_block}.${conn.source_port}-${conn.target_block}.${conn.target_port}-${index}`,
    source: conn.source_block,
    sourceHandle: conn.source_port,
    target: conn.target_block,
    targetHandle: conn.target_port,
    type: 'smoothstep',
    animated: false,
    style: { stroke: '#888', strokeWidth: 2 },
  };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

let blockCounter = 0;

export function BlockCanvas() {
  const model = useModelStore((s) => s.model);
  const blockLibrary = useModelStore((s) => s.blockLibrary);
  const selectedBlockId = useModelStore((s) => s.selectedBlockId);
  const selectBlock = useModelStore((s) => s.selectBlock);
  const updateBlockPosition = useModelStore((s) => s.updateBlockPosition);
  const addBlock = useModelStore((s) => s.addBlock);
  const addConnection = useModelStore((s) => s.addConnection);
  const removeBlock = useModelStore((s) => s.removeBlock);
  const removeConnection = useModelStore((s) => s.removeConnection);

  const { screenToFlowPosition } = useReactFlow();

  // Build library lookup map
  const libraryMap = useMemo(() => {
    const map = new Map<string, BlockTypeInfo>();
    for (const b of blockLibrary) {
      map.set(b.type, b);
    }
    return map;
  }, [blockLibrary]);

  // Convert store → React Flow nodes
  const nodes = useMemo<Node<BlockNodeData>[]>(
    () => model.blocks.map((b) => blockToNode(b, libraryMap)),
    [model.blocks, libraryMap],
  );

  // Apply selection styling
  const nodesWithSelection = useMemo(
    () =>
      nodes.map((n) => ({
        ...n,
        selected: n.id === selectedBlockId,
      })),
    [nodes, selectedBlockId],
  );

  // Convert store → React Flow edges
  const edges = useMemo<Edge[]>(
    () => model.connections.map((c, i) => connectionToEdge(c, i)),
    [model.connections],
  );

  // --- Event handlers ---

  const onNodesChange: OnNodesChange = useCallback(
    (changes) => {
      // Apply changes locally (for dragging positions)
      // We intercept position changes to update the store
      for (const change of changes) {
        if (change.type === 'position' && change.position && change.id) {
          updateBlockPosition(change.id, change.position.x, change.position.y);
        }
        if (change.type === 'select' && change.id) {
          if (change.selected) {
            selectBlock(change.id);
          } else if (selectedBlockId === change.id) {
            selectBlock(null);
          }
        }
      }

      // Let React Flow apply the changes for its internal state as well
      // We compute a "dummy" pass so React Flow can reconcile
      // Since we're driving nodes from the store, we don't need to use
      // setNodes — but we still need to handle remove changes
      for (const change of changes) {
        if (change.type === 'remove') {
          removeBlock(change.id).catch(console.error);
        }
      }
    },
    [updateBlockPosition, selectBlock, selectedBlockId, removeBlock],
  );

  const onEdgesChange: OnEdgesChange = useCallback(
    (changes) => {
      for (const change of changes) {
        if (change.type === 'remove') {
          // Parse edge ID to recover connection info
          const edge = edges.find((e) => e.id === change.id);
          if (edge && edge.sourceHandle && edge.targetHandle) {
            removeConnection({
              source_block: edge.source,
              source_port: edge.sourceHandle,
              target_block: edge.target,
              target_port: edge.targetHandle,
            }).catch(console.error);
          }
        }
      }
    },
    [edges, removeConnection],
  );

  const onConnect: OnConnect = useCallback(
    (connection: Connection) => {
      if (
        connection.source &&
        connection.target &&
        connection.sourceHandle &&
        connection.targetHandle
      ) {
        addConnection({
          source_block: connection.source,
          source_port: connection.sourceHandle,
          target_block: connection.target,
          target_port: connection.targetHandle,
        }).catch(console.error);
      }
    },
    [addConnection],
  );

  // --- Drag & Drop from palette ---

  const onDragOver = useCallback((event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault();

      const blockType = event.dataTransfer.getData(
        'application/blocksim-block-type',
      );
      if (!blockType) return;

      // Convert screen coords to flow coords
      const position = screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });

      // Get default params from library
      const info = libraryMap.get(blockType);
      const defaultParams = info?.params ?? {};

      blockCounter += 1;
      const newBlock: BlockSchema = {
        id: `${blockType}_${blockCounter}`,
        type: blockType,
        params: { ...defaultParams },
        position: [position.x, position.y],
      };

      addBlock(newBlock).catch(console.error);
    },
    [screenToFlowPosition, libraryMap, addBlock],
  );

  // --- Pane click to deselect ---
  const onPaneClick = useCallback(() => {
    selectBlock(null);
  }, [selectBlock]);

  // --- Fetch block library on mount ---
  const fetchBlockLibrary = useModelStore((s) => s.fetchBlockLibrary);
  const createModel = useModelStore((s) => s.createModel);
  const modelId = useModelStore((s) => s.modelId);

  useEffect(() => {
    fetchBlockLibrary();
  }, [fetchBlockLibrary]);

  // Auto-create a model if none loaded
  useEffect(() => {
    if (!modelId) {
      createModel('Untitled').catch(console.error);
    }
  }, [modelId, createModel]);

  return (
    <div className="block-canvas">
      <ReactFlow
        nodes={nodesWithSelection}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onDragOver={onDragOver}
        onDrop={onDrop}
        onPaneClick={onPaneClick}
        nodeTypes={nodeTypes}
        fitView
        snapToGrid
        snapGrid={[15, 15]}
        deleteKeyCode="Delete"
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} color="#444" gap={20} size={1} />
        <Controls
          position="bottom-right"
          style={{ background: '#2a2a4a', borderColor: '#555' }}
        />
        <MiniMap
          position="bottom-left"
          nodeColor={(node) => {
            const data = node.data as BlockNodeData | undefined;
            if (data?.blockType) {
              // Use a simple category → color mapping
              const cat = data.blockType;
              if (cat.includes('Source') || cat === 'Sine' || cat === 'Step' || cat === 'Constant' || cat === 'Ramp')
                return '#4ade80';
              if (cat === 'Scope' || cat === 'Display') return '#f87171';
              return '#60a5fa';
            }
            return '#94a3b8';
          }}
          maskColor="rgba(0,0,0,0.7)"
          style={{ background: '#1a1a2e' }}
        />
      </ReactFlow>
    </div>
  );
}
