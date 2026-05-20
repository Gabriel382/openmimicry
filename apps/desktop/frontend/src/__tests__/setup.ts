/**
 * Vitest global setup.
 *
 * Intentionally minimal — we keep `@testing-library/jest-dom` out of the
 * dep tree (smaller blast radius for `minimum-release-age`). Tests use
 * plain `expect` assertions against DOM properties.
 */

export {};
