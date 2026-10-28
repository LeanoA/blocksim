/**
 * Tests for frontend TypeScript types and API client.
 *
 * Task 7.1:
 * - Verify type compilation (implicit — these tests import and use the types)
 * - Test API client methods (mock fetch, verify correct URLs, request formats, response parsing)
 * - Test exportModel triggers download
 * - Test importModel sends FormData
 * - Test validateModel returns ValidationResult
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import type {
  ValidationIssue,
  ValidationResult,
  ImportResponse,
  ExportEnvelope,
  BlockExecutionError,
  SimulationResult,
  ModelResponse,
} from '../types';

import {
  exportModel,
  importModel,
  validateModel,
  createModel,
  getModel,
  simulate,
  getBlockLibrary,
} from '../api/client';

// ---------------------------------------------------------------------------
// Type compilation tests (if these compile, the types are correct)
// ---------------------------------------------------------------------------

describe('TypeScript types compile correctly', () => {
  it('ValidationIssue has all required fields', () => {
    const issue: ValidationIssue = {
      severity: 'error',
      category: 'schema',
      message: 'Missing required field',
      block_id: 'block-1',
      field: 'type',
    };
    expect(issue.severity).toBe('error');
    expect(issue.category).toBe('schema');
    expect(issue.message).toBe('Missing required field');
    expect(issue.block_id).toBe('block-1');
    expect(issue.field).toBe('type');
  });

  it('ValidationIssue block_id and field can be null', () => {
    const issue: ValidationIssue = {
      severity: 'warning',
      category: 'semantic',
      message: 'Unconnected port',
      block_id: null,
      field: null,
    };
    expect(issue.block_id).toBeNull();
    expect(issue.field).toBeNull();
  });

  it('ValidationResult has valid, issues, checksum_match', () => {
    const result: ValidationResult = {
      valid: true,
      issues: [],
      checksum_match: null,
    };
    expect(result.valid).toBe(true);
    expect(result.issues).toHaveLength(0);
    expect(result.checksum_match).toBeNull();
  });

  it('ImportResponse has id, model, validation', () => {
    const res: ImportResponse = {
      id: 'model-123',
      model: { name: 'Test', blocks: [], connections: [], metadata: {} },
      validation: { valid: true, issues: [], checksum_match: true },
    };
    expect(res.id).toBe('model-123');
    expect(res.model.name).toBe('Test');
    expect(res.validation.valid).toBe(true);
  });

  it('ExportEnvelope has all envelope fields', () => {
    const envelope: ExportEnvelope = {
      schema_version: '1.0.0',
      exported_at: '2026-03-31T12:00:00Z',
      blocksim_version: '0.1.0',
      checksum: 'abc123',
      model: { name: 'Test', blocks: [], connections: [], metadata: {} },
    };
    expect(envelope.schema_version).toBe('1.0.0');
    expect(envelope.checksum).toBe('abc123');
  });

  it('BlockExecutionError has block_id, step, time, error', () => {
    const err: BlockExecutionError = {
      block_id: 'R1',
      step: 5,
      time: 0.005,
      error: 'Division by zero',
    };
    expect(err.block_id).toBe('R1');
    expect(err.step).toBe(5);
    expect(err.time).toBe(0.005);
    expect(err.error).toBe('Division by zero');
  });

  it('SimulationResult supports block_errors and status', () => {
    const result: SimulationResult = {
      time: [0, 0.001],
      signals: { out: [1.0, 2.0] },
      block_errors: {
        R1: [{ block_id: 'R1', step: 0, time: 0, error: 'fail' }],
      },
      status: 'completed_with_errors',
    };
    expect(result.block_errors).toBeDefined();
    expect(result.status).toBe('completed_with_errors');
  });

  it('SimulationResult block_errors and status are optional', () => {
    const result: SimulationResult = {
      time: [0, 0.001],
      signals: { out: [1.0, 2.0] },
    };
    expect(result.block_errors).toBeUndefined();
    expect(result.status).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// API client method tests
// ---------------------------------------------------------------------------

describe('API client', () => {
  const mockFetch = vi.fn();
  let originalFetch: typeof globalThis.fetch;

  beforeEach(() => {
    originalFetch = globalThis.fetch;
    globalThis.fetch = mockFetch;
    mockFetch.mockReset();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  // Helper to create a mock Response
  function jsonResponse(data: unknown, status = 200, headers: Record<string, string> = {}): Response {
    const headersObj = new Headers(headers);
    headersObj.set('Content-Type', 'application/json');
    return {
      ok: status >= 200 && status < 300,
      status,
      headers: headersObj,
      json: async () => data,
      blob: async () => new Blob([JSON.stringify(data)], { type: 'application/json' }),
      text: async () => JSON.stringify(data),
    } as Response;
  }

  // ---- getBlockLibrary ----

  describe('getBlockLibrary', () => {
    it('fetches GET /api/blocks/library', async () => {
      const blocks = [
        { type: 'Gain', params: { gain: 1 }, input_ports: [], output_ports: [] },
      ];
      mockFetch.mockResolvedValue(jsonResponse({ blocks }));

      const result = await getBlockLibrary();

      expect(mockFetch).toHaveBeenCalledOnce();
      const [url, opts] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/blocks/library');
      expect(opts?.method ?? 'GET').toBe('GET');
      expect(result).toEqual(blocks);
    });
  });

  // ---- createModel ----

  describe('createModel', () => {
    it('sends POST /api/models with JSON body', async () => {
      const modelResponse: ModelResponse = {
        id: 'model-1',
        model: { name: 'New Model', blocks: [], connections: [], metadata: {} },
      };
      mockFetch.mockResolvedValue(jsonResponse(modelResponse));

      const result = await createModel({ name: 'New Model' });

      expect(mockFetch).toHaveBeenCalledOnce();
      const [url, opts] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/models');
      expect(opts.method).toBe('POST');
      expect(opts.headers?.['Content-Type']).toBe('application/json');
      const body = JSON.parse(opts.body);
      expect(body.name).toBe('New Model');
      expect(result).toEqual(modelResponse);
    });
  });

  // ---- getModel ----

  describe('getModel', () => {
    it('fetches GET /api/models/{id}', async () => {
      const modelResponse: ModelResponse = {
        id: 'model-42',
        model: { name: 'Test', blocks: [], connections: [], metadata: {} },
      };
      mockFetch.mockResolvedValue(jsonResponse(modelResponse));

      const result = await getModel('model-42');

      const [url] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/models/model-42');
      expect(result).toEqual(modelResponse);
    });
  });

  // ---- simulate ----

  describe('simulate', () => {
    it('sends POST /api/simulate/{id} with config', async () => {
      const simResult: SimulationResult = {
        time: [0, 0.001, 0.002],
        signals: { out: [1, 2, 3] },
      };
      mockFetch.mockResolvedValue(jsonResponse(simResult));

      const result = await simulate('model-1', { t_end: 1.0, dt: 0.001, solver: 'rk4', t_start: 0 });

      const [url, opts] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/simulate/model-1');
      expect(opts.method).toBe('POST');
      const body = JSON.parse(opts.body);
      expect(body.t_end).toBe(1.0);
      expect(body.dt).toBe(0.001);
      expect(result).toEqual(simResult);
    });

    it('parses block_errors and status from response', async () => {
      const simResult: SimulationResult = {
        time: [0, 0.001],
        signals: { out: [1, NaN] },
        block_errors: {
          R1: [{ block_id: 'R1', step: 1, time: 0.001, error: 'test error' }],
        },
        status: 'completed_with_errors',
      };
      mockFetch.mockResolvedValue(jsonResponse(simResult));

      const result = await simulate('model-1');

      expect(result.block_errors).toBeDefined();
      expect(result.block_errors!['R1']).toHaveLength(1);
      expect(result.status).toBe('completed_with_errors');
    });
  });

  // ---- exportModel ----

  describe('exportModel', () => {
    it('fetches GET /api/models/{id}/export and triggers download', async () => {
      const envelope: ExportEnvelope = {
        schema_version: '1.0.0',
        exported_at: '2026-03-31T12:00:00Z',
        blocksim_version: '0.1.0',
        checksum: 'abc123',
        model: { name: 'Test Circuit', blocks: [], connections: [], metadata: {} },
      };

      // Mock blob and URL
      const mockBlob = new Blob([JSON.stringify(envelope)], { type: 'application/json' });
      const mockUrl = 'blob:http://localhost/mock-url';

      const createObjectURLMock = vi.fn().mockReturnValue(mockUrl);
      const revokeObjectURLMock = vi.fn();
      URL.createObjectURL = createObjectURLMock;
      URL.revokeObjectURL = revokeObjectURLMock;

      // Track anchor element created for download
      const clickMock = vi.fn();
      const appendChildMock = vi.spyOn(document.body, 'appendChild').mockImplementation((el) => {
        // Capture the click
        return el;
      });
      const removeChildMock = vi.spyOn(document.body, 'removeChild').mockImplementation((el) => el);

      // Mock createElement to intercept anchor
      let capturedAnchor: HTMLAnchorElement | null = null;
      const origCreateElement = document.createElement.bind(document);
      vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
        const el = origCreateElement(tag);
        if (tag === 'a') {
          capturedAnchor = el as HTMLAnchorElement;
          el.click = clickMock;
        }
        return el;
      });

      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        headers: new Headers({
          'Content-Disposition': 'attachment; filename="Test_Circuit.blocksim.json"',
          'Content-Type': 'application/json',
        }),
        blob: async () => mockBlob,
        json: async () => envelope,
      } as Response);

      await exportModel('model-1');

      // Verify fetch call
      const [url] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/models/model-1/export');

      // Verify download was triggered
      expect(createObjectURLMock).toHaveBeenCalledWith(mockBlob);
      expect(clickMock).toHaveBeenCalled();
      expect(revokeObjectURLMock).toHaveBeenCalledWith(mockUrl);

      // Verify anchor had correct attributes
      expect(capturedAnchor).not.toBeNull();
      expect(capturedAnchor!.download).toBe('Test_Circuit.blocksim.json');
      expect(capturedAnchor!.href).toBe(mockUrl);

      // Cleanup
      appendChildMock.mockRestore();
      removeChildMock.mockRestore();
      vi.mocked(document.createElement).mockRestore();
    });

    it('uses fallback filename if Content-Disposition is missing', async () => {
      const mockBlob = new Blob(['{}'], { type: 'application/json' });
      const mockUrl = 'blob:http://localhost/mock-url-2';

      URL.createObjectURL = vi.fn().mockReturnValue(mockUrl);
      URL.revokeObjectURL = vi.fn();

      let capturedAnchor: HTMLAnchorElement | null = null;
      const origCreateElement = document.createElement.bind(document);
      vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
        const el = origCreateElement(tag);
        if (tag === 'a') {
          capturedAnchor = el as HTMLAnchorElement;
          el.click = vi.fn();
        }
        return el;
      });
      vi.spyOn(document.body, 'appendChild').mockImplementation((el) => el);
      vi.spyOn(document.body, 'removeChild').mockImplementation((el) => el);

      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        headers: new Headers({}),
        blob: async () => mockBlob,
      } as Response);

      await exportModel('xyz-123');

      expect(capturedAnchor).not.toBeNull();
      expect(capturedAnchor!.download).toBe('model-xyz-123.blocksim.json');

      // Cleanup
      vi.restoreAllMocks();
    });

    it('throws on non-2xx response', async () => {
      mockFetch.mockResolvedValue(
        jsonResponse({ detail: 'Not Found' }, 404),
      );

      await expect(exportModel('bad-id')).rejects.toThrow('Not Found');
    });
  });

  // ---- importModel ----

  describe('importModel', () => {
    it('sends POST /api/models/import with FormData', async () => {
      const importRes: ImportResponse = {
        id: 'imported-1',
        model: { name: 'Imported', blocks: [], connections: [], metadata: {} },
        validation: { valid: true, issues: [], checksum_match: true },
      };
      mockFetch.mockResolvedValue(jsonResponse(importRes, 201));

      const file = new File(
        [JSON.stringify({ model: { name: 'Imported' } })],
        'test.blocksim.json',
        { type: 'application/json' },
      );

      const result = await importModel(file);

      expect(mockFetch).toHaveBeenCalledOnce();
      const [url, opts] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/models/import');
      expect(opts.method).toBe('POST');

      // Body should be FormData
      expect(opts.body).toBeInstanceOf(FormData);
      const formData = opts.body as FormData;
      expect(formData.get('file')).toBeInstanceOf(File);

      // Should NOT set Content-Type header (browser sets multipart boundary)
      expect(opts.headers).toBeUndefined();

      // Verify response parsing
      expect(result.id).toBe('imported-1');
      expect(result.model.name).toBe('Imported');
      expect(result.validation.valid).toBe(true);
      expect(result.validation.checksum_match).toBe(true);
    });

    it('returns validation issues from response', async () => {
      const importRes: ImportResponse = {
        id: 'imported-2',
        model: { name: 'Bad Model', blocks: [], connections: [], metadata: {} },
        validation: {
          valid: false,
          issues: [
            { severity: 'error', category: 'referential', message: 'Unknown block type', block_id: 'b1', field: null },
            { severity: 'warning', category: 'semantic', message: 'Unconnected port', block_id: 'b2', field: 'input' },
          ],
          checksum_match: false,
        },
      };
      mockFetch.mockResolvedValue(jsonResponse(importRes, 201));

      const file = new File(['{}'], 'bad.json', { type: 'application/json' });
      const result = await importModel(file);

      expect(result.validation.valid).toBe(false);
      expect(result.validation.issues).toHaveLength(2);
      expect(result.validation.issues[0].severity).toBe('error');
      expect(result.validation.checksum_match).toBe(false);
    });

    it('throws on non-2xx response', async () => {
      mockFetch.mockResolvedValue(
        jsonResponse({ detail: 'File too large' }, 413),
      );

      const file = new File(['x'.repeat(100)], 'big.json');
      await expect(importModel(file)).rejects.toThrow('File too large');
    });
  });

  // ---- validateModel ----

  describe('validateModel', () => {
    it('sends POST /api/models/{id}/validate and returns ValidationResult', async () => {
      const validationResult: ValidationResult = {
        valid: true,
        issues: [],
        checksum_match: null,
      };
      mockFetch.mockResolvedValue(
        jsonResponse({ validation: validationResult }),
      );

      const result = await validateModel('model-1');

      const [url, opts] = mockFetch.mock.calls[0];
      expect(url).toBe('/api/models/model-1/validate');
      expect(opts.method).toBe('POST');
      expect(opts.headers?.['Content-Type']).toBe('application/json');

      expect(result).toEqual(validationResult);
    });

    it('returns validation issues when model has problems', async () => {
      const validationResult: ValidationResult = {
        valid: false,
        issues: [
          { severity: 'error', category: 'schema', message: 'Missing type', block_id: null, field: 'type' },
          { severity: 'warning', category: 'semantic', message: 'Unconnected port', block_id: 'G1', field: null },
          { severity: 'info', category: 'semantic', message: 'Unused block', block_id: 'S1', field: null },
        ],
        checksum_match: null,
      };
      mockFetch.mockResolvedValue(
        jsonResponse({ validation: validationResult }),
      );

      const result = await validateModel('model-2');

      expect(result.valid).toBe(false);
      expect(result.issues).toHaveLength(3);
      expect(result.issues[0].severity).toBe('error');
      expect(result.issues[1].severity).toBe('warning');
      expect(result.issues[2].severity).toBe('info');
    });

    it('throws on non-2xx response', async () => {
      mockFetch.mockResolvedValue(
        jsonResponse({ detail: 'Model not found' }, 404),
      );

      await expect(validateModel('bad-id')).rejects.toThrow('Model not found');
    });
  });

  // ---- Error handling ----

  describe('error handling', () => {
    it('throws with detail from backend error body', async () => {
      mockFetch.mockResolvedValue(
        jsonResponse({ detail: 'Validation failed: invalid block type' }, 422),
      );

      await expect(getModel('bad-model')).rejects.toThrow(
        'Validation failed: invalid block type',
      );
    });

    it('throws generic HTTP error when body has no detail', async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        status: 500,
        headers: new Headers(),
        json: async () => { throw new Error('Not JSON'); },
      } as unknown as Response);

      await expect(getModel('error-model')).rejects.toThrow('HTTP 500');
    });
  });
});
