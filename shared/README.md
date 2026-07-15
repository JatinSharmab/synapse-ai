# Shared Contracts

This directory contains versioned, implementation-neutral contracts shared across services.

Phase 8 adds `genui.ts`, the canonical Zod `1.0` protocol for the eight allowlisted Gen-UI component
types. The frontend re-exports this schema and validates unknown payloads immediately before using
its fixed renderer registry. The equivalent Pydantic models live in
`ai-service/app/schemas/genui.py`.

Phase 10 adds `streaming.ts`, the strict client-side union for SSE lifecycle, token, Gen-UI,
guardrail, completion, and normalized error events. The frontend validates every parsed event and
requires its SSE `id` and `event` envelope fields to match the typed JSON data.
