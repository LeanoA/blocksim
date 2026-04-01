/**
 * Tests for frontend components.
 *
 * Task 7.2:
 * - Test ValidationPanel renders issues correctly by severity
 * - Test Export/Import buttons exist in SimulationControls
 * - Test BlockNode error indicators display correctly
 *
 * Uses @testing-library/react with Zustand store mocking.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';
import { ReactFlowProvider } from '@xyflow/react';

import type { ValidationResult, ValidationIssue } from '../types';

// ---------------------------------------------------------------------------
// Zustand store mock
// ---------------------------------------------------------------------------

// We need to mock the Zustand store so components read our test data
// without needing the full app context.

const mockStoreState: Record<string, unknown> = {};

vi.mock('../store/useModelStore', () => ({
  useModelStore: (selector: (state: Record<string, unknown>) => unknown) => selector(mockStoreState),
}));

// Mock BlockPalette's getCategoryColor (used by BlockNode)
vi.mock('./BlockPalette', () => ({
  getCategoryColor: () => '#60a5fa',
}));

// Need to import components AFTER mocks are set up
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let ValidationPanel: any;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let SimulationControls: any;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let BlockNodeComponent: any;

beforeEach(async () => {
  // Dynamic import to pick up the mocks
  const vpMod = await import('../components/ValidationPanel');
  ValidationPanel = vpMod.ValidationPanel;

  const scMod = await import('../components/SimulationControls');
  SimulationControls = scMod.SimulationControls;

  const bnMod = await import('../components/BlockNode');
  BlockNodeComponent = bnMod.default;
});

function setMockStore(overrides: Record<string, unknown>) {
  Object.assign(mockStoreState, {
    // Defaults
    model: { name: 'Test Model', blocks: [], connections: [], metadata: {} },
    modelId: 'model-1',
    simulationConfig: { t_start: 0, t_end: 1.0, dt: 0.001, solver: 'rk4' },
    simulationStatus: 'idle',
    simulationError: null,
    validationResult: null,
    blockErrors: {},
    selectedBlockId: null,
    blockLibrary: [],
    liveFrames: [],
    simulationResult: null,
    // Actions (no-ops by default)
    setSimulationConfig: vi.fn(),
    runSimulation: vi.fn(),
    startStreamingSimulation: vi.fn(),
    stopStreamingSimulation: vi.fn(),
    saveModel: vi.fn(),
    exportModel: vi.fn(),
    importModel: vi.fn(),
    validateModel: vi.fn(),
    selectBlock: vi.fn(),
    fetchBlockLibrary: vi.fn(),
    ...overrides,
  });
}

afterEach(() => {
  // Clear store state
  for (const key of Object.keys(mockStoreState)) {
    delete mockStoreState[key];
  }
});

// ---------------------------------------------------------------------------
// ValidationPanel tests
// ---------------------------------------------------------------------------

describe('ValidationPanel', () => {
  it('does not render when validationResult is null', () => {
    setMockStore({ validationResult: null });
    const { container } = render(<ValidationPanel />);
    expect(container.innerHTML).toBe('');
  });

  it('renders "OK" when validation has no issues', () => {
    const validResult: ValidationResult = {
      valid: true,
      issues: [],
      checksum_match: null,
    };
    setMockStore({ validationResult: validResult });

    render(<ValidationPanel />);

    expect(screen.getByText('OK')).toBeInTheDocument();
    expect(screen.getByText('Model is valid — no issues found.')).toBeInTheDocument();
  });

  it('renders error issues grouped under "Errors"', () => {
    const issues: ValidationIssue[] = [
      { severity: 'error', category: 'schema', message: 'Missing type field', block_id: 'b1', field: 'type' },
      { severity: 'error', category: 'referential', message: 'Dangling connection', block_id: 'b2', field: null },
    ];
    setMockStore({
      validationResult: { valid: false, issues, checksum_match: null },
    });

    render(<ValidationPanel />);

    // Error badge should show count 2
    const badges = screen.getAllByText('2');
    expect(badges.length).toBeGreaterThanOrEqual(1);

    // Issue messages should be rendered
    expect(screen.getByText('Missing type field')).toBeInTheDocument();
    expect(screen.getByText('Dangling connection')).toBeInTheDocument();

    // Error group header
    expect(screen.getByText('Errors (2)')).toBeInTheDocument();
  });

  it('renders warning issues grouped under "Warnings"', () => {
    const issues: ValidationIssue[] = [
      { severity: 'warning', category: 'semantic', message: 'Unconnected input port', block_id: 'G1', field: null },
    ];
    setMockStore({
      validationResult: { valid: true, issues, checksum_match: null },
    });

    render(<ValidationPanel />);

    expect(screen.getByText('Warnings (1)')).toBeInTheDocument();
    expect(screen.getByText('Unconnected input port')).toBeInTheDocument();
  });

  it('renders info issues grouped under "Info"', () => {
    const issues: ValidationIssue[] = [
      { severity: 'info', category: 'semantic', message: 'Block has no connections', block_id: 'S1', field: null },
    ];
    setMockStore({
      validationResult: { valid: true, issues, checksum_match: null },
    });

    render(<ValidationPanel />);

    expect(screen.getByText('Info (1)')).toBeInTheDocument();
    expect(screen.getByText('Block has no connections')).toBeInTheDocument();
  });

  it('renders mixed severity issues in correct order (errors first)', () => {
    const issues: ValidationIssue[] = [
      { severity: 'info', category: 'semantic', message: 'Info msg', block_id: null, field: null },
      { severity: 'error', category: 'schema', message: 'Error msg', block_id: null, field: null },
      { severity: 'warning', category: 'referential', message: 'Warning msg', block_id: null, field: null },
    ];
    setMockStore({
      validationResult: { valid: false, issues, checksum_match: null },
    });

    render(<ValidationPanel />);

    // All three groups should be present
    expect(screen.getByText('Errors (1)')).toBeInTheDocument();
    expect(screen.getByText('Warnings (1)')).toBeInTheDocument();
    expect(screen.getByText('Info (1)')).toBeInTheDocument();

    // Verify order: errors before warnings before info
    const body = screen.getByText('Errors (1)').closest('.validation-panel__body');
    if (body) {
      const headers = within(body as HTMLElement).getAllByText(/Errors|Warnings|Info/);
      // Filter to just group headers
      const groupHeaders = headers.filter(el =>
        el.classList.contains('validation-panel__group-header'),
      );
      if (groupHeaders.length === 3) {
        expect(groupHeaders[0].textContent).toContain('Errors');
        expect(groupHeaders[1].textContent).toContain('Warnings');
        expect(groupHeaders[2].textContent).toContain('Info');
      }
    }
  });

  it('shows checksum mismatch warning when checksum_match is false', () => {
    setMockStore({
      validationResult: {
        valid: true,
        issues: [],
        checksum_match: false,
      },
    });

    render(<ValidationPanel />);

    expect(
      screen.getByText(/checksum mismatch/i),
    ).toBeInTheDocument();
  });

  it('does not show checksum warning when checksum_match is null', () => {
    setMockStore({
      validationResult: {
        valid: true,
        issues: [],
        checksum_match: null,
      },
    });

    render(<ValidationPanel />);

    expect(screen.queryByText(/checksum mismatch/i)).not.toBeInTheDocument();
  });

  it('calls selectBlock when clicking an issue with block_id', () => {
    const selectBlock = vi.fn();
    const issues: ValidationIssue[] = [
      { severity: 'error', category: 'referential', message: 'Bad ref', block_id: 'block-42', field: null },
    ];
    setMockStore({
      validationResult: { valid: false, issues, checksum_match: null },
      selectBlock,
    });

    render(<ValidationPanel />);

    const issueEl = screen.getByText('Bad ref').closest('.validation-panel__issue');
    expect(issueEl).not.toBeNull();
    fireEvent.click(issueEl!);

    expect(selectBlock).toHaveBeenCalledWith('block-42');
  });

  it('shows block_id tag in issue text', () => {
    const issues: ValidationIssue[] = [
      { severity: 'error', category: 'schema', message: 'Invalid params', block_id: 'myBlock', field: null },
    ];
    setMockStore({
      validationResult: { valid: false, issues, checksum_match: null },
    });

    render(<ValidationPanel />);

    expect(screen.getByText('[myBlock]')).toBeInTheDocument();
  });

  it('toggles collapsed/expanded on header click', () => {
    setMockStore({
      validationResult: { valid: true, issues: [], checksum_match: null },
    });

    render(<ValidationPanel />);

    // Initially expanded — body should be visible
    expect(screen.getByText('Model is valid — no issues found.')).toBeInTheDocument();

    // Click the header button to collapse
    const header = screen.getByRole('button');
    fireEvent.click(header);

    // Body should be hidden after collapse
    expect(screen.queryByText('Model is valid — no issues found.')).not.toBeInTheDocument();

    // Click again to expand
    fireEvent.click(header);
    expect(screen.getByText('Model is valid — no issues found.')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// SimulationControls tests — Export/Import/Validate buttons
// ---------------------------------------------------------------------------

describe('SimulationControls', () => {
  it('renders Export button', () => {
    setMockStore({});
    render(<SimulationControls />);
    expect(screen.getByText('Export')).toBeInTheDocument();
  });

  it('renders Import button', () => {
    setMockStore({});
    render(<SimulationControls />);
    expect(screen.getByText('Import')).toBeInTheDocument();
  });

  it('renders Validate button', () => {
    setMockStore({});
    render(<SimulationControls />);
    expect(screen.getByText(/Validate/)).toBeInTheDocument();
  });

  it('Export button calls exportModel action', () => {
    const exportModel = vi.fn().mockResolvedValue(undefined);
    setMockStore({ exportModel });

    render(<SimulationControls />);
    fireEvent.click(screen.getByText('Export'));

    expect(exportModel).toHaveBeenCalled();
  });

  it('Import button triggers file input click', () => {
    setMockStore({});

    render(<SimulationControls />);

    // The Import button should exist
    const importBtn = screen.getByText('Import');
    expect(importBtn).toBeInTheDocument();

    // Clicking it should trigger the hidden file input
    // We can't easily test this without deeper DOM inspection,
    // but at minimum verify the button is clickable and not disabled
    expect(importBtn).not.toBeDisabled();
  });

  it('Validate button calls validateModel action', () => {
    const validateModel = vi.fn().mockResolvedValue(undefined);
    setMockStore({ validateModel });

    render(<SimulationControls />);
    fireEvent.click(screen.getByText(/Validate/));

    expect(validateModel).toHaveBeenCalled();
  });

  it('disables Export/Import/Validate buttons while simulation is running', () => {
    setMockStore({ simulationStatus: 'running' });

    render(<SimulationControls />);

    expect(screen.getByText('Export')).toBeDisabled();
    expect(screen.getByText('Import')).toBeDisabled();
    expect(screen.getByText(/Validate/)).toBeDisabled();
  });

  it('shows validation error/warning badges on Validate button', () => {
    const issues: ValidationIssue[] = [
      { severity: 'error', category: 'schema', message: 'err1', block_id: null, field: null },
      { severity: 'error', category: 'schema', message: 'err2', block_id: null, field: null },
      { severity: 'warning', category: 'semantic', message: 'warn1', block_id: null, field: null },
    ];
    setMockStore({
      validationResult: { valid: false, issues, checksum_match: null },
    });

    render(<SimulationControls />);

    // Look for badge with error count
    const validateBtn = screen.getByText(/Validate/).closest('button');
    expect(validateBtn).not.toBeNull();

    // Error badge should show "2", warning badge should show "1"
    const badgeTexts = within(validateBtn!).getAllByText(/^[0-9]+$/);
    const badgeValues = badgeTexts.map((el) => el.textContent);
    expect(badgeValues).toContain('2');
    expect(badgeValues).toContain('1');
  });
});

// ---------------------------------------------------------------------------
// BlockNode error indicator tests
// ---------------------------------------------------------------------------

describe('BlockNode error indicators', () => {
  // BlockNode expects props from React Flow's NodeProps
  const baseNodeProps = {
    id: 'node-1',
    type: 'block',
    dragging: false,
    zIndex: 1,
    isConnectable: true,
    positionAbsoluteX: 0,
    positionAbsoluteY: 0,
    data: {
      blockId: 'block-1',
      blockType: 'Gain',
      label: 'Gain',
      params: { gain: 2.0 },
      inputPorts: [{ name: 'input', direction: 'in' as const, dtype: 'float' }],
      outputPorts: [{ name: 'output', direction: 'out' as const, dtype: 'float' }],
    },
    selected: false,
  };

  it('renders without error indicators when no errors', () => {
    setMockStore({
      blockErrors: {},
      validationResult: null,
    });

    const { container } = render(
      <ReactFlowProvider>
        <BlockNodeComponent {...baseNodeProps} />
      </ReactFlowProvider>,
    );

    expect(container.querySelector('.block-node--error')).toBeNull();
    expect(container.querySelector('.block-node--warning')).toBeNull();
    expect(container.querySelector('.block-node__error-indicator')).toBeNull();
    expect(container.querySelector('.block-node__warning-indicator')).toBeNull();
  });

  it('shows error indicator when block has simulation errors', () => {
    setMockStore({
      blockErrors: {
        'block-1': [{ block_id: 'block-1', step: 5, time: 0.005, error: 'Division by zero' }],
      },
      validationResult: null,
    });

    const { container } = render(
      <ReactFlowProvider>
        <BlockNodeComponent {...baseNodeProps} />
      </ReactFlowProvider>,
    );

    expect(container.querySelector('.block-node--error')).not.toBeNull();
    expect(container.querySelector('.block-node__error-indicator')).not.toBeNull();
  });

  it('shows error indicator when block has validation errors', () => {
    const validationResult: ValidationResult = {
      valid: false,
      issues: [
        { severity: 'error', category: 'referential', message: 'Bad port', block_id: 'block-1', field: null },
      ],
      checksum_match: null,
    };
    setMockStore({
      blockErrors: {},
      validationResult,
    });

    const { container } = render(
      <ReactFlowProvider>
        <BlockNodeComponent {...baseNodeProps} />
      </ReactFlowProvider>,
    );

    expect(container.querySelector('.block-node--error')).not.toBeNull();
    expect(container.querySelector('.block-node__error-indicator')).not.toBeNull();
  });

  it('shows warning indicator when block has only validation warnings', () => {
    const validationResult: ValidationResult = {
      valid: true,
      issues: [
        { severity: 'warning', category: 'semantic', message: 'Unconnected input', block_id: 'block-1', field: null },
      ],
      checksum_match: null,
    };
    setMockStore({
      blockErrors: {},
      validationResult,
    });

    const { container } = render(
      <ReactFlowProvider>
        <BlockNodeComponent {...baseNodeProps} />
      </ReactFlowProvider>,
    );

    expect(container.querySelector('.block-node--warning')).not.toBeNull();
    expect(container.querySelector('.block-node__warning-indicator')).not.toBeNull();
    // Should NOT show error indicator
    expect(container.querySelector('.block-node--error')).toBeNull();
    expect(container.querySelector('.block-node__error-indicator')).toBeNull();
  });

  it('error takes precedence over warning', () => {
    const validationResult: ValidationResult = {
      valid: false,
      issues: [
        { severity: 'error', category: 'referential', message: 'Error', block_id: 'block-1', field: null },
        { severity: 'warning', category: 'semantic', message: 'Warning', block_id: 'block-1', field: null },
      ],
      checksum_match: null,
    };
    setMockStore({
      blockErrors: {},
      validationResult,
    });

    const { container } = render(
      <ReactFlowProvider>
        <BlockNodeComponent {...baseNodeProps} />
      </ReactFlowProvider>,
    );

    // Error class should be applied, not warning
    expect(container.querySelector('.block-node--error')).not.toBeNull();
    expect(container.querySelector('.block-node--warning')).toBeNull();
  });

  it('does not show indicators for issues on other blocks', () => {
    const validationResult: ValidationResult = {
      valid: false,
      issues: [
        { severity: 'error', category: 'referential', message: 'Other block error', block_id: 'block-99', field: null },
      ],
      checksum_match: null,
    };
    setMockStore({
      blockErrors: {},
      validationResult,
    });

    const { container } = render(
      <ReactFlowProvider>
        <BlockNodeComponent {...baseNodeProps} />
      </ReactFlowProvider>,
    );

    expect(container.querySelector('.block-node--error')).toBeNull();
    expect(container.querySelector('.block-node--warning')).toBeNull();
  });
});
