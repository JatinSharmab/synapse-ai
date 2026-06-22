# API Contracts

## Status and Conventions

Unless marked as implemented, contracts in this document are **planned, versioned design contracts**.
Phase 3 implements the unversioned process-liveness endpoint `GET /health` on both backends,
`POST /api/v1/chat/invoke`, and `GET /api/v1/system/ai-provider` on the AI service. Exact future routes may evolve through recorded
architecture decisions before implementation.

- External base path: `/api/v1`
- Content type: `application/json` unless noted
- Streaming: Server-Sent Events (`text/event-stream`)
- Identifiers: opaque server-generated strings
- Timestamps: ISO 8601 UTC strings
- Durations and evidence time ranges: milliseconds unless the display field says otherwise
- Correlation: accept or generate `X-Correlation-ID`; return it in headers and error bodies
- Idempotency: ingestion control requests should accept an `Idempotency-Key`
- Unknown fields: reject at security-sensitive boundaries unless a versioned compatibility policy explicitly allows them

The gateway validates transport payloads and proxies them. The AI service performs authoritative domain validation and owns all AI behavior.

## Common Error Envelope

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request could not be accepted.",
    "details": [],
    "retryable": false
  },
  "correlation_id": "corr_opaque"
}
```

Public errors must not contain stack traces, prompts, secrets, provider payloads, or chain-of-thought. Planned stable code families include validation, authorization, rate limit, source not found, ingestion, provider unavailable, retrieval, guardrail blocked, and internal error.

## Health and Readiness

### `GET /health` — Implemented in Phase 1

Reports process liveness only. Both backends return the same field shape with a service-specific name.

```json
{
  "service": "ai-service",
  "status": "ok",
  "version": "0.1.0",
  "environment": "development"
}
```

Implemented service names are `synapse-gateway` and `synapse-ai-service`. The endpoint does not claim
dependency or AI readiness.

### `GET /api/v1/readiness` — Planned

Reports whether required dependencies and local indexes are ready to serve relevant traffic.

```json
{
  "status": "ready",
  "checks": {
    "metadata": "ready",
    "object_storage": "ready",
    "vector_index": "ready",
    "ai_provider": "mock"
  }
}
```

`degraded`, `warming`, and `not_ready` are valid status concepts. Liveness must not claim index readiness.

## Source and Upload Control

### `POST /api/v1/uploads/authorize`

Creates short-lived upload authorization for production browser-to-Supabase upload. Request fields include a sanitized filename, media type, byte size, checksum when available, and source kind (`pdf`, `video`, or `csv`). The response includes an opaque upload ID, signed upload information, expiry, and target object reference.

Large file bytes do not pass through this endpoint or the Vercel gateway.

### `POST /api/v1/ingestions`

Starts ingestion from an authorized stored object reference.

```json
{
  "upload_id": "upl_opaque",
  "object_ref": "obj_opaque",
  "source_kind": "pdf",
  "display_name": "policy.pdf",
  "options": {
    "transcribe_audio": false
  }
}
```

```json
{
  "ingestion_id": "ing_opaque",
  "source_id": "src_opaque",
  "status": "queued",
  "correlation_id": "corr_opaque"
}
```

The AI service verifies that the object reference is authorized and matches expected ownership, type, size, and checksum. Local-development direct upload endpoints, if later added, belong to FastAPI and must be disabled or constrained in production.

### `GET /api/v1/ingestions/{ingestion_id}`

Returns `queued`, `validating`, `processing`, `indexing`, `ready`, `failed`, or `cancelled`, plus safe progress, stage timings, and a normalized failure when applicable.

### `GET /api/v1/sources`

Lists authorized source metadata and readiness. Binary content, embedding vectors, hidden object paths, and credentials are never returned.

### `GET /api/v1/sources/{source_id}`

Returns trusted display metadata, modality, ingestion status, version/checksum metadata safe for display, and bounded processing summaries.

## Chat and Streaming

### `POST /api/v1/chat/invoke` — Implemented in Phase 2, provider-backed in Phase 3

Synchronously invokes the LangGraph workflow. `thread_id` is propagated for correlation only;
Phase 3 has no checkpointer, memory, retrieval, or database.

```json
{
  "message": "Summarize page 4 of the PDF document",
  "thread_id": "thread_opaque"
}
```

The safe response includes `request_id`, `thread_id`, `intent`, `route`, `final_response`, empty
citation/Gen-UI arrays, `guardrail_result`, public errors, safe trace events, safe inference metadata,
and a bounded `rewrite_count`. It excludes `user_query`, `draft_response`, retrieved context, tool
internals, prompts, credentials, and private reasoning.

`message` is trimmed and limited to 4,000 characters. `thread_id` is trimmed, limited to 128
characters, and restricted to letters, digits, `.`, `_`, `:`, and `-`. Unknown request fields fail
validation.

### `GET /api/v1/system/ai-provider` — Implemented in Phase 3

Returns only credential-free runtime provider information:

```json
{
  "provider": "mock",
  "models": {
    "chat": "mock-chat-v1",
    "vision": "mock-vision-v1",
    "embedding": "mock-embedding-v1"
  },
  "mock": true
}
```

The response never includes credentials, provider request payloads, prompts, or hidden reasoning.

### `POST /api/v1/runs`

Creates a run for a query.

```json
{
  "query": "What policy changes are supported by the uploaded sources?",
  "source_ids": ["src_doc", "src_video"],
  "response_mode": "stream",
  "conversation_id": "conv_opaque"
}
```

```json
{
  "run_id": "run_opaque",
  "status": "accepted",
  "stream_url": "/api/v1/runs/run_opaque/events",
  "correlation_id": "corr_opaque"
}
```

The query and source count are bounded. Source authorization is mandatory. The client cannot select arbitrary tools, prompts, models, or executable operations through this endpoint.

### `GET /api/v1/runs/{run_id}`

Returns the current run status and, when complete, the validated response envelope.

### `GET /api/v1/runs/{run_id}/events`

Proxies ordered SSE events from the AI service. Each event has a monotonically increasing sequence number and may include an SSE `id` for reconnection.

```text
event: route.selected
id: 3
data: {"schema_version":"1.0","run_id":"run_opaque","sequence":3,"route":"document_search"}
```

Planned event types:

- `run.accepted`
- `route.selected`
- `tool.started`
- `tool.completed`
- `evidence.available`
- `answer.delta`
- `ui.available`
- `sentinel.completed`
- `metrics.summary`
- `run.completed`
- `run.error`

Events expose safe operational traces only. They never include chain-of-thought, hidden prompts, credentials, or raw provider internals. Heartbeats may use SSE comments and carry no domain state.

## Response Envelope

```json
{
  "schema_version": "1.0",
  "run_id": "run_opaque",
  "status": "completed",
  "answer": "The supported answer appears here.",
  "citations": [],
  "components": [],
  "evidence": [],
  "safety": {
    "decision": "approve",
    "rewrite_count": 0,
    "finding_codes": []
  },
  "metrics": {
    "total_latency_ms": 0,
    "retrieval_latency_ms": 0,
    "generation_latency_ms": 0,
    "guardrail_latency_ms": 0,
    "provider_calls": 0,
    "estimated_input_tokens": 0,
    "estimated_output_tokens": 0
  },
  "correlation_id": "corr_opaque"
}
```

Metrics are operational estimates, not hidden reasoning. Fields unavailable for a route should be absent or explicitly nullable according to the eventual schema, never fabricated.

## Evidence and Citation Contracts

A normalized evidence item is a discriminated union by modality.

### Document Evidence

```json
{
  "type": "document",
  "evidence_id": "ev_opaque",
  "source_id": "src_opaque",
  "display_name": "policy.pdf",
  "page": 12,
  "excerpt": "Bounded source excerpt.",
  "chunk_id": "chunk_opaque",
  "scores": {
    "dense": 0.0,
    "lexical": 0.0,
    "fusion": 0.0,
    "rerank": 0.0
  }
}
```

### Video Evidence

```json
{
  "type": "video",
  "evidence_id": "ev_opaque",
  "source_id": "src_opaque",
  "display_name": "briefing.mp4",
  "start_ms": 42500,
  "end_ms": 58100,
  "description": "Bounded segment description.",
  "frame_ref": "frame_opaque",
  "segment_id": "segment_opaque"
}
```

### Analytics Evidence

```json
{
  "type": "analytics",
  "evidence_id": "ev_opaque",
  "source_id": "src_opaque",
  "dataset_version": "sha256:opaque",
  "operation": {
    "type": "mean",
    "column": "revenue"
  },
  "result": 125.5
}
```

A citation references `evidence_id` and optional claim IDs. The server resolves display name, page, and timestamp from trusted evidence. Model-authored location fields are never authoritative.

## Constrained Analytics Contract

### `POST /api/v1/analytics/execute`

This route may be used internally by orchestration or exposed with equivalent authorization. The operation is a versioned discriminated union. A representative request is:

```json
{
  "dataset_id": "src_csv",
  "operation": {
    "type": "group_by",
    "group_columns": ["region"],
    "aggregations": [
      {"column": "revenue", "function": "sum", "alias": "total_revenue"}
    ],
    "sort": [{"column": "total_revenue", "direction": "desc"}],
    "limit": 10
  }
}
```

Allowed types are `describe`, `count`, `sum`, `mean`, `min`, `max`, `group_by`, `sort`, `top_n`, and `aggregate`. Columns must exist in the validated dataset schema. Filters, cardinality, output rows, and execution time are bounded. No field accepts Python, SQL, JavaScript, or a general expression language.

## Gen-UI Contract

Components form a versioned discriminated union validated in Python with Pydantic and in TypeScript with Zod. The fixed allowlist is:

```text
text | metric | bar_chart | line_chart | pie_chart | table | citation_list | video_evidence
```

A representative component is:

```json
{
  "type": "bar_chart",
  "id": "component_opaque",
  "title": "Revenue by region",
  "data": [
    {"label": "North", "value": 120.0},
    {"label": "South", "value": 95.0}
  ],
  "x_key": "label",
  "series": [{"data_key": "value", "label": "Revenue"}],
  "evidence_ids": ["ev_analytics"]
}
```

Schemas must cap component counts, rows, series, labels, and text. Arbitrary properties, HTML, JSX, scripts, event handlers, and unsafe URL schemes are rejected. The frontend never evaluates component data as code.

## Evaluation Contracts

### `POST /api/v1/evaluations/runs`

Starts a bounded evaluation against a versioned local/authorized dataset and named suite. Network-backed provider evaluation must be explicit; mock evaluation is the automated-test default.

### `GET /api/v1/evaluations/runs/{evaluation_run_id}`

Returns suite version, provider mode, configuration fingerprint, status, aggregate metrics, per-case safe results, timings, and failures. Model-judge and deterministic metrics must be labeled separately.

## Versioning and Compatibility

Public envelopes and Gen-UI payloads carry `schema_version`. Breaking contract changes require a new API or schema version and a decision-log entry. Provider SDK types, database documents, and LangGraph internal state are not public API contracts.
