/**
 * Vitest test setup — runs before each test file.
 *
 * Extends vitest matchers with @testing-library/jest-dom for
 * DOM-specific assertions (toBeInTheDocument, toHaveClass, etc.).
 */

import '@testing-library/jest-dom/vitest';
