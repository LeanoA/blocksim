/**
 * TypeScript types mirroring backend Pydantic schemas.
 *
 * These types define the API contract between the React frontend
 * and the FastAPI backend. They MUST match the Pydantic models in
 * backend/blocksim/models/schemas.py exactly.
 */

// ---------------------------------------------------------------------------
// Position (for React Flow node layout)
// ---------------------------------------------------------------------------

export interface Position {
  x: number;
  y: number;
}

// ---------------------------------------------------------------------------
// Port
// ---------------------------------------------------------------------------

export interface PortSchema {
  name: string;
  direction: 'in' | 'out';
  dtype: string;
}

// ---------------------------------------------------------------------------
// Block
// ---------------------------------------------------------------------------

/** Block type info returned by GET /api/blocks/library */
export interface BlockTypeInfo {
  type: string;
  params: Record<string, unknown>;
  input_ports: PortSchema[];
  output_ports: PortSchema[];
  error?: string;
}

/** Block definition used in model CRUD */
export interface BlockSchema {
  id: string;
  type: string;
  params: Record<string, unknown>;
  position: [number, number];
}

// ---------------------------------------------------------------------------
// Connection
// ---------------------------------------------------------------------------

export interface ConnectionSchema {
  source_block: string;
  source_port: string;
  target_block: string;
  target_port: string;
}

// ---------------------------------------------------------------------------
// Model
// ---------------------------------------------------------------------------

export interface ModelSchema {
  name: string;
  blocks: BlockSchema[];
  connections: ConnectionSchema[];
  metadata: Record<string, unknown>;
}

/** Response from POST/GET/PUT model endpoints */
export interface ModelResponse {
  id: string;
  model: ModelSchema;
}

/** Response from GET /api/models (list all) */
export interface ModelsListResponse {
  models: ModelResponse[];
}

// ---------------------------------------------------------------------------
// Simulation
// ---------------------------------------------------------------------------

export type SolverType = 'euler' | 'rk4' | 'radau';

export interface SimulationConfig {
  t_start: number;
  t_end: number;
  dt: number;
  solver: SolverType;
}

export interface SimulationResult {
  time: number[];
  signals: Record<string, number[]>;
}

/** Single WebSocket simulation frame */
export interface SimFrame {
  t: number;
  signals: Record<string, number>;
}

// ---------------------------------------------------------------------------
// WebSocket protocol messages
// ---------------------------------------------------------------------------

export interface WsStartMessage {
  action: 'start';
  config: Partial<SimulationConfig>;
}

export interface WsStopMessage {
  action: 'stop';
}

export type WsClientMessage = WsStartMessage | WsStopMessage;

export interface WsFrameMessage {
  type: 'frame';
  data: SimFrame;
}

export interface WsCompleteMessage {
  type: 'complete' | 'stopped';
  summary: {
    steps: number;
    t_end: number;
    solver: string;
  };
}

export interface WsErrorMessage {
  type: 'error';
  message: string;
}

export type WsServerMessage = WsFrameMessage | WsCompleteMessage | WsErrorMessage;

// ---------------------------------------------------------------------------
// UI State types
// ---------------------------------------------------------------------------

export type SimulationStatus = 'idle' | 'running' | 'complete' | 'error' | 'stopped';
