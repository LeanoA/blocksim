/**
 * API client for the BlockSim backend.
 *
 * All functions talk to the FastAPI backend via the Vite dev-server proxy
 * (requests to /api/* are forwarded to localhost:8000).
 *
 * Functions throw on non-2xx responses with the error detail from the backend.
 */

import type {
  BlockSchema,
  BlockTypeInfo,
  ConnectionSchema,
  ImportResponse,
  ModelResponse,
  ModelSchema,
  ModelsListResponse,
  SimulationConfig,
  SimulationResult,
  ValidationResult,
  WsClientMessage,
  WsServerMessage,
} from '../types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const BASE = '/api';

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body.detail) detail = String(body.detail);
    } catch {
      // ignore parse errors
    }
    throw new Error(detail);
  }

  // 204 No Content
  if (res.status === 204) return undefined as unknown as T;

  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Block library
// ---------------------------------------------------------------------------

export async function getBlockLibrary(): Promise<BlockTypeInfo[]> {
  const data = await request<{ blocks: BlockTypeInfo[] }>('/blocks/library');
  return data.blocks;
}

// ---------------------------------------------------------------------------
// Model CRUD
// ---------------------------------------------------------------------------

export async function createModel(
  model: Partial<ModelSchema> & { name: string },
): Promise<ModelResponse> {
  return request<ModelResponse>('/models', {
    method: 'POST',
    body: JSON.stringify({
      name: model.name,
      blocks: model.blocks ?? [],
      connections: model.connections ?? [],
      metadata: model.metadata ?? {},
    }),
  });
}

export async function listModels(): Promise<ModelResponse[]> {
  const data = await request<ModelsListResponse>('/models');
  return data.models;
}

export async function getModel(modelId: string): Promise<ModelResponse> {
  return request<ModelResponse>(`/models/${modelId}`);
}

export async function updateModel(
  modelId: string,
  model: ModelSchema,
): Promise<ModelResponse> {
  return request<ModelResponse>(`/models/${modelId}`, {
    method: 'PUT',
    body: JSON.stringify(model),
  });
}

export async function deleteModel(modelId: string): Promise<void> {
  await request<void>(`/models/${modelId}`, { method: 'DELETE' });
}

// ---------------------------------------------------------------------------
// Model sub-resources: blocks
// ---------------------------------------------------------------------------

export async function addBlock(
  modelId: string,
  block: BlockSchema,
): Promise<ModelResponse> {
  return request<ModelResponse>(`/models/${modelId}/blocks`, {
    method: 'POST',
    body: JSON.stringify(block),
  });
}

export async function removeBlock(
  modelId: string,
  blockId: string,
): Promise<ModelResponse> {
  return request<ModelResponse>(`/models/${modelId}/blocks/${blockId}`, {
    method: 'DELETE',
  });
}

// ---------------------------------------------------------------------------
// Model sub-resources: connections
// ---------------------------------------------------------------------------

export async function addConnection(
  modelId: string,
  connection: ConnectionSchema,
): Promise<ModelResponse> {
  return request<ModelResponse>(`/models/${modelId}/connections`, {
    method: 'POST',
    body: JSON.stringify(connection),
  });
}

export async function removeConnection(
  modelId: string,
  connection: ConnectionSchema,
): Promise<ModelResponse> {
  return request<ModelResponse>(`/models/${modelId}/connections`, {
    method: 'DELETE',
    body: JSON.stringify(connection),
  });
}

// ---------------------------------------------------------------------------
// Simulation (synchronous)
// ---------------------------------------------------------------------------

export async function simulate(
  modelId: string,
  config?: Partial<SimulationConfig>,
): Promise<SimulationResult> {
  return request<SimulationResult>(`/simulate/${modelId}`, {
    method: 'POST',
    body: config ? JSON.stringify(config) : undefined,
  });
}

// ---------------------------------------------------------------------------
// Model Export / Import / Validation
// ---------------------------------------------------------------------------

/**
 * Export a model as a .blocksim.json file download.
 *
 * Fetches the export endpoint and triggers a browser file-save dialog
 * by creating a temporary blob URL and clicking a hidden anchor element.
 */
export async function exportModel(modelId: string): Promise<void> {
  const res = await fetch(`${BASE}/models/${modelId}/export`);

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body.detail) detail = String(body.detail);
    } catch {
      // ignore parse errors
    }
    throw new Error(detail);
  }

  // Extract filename from Content-Disposition header, fallback to generic name.
  const disposition = res.headers.get('Content-Disposition') ?? '';
  const filenameMatch = disposition.match(/filename="?([^";\n]+)"?/);
  const filename = filenameMatch?.[1] ?? `model-${modelId}.blocksim.json`;

  // Create blob URL and trigger download via hidden anchor.
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();

  // Clean up.
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

/**
 * Import a model from a .blocksim.json file.
 *
 * Uploads the file as multipart/form-data. The backend validates the
 * file contents and returns the imported model with validation results.
 */
export async function importModel(file: File): Promise<ImportResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(`${BASE}/models/import`, {
    method: 'POST',
    body: formData,
    // NOTE: Do NOT set Content-Type header — the browser sets it
    // automatically with the correct multipart boundary.
  });

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body.detail) detail = String(body.detail);
    } catch {
      // ignore parse errors
    }
    throw new Error(detail);
  }

  return res.json() as Promise<ImportResponse>;
}

/**
 * Validate a stored model without re-importing.
 *
 * Runs the backend's multi-level validator (schema, referential, semantic)
 * and returns the validation result.
 */
export async function validateModel(modelId: string): Promise<ValidationResult> {
  const data = await request<{ validation: ValidationResult }>(
    `/models/${modelId}/validate`,
    { method: 'POST' },
  );
  return data.validation;
}

// ---------------------------------------------------------------------------
// WebSocket simulation streaming
// ---------------------------------------------------------------------------

export interface SimulationSocket {
  /** Send a message to the server (start/stop). */
  send: (msg: WsClientMessage) => void;
  /** Close the WebSocket connection. */
  close: () => void;
  /** The underlying WebSocket instance. */
  ws: WebSocket;
}

/**
 * Connect a WebSocket for real-time simulation streaming.
 *
 * @param modelId - The model to simulate.
 * @param onMessage - Called for each server message (frame/complete/error).
 * @param onClose - Called when the connection closes.
 * @param onError - Called on WebSocket error.
 * @returns A handle to send messages and close the connection.
 */
export function connectSimulationWs(
  modelId: string,
  onMessage: (msg: WsServerMessage) => void,
  onClose?: () => void,
  onError?: (event: Event) => void,
): SimulationSocket {
  // Build WebSocket URL relative to current page origin.
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/simulate/${modelId}`;

  const ws = new WebSocket(wsUrl);

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data) as WsServerMessage;
      onMessage(msg);
    } catch {
      console.error('Failed to parse WebSocket message:', event.data);
    }
  };

  ws.onclose = () => onClose?.();
  ws.onerror = (event) => onError?.(event);

  return {
    send: (msg: WsClientMessage) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(msg));
      }
    },
    close: () => {
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close();
      }
    },
    ws,
  };
}
