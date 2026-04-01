/**
 * Validation Panel — collapsible panel displaying model validation results.
 *
 * Shows validation issues grouped by severity (error, warning, info).
 * Each issue is clickable to select/highlight the affected block on the canvas.
 * Displays issue count badges in the header.
 */

import { useCallback, useState, useMemo } from 'react';

import { useModelStore } from '../store/useModelStore';
import type { ValidationIssue, ValidationSeverity } from '../types';

// ---------------------------------------------------------------------------
// Severity config — color, label, sort order
// ---------------------------------------------------------------------------

const SEVERITY_CONFIG: Record<ValidationSeverity, { color: string; label: string; order: number }> = {
  error: { color: '#f87171', label: 'Errors', order: 0 },
  warning: { color: '#facc15', label: 'Warnings', order: 1 },
  info: { color: '#60a5fa', label: 'Info', order: 2 },
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ValidationPanel() {
  const validationResult = useModelStore((s) => s.validationResult);
  const selectBlock = useModelStore((s) => s.selectBlock);
  const [collapsed, setCollapsed] = useState(false);

  const toggleCollapsed = useCallback(() => {
    setCollapsed((prev) => !prev);
  }, []);

  const handleIssueClick = useCallback(
    (issue: ValidationIssue) => {
      if (issue.block_id) {
        selectBlock(issue.block_id);
      }
    },
    [selectBlock],
  );

  // Group issues by severity
  const groupedIssues = useMemo(() => {
    if (!validationResult) return [];
    const groups: { severity: ValidationSeverity; issues: ValidationIssue[] }[] = [];
    const byLevel = new Map<ValidationSeverity, ValidationIssue[]>();

    for (const issue of validationResult.issues) {
      const existing = byLevel.get(issue.severity);
      if (existing) {
        existing.push(issue);
      } else {
        byLevel.set(issue.severity, [issue]);
      }
    }

    // Sort by severity order
    for (const [severity, issues] of byLevel.entries()) {
      groups.push({ severity, issues });
    }
    groups.sort((a, b) => SEVERITY_CONFIG[a.severity].order - SEVERITY_CONFIG[b.severity].order);

    return groups;
  }, [validationResult]);

  // Count by severity
  const errorCount = validationResult?.issues.filter((i) => i.severity === 'error').length ?? 0;
  const warningCount = validationResult?.issues.filter((i) => i.severity === 'warning').length ?? 0;
  const infoCount = validationResult?.issues.filter((i) => i.severity === 'info').length ?? 0;
  const totalCount = errorCount + warningCount + infoCount;

  // Don't render anything if there's no validation result
  if (!validationResult) return null;

  return (
    <div className={`validation-panel ${collapsed ? 'validation-panel--collapsed' : ''}`}>
      {/* Header */}
      <button className="validation-panel__header" onClick={toggleCollapsed}>
        <span className="validation-panel__title">
          Validation
          <span className={`validation-panel__arrow ${collapsed ? 'validation-panel__arrow--collapsed' : ''}`}>
            {collapsed ? '\u25B6' : '\u25BC'}
          </span>
        </span>
        <span className="validation-panel__badges">
          {errorCount > 0 && (
            <span className="validation-panel__badge validation-panel__badge--error">
              {errorCount}
            </span>
          )}
          {warningCount > 0 && (
            <span className="validation-panel__badge validation-panel__badge--warning">
              {warningCount}
            </span>
          )}
          {infoCount > 0 && (
            <span className="validation-panel__badge validation-panel__badge--info">
              {infoCount}
            </span>
          )}
          {totalCount === 0 && (
            <span className="validation-panel__badge validation-panel__badge--ok">OK</span>
          )}
        </span>
      </button>

      {/* Issue list */}
      {!collapsed && (
        <div className="validation-panel__body">
          {validationResult.checksum_match === false && (
            <div className="validation-panel__checksum-warning">
              Checksum mismatch — file may have been modified externally
            </div>
          )}

          {totalCount === 0 ? (
            <div className="validation-panel__empty">
              Model is valid — no issues found.
            </div>
          ) : (
            groupedIssues.map((group) => {
              const config = SEVERITY_CONFIG[group.severity];
              return (
                <div key={group.severity} className="validation-panel__group">
                  <div
                    className="validation-panel__group-header"
                    style={{ color: config.color }}
                  >
                    {config.label} ({group.issues.length})
                  </div>
                  {group.issues.map((issue, idx) => (
                    <div
                      key={idx}
                      className={`validation-panel__issue ${issue.block_id ? 'validation-panel__issue--clickable' : ''}`}
                      onClick={() => handleIssueClick(issue)}
                      title={issue.block_id ? `Click to select block: ${issue.block_id}` : undefined}
                    >
                      <span
                        className="validation-panel__issue-dot"
                        style={{ backgroundColor: config.color }}
                      />
                      <span className="validation-panel__issue-text">
                        {issue.message}
                        {issue.block_id && (
                          <span className="validation-panel__issue-block">
                            {' '}[{issue.block_id}]
                          </span>
                        )}
                      </span>
                      <span className="validation-panel__issue-category">
                        {issue.category}
                      </span>
                    </div>
                  ))}
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
