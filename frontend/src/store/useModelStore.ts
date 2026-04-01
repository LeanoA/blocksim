/**
 * Zustand store for BlockSim model state.
 *
 * Manages:
 * - Current model (blocks, connections)
 * - Simulation results & status
 * - UI state (selected block, simulation running flag)
 *
 * Actions call the API client for backend persistence, then update local state.
 */

import { create } from 'zustand';

import * as api from '../api/client';
import type {
  BlockSchema,
  BlockTypeInfo,
  ConnectionSchema,
  ModelSchema,
  SimulationConfig,
  SimulationResult,
  SimulationStatus,
  SimFrame,
  WsServerMessage,
} from '../types';

// ---------------------------------------------------------------------------
// State shape
// ---------------------------------------------------------------------------

export interface ModelState {
  // --- Model data ---
  modelId: string | null;
  model: ModelSchema;

  // --- Block library ---
  blockLibrary: BlockTypeInfo[];

  // --- Simulation ---
  simulationConfig: SimulationConfig;
  simulationResult: SimulationResult | null;
  simulationStatus: SimulationStatus;
  simulationError: string | null;
  /** Live frames accumulated during WebSocket streaming */
  liveFrames: SimFrame[];

  // --- UI state ---
  selectedBlockId: string | null;

  // --- Actions: block library ---
  fetchBlockLibrary: () => Promise<void>;

  // --- Actions: model lifecycle ---
  createModel: (name: string) => Promise<void>;
  loadModel: (modelId: string) => Promise<void>;
  saveModel: () => Promise<void>;

  // --- Actions: blocks ---
  addBlock: (block: BlockSchema) => Promise<void>;
  removeBlock: (blockId: string) => Promise<void>;
  updateBlockPosition: (blockId: string, x: number, y: number) => void;
  updateBlockParams: (blockId: string, params: Record<string, unknown>) => void;

  // --- Actions: connections ---
  addConnection: (connection: ConnectionSchema) => Promise<void>;
  removeConnection: (connection: ConnectionSchema) => Promise<void>;

  // --- Actions: simulation ---
  setSimulationConfig: (config: Partial<SimulationConfig>) => void;
  runSimulation: () => Promise<void>;
  setSimulationResults: (result: SimulationResult | null) => void;

  // --- Actions: WebSocket streaming ---
  startStreamingSimulation: () => void;
  stopStreamingSimulation: () => void;

  // --- Actions: UI ---
  selectBlock: (blockId: string | null) => void;
  reset: () => void;
}

// ---------------------------------------------------------------------------
// Default state values
// ---------------------------------------------------------------------------

const defaultModel: ModelSchema = {
  name: 'Untitled',
  blocks: [],
  connections: [],
  metadata: {},
};

const defaultSimConfig: SimulationConfig = {
  t_start: 0.0,
  t_end: 1.0,
  dt: 0.001,
  solver: 'rk4',
};

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

/** Active WebSocket handle (module-level — not in state to avoid serialization issues) */
let wsHandle: api.SimulationSocket | null = null;

export const useModelStore = create<ModelState>((set, get) => ({
  // --- Initial state ---
  modelId: null,
  model: { ...defaultModel },
  blockLibrary: [],
  simulationConfig: { ...defaultSimConfig },
  simulationResult: null,
  simulationStatus: 'idle',
  simulationError: null,
  liveFrames: [],
  selectedBlockId: null,

  // --- Block library ---
  fetchBlockLibrary: async () => {
    try {
      const blocks = await api.getBlockLibrary();
      set({ blockLibrary: blocks });
    } catch (err) {
      console.error('Failed to fetch block library:', err);
    }
  },

  // --- Model lifecycle ---
  createModel: async (name: string) => {
    try {
      const res = await api.createModel({ name });
      set({
        modelId: res.id,
        model: res.model,
        simulationResult: null,
        simulationStatus: 'idle',
        simulationError: null,
        liveFrames: [],
        selectedBlockId: null,
      });
    } catch (err) {
      console.error('Failed to create model:', err);
      throw err;
    }
  },

  loadModel: async (modelId: string) => {
    try {
      const res = await api.getModel(modelId);
      set({
        modelId: res.id,
        model: res.model,
        simulationResult: null,
        simulationStatus: 'idle',
        simulationError: null,
        liveFrames: [],
        selectedBlockId: null,
      });
    } catch (err) {
      console.error('Failed to load model:', err);
      throw err;
    }
  },

  saveModel: async () => {
    const { modelId, model } = get();
    if (!modelId) return;
    try {
      const res = await api.updateModel(modelId, model);
      set({ model: res.model });
    } catch (err) {
      console.error('Failed to save model:', err);
      throw err;
    }
  },

  // --- Blocks ---
  addBlock: async (block: BlockSchema) => {
    const { modelId } = get();
    if (!modelId) throw new Error('No model loaded');
    try {
      const res = await api.addBlock(modelId, block);
      set({ model: res.model });
    } catch (err) {
      console.error('Failed to add block:', err);
      throw err;
    }
  },

  removeBlock: async (blockId: string) => {
    const { modelId, selectedBlockId } = get();
    if (!modelId) throw new Error('No model loaded');
    try {
      const res = await api.removeBlock(modelId, blockId);
      set({
        model: res.model,
        selectedBlockId: selectedBlockId === blockId ? null : selectedBlockId,
      });
    } catch (err) {
      console.error('Failed to remove block:', err);
      throw err;
    }
  },

  updateBlockPosition: (blockId: string, x: number, y: number) => {
    set((state) => ({
      model: {
        ...state.model,
        blocks: state.model.blocks.map((b) =>
          b.id === blockId ? { ...b, position: [x, y] as [number, number] } : b,
        ),
      },
    }));
    // Note: Position updates are local-only (debounced save can be added later).
  },

  updateBlockParams: (blockId: string, params: Record<string, unknown>) => {
    set((state) => ({
      model: {
        ...state.model,
        blocks: state.model.blocks.map((b) =>
          b.id === blockId ? { ...b, params: { ...b.params, ...params } } : b,
        ),
      },
    }));
  },

  // --- Connections ---
  addConnection: async (connection: ConnectionSchema) => {
    const { modelId } = get();
    if (!modelId) throw new Error('No model loaded');
    try {
      const res = await api.addConnection(modelId, connection);
      set({ model: res.model });
    } catch (err) {
      console.error('Failed to add connection:', err);
      throw err;
    }
  },

  removeConnection: async (connection: ConnectionSchema) => {
    const { modelId } = get();
    if (!modelId) throw new Error('No model loaded');
    try {
      const res = await api.removeConnection(modelId, connection);
      set({ model: res.model });
    } catch (err) {
      console.error('Failed to remove connection:', err);
      throw err;
    }
  },

  // --- Simulation config ---
  setSimulationConfig: (config: Partial<SimulationConfig>) => {
    set((state) => ({
      simulationConfig: { ...state.simulationConfig, ...config },
    }));
  },

  // --- Synchronous simulation ---
  runSimulation: async () => {
    const { modelId, simulationConfig } = get();
    if (!modelId) throw new Error('No model loaded');

    set({
      simulationStatus: 'running',
      simulationError: null,
      simulationResult: null,
      liveFrames: [],
    });

    try {
      const result = await api.simulate(modelId, simulationConfig);
      set({
        simulationResult: result,
        simulationStatus: 'complete',
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      set({
        simulationStatus: 'error',
        simulationError: message,
      });
      throw err;
    }
  },

  setSimulationResults: (result: SimulationResult | null) => {
    set({
      simulationResult: result,
      simulationStatus: result ? 'complete' : 'idle',
      simulationError: null,
    });
  },

  // --- WebSocket streaming ---
  startStreamingSimulation: () => {
    const { modelId, simulationConfig } = get();
    if (!modelId) return;

    // Close any existing connection.
    if (wsHandle) {
      wsHandle.close();
      wsHandle = null;
    }

    set({
      simulationStatus: 'running',
      simulationError: null,
      simulationResult: null,
      liveFrames: [],
    });

    wsHandle = api.connectSimulationWs(
      modelId,
      // onMessage
      (msg: WsServerMessage) => {
        switch (msg.type) {
          case 'frame':
            set((state) => ({
              liveFrames: [...state.liveFrames, msg.data],
            }));
            break;
          case 'complete':
          case 'stopped': {
            // Convert accumulated frames to a SimulationResult.
            const frames = get().liveFrames;
            if (frames.length > 0) {
              const time = frames.map((f) => f.t);
              const signalKeys = Object.keys(frames[0].signals);
              const signals: Record<string, number[]> = {};
              for (const key of signalKeys) {
                signals[key] = frames.map((f) => f.signals[key] ?? 0);
              }
              set({
                simulationResult: { time, signals },
                simulationStatus: msg.type === 'complete' ? 'complete' : 'stopped',
              });
            } else {
              set({ simulationStatus: msg.type === 'complete' ? 'complete' : 'stopped' });
            }
            wsHandle = null;
            break;
          }
          case 'error':
            set({
              simulationStatus: 'error',
              simulationError: msg.message,
            });
            wsHandle = null;
            break;
        }
      },
      // onClose
      () => {
        const { simulationStatus } = get();
        if (simulationStatus === 'running') {
          set({ simulationStatus: 'idle' });
        }
        wsHandle = null;
      },
      // onError
      () => {
        set({
          simulationStatus: 'error',
          simulationError: 'WebSocket connection error',
        });
        wsHandle = null;
      },
    );

    // Wait for connection to open, then send start command.
    wsHandle.ws.onopen = () => {
      wsHandle?.send({
        action: 'start',
        config: simulationConfig,
      });
    };
  },

  stopStreamingSimulation: () => {
    if (wsHandle) {
      wsHandle.send({ action: 'stop' });
    }
  },

  // --- UI ---
  selectBlock: (blockId: string | null) => {
    set({ selectedBlockId: blockId });
  },

  reset: () => {
    if (wsHandle) {
      wsHandle.close();
      wsHandle = null;
    }
    set({
      modelId: null,
      model: { ...defaultModel },
      simulationConfig: { ...defaultSimConfig },
      simulationResult: null,
      simulationStatus: 'idle',
      simulationError: null,
      liveFrames: [],
      selectedBlockId: null,
    });
  },
}));
