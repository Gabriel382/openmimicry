# openmimicry-memory

Optional long-term memory adapters for OpenMimicry. The default local adapter
uses Python's standard-library SQLite implementation. Hindsight support is
loaded only when explicitly selected. Memory is disabled by default and raw
audio is never accepted by this package.

Local memory supports exact-fact deduplication, lexical recall, expiry, CRUD,
and JSON export. Extraction is either deterministic (no LLM) or handled by an
independently selected backend after the main reply completes. Provider
failure and deadline expiry are non-fatal to conversation. See
`docs/memory.md` in the repository root for configuration and privacy guidance.
