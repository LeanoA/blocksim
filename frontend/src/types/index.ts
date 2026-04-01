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
// Validation
// ---------------------------------------------------------------------------

/** Severity level for validation issues. */
export type ValidationSeverity = 'error' | 'warning' | 'info';

/** A single validation issue found during model validation. */
export interface ValidationIssue {
  severity: ValidationSeverity;
  category: string; // "schema" | "referential" | "semantic"
  message: string;
  block_id: string | null;
  field: string | null;
}

/** Result of running the multi-level model validator. */
export interface ValidationResult {
  valid: boolean; // true if no errors (warnings OK)
  issues: ValidationIssue[];
  checksum_match: boolean | null; // null if no checksum in file
}

// ---------------------------------------------------------------------------
// Export / Import
// ---------------------------------------------------------------------------

/** Envelope format for exported model files (.blocksim.json). */
export interface ExportEnvelope {
  schema_version: string;
  exported_at: string; // ISO 8601
  blocksim_version: string;
  checksum: string; // SHA-256 hex
  model: ModelSchema;
}

/** Response from POST /api/models/import. */
export interface ImportResponse {
  id: string;
  model: ModelSchema;
  validation: ValidationResult;
}

// ---------------------------------------------------------------------------
// Block Execution Errors (simulation resilience)
// ---------------------------------------------------------------------------

/** Error recorded when a block's compute() fails during simulation. */
export interface BlockExecutionError {
  block_id: string;
  step: number;
  time: number;
  error: string;
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

export type SimulationResultStatus = 'completed' | 'completed_with_errors';

export interface SimulationResult {
  time: number[];
  signals: Record<string, number[]>;
  block_errors?: Record<string, BlockExecutionError[]>;
  status?: SimulationResultStatus;
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

export type SimulationStatus = 'idle' | 'running' | 'complete' | 'complete_with_errors' | 'error' | 'stopped';
