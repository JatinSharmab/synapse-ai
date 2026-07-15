# API Contracts

## Status and Conventions

Unless marked as implemented, contracts in this document are **planned, versioned design contracts**.
Through Phase 13, the repository implements backend liveness, AI retrieval readiness, synchronous and SSE
AI-service chat, provider-status, local document CRUD, hybrid document search, local video
upload/list, semantic
video search, local dataset CRUD, constrained analytics execution, secure Gen-UI responses, and
debug-gated document retrieval endpoints described below. Exact
future routes may evolve through recorded architecture decisions before implementation.

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

### `GET /ready` — Implemented in Phase 12

Reports whether required dependencies and local indexes are ready to serve relevant traffic.

```json
{
  "service": "synapse-ai-service",
  "status": "ready",
  "documents": {"state": "ready", "durable_records": 3, "indexed_records": 3, "rebuilt": false, "error": null},
  "videos": {"state": "ready", "durable_records": 2, "indexed_records": 2, "rebuilt": true, "error": null},
  "checked_at": "2026-07-09T00:00:00Z"
}
```

The endpoint returns HTTP 503 with `status=not_ready` while either namespace is starting,
rebuilding, or failed. `GET /health` remains fast and never waits for reconciliation.

## Source and Upload Control

### `POST /api/v1/uploads/presign` — Implemented in Phase 12

Creates short-lived production browser-to-Supabase upload authorization. The strict request contains
`asset_type` (`document|video`), a plain filename, allowed content type, and bounded `size_bytes`.
The response contains only `signed_upload_url`, generated `object_path`, and `expires_at`; the
Supabase service-role credential is never serialized.

Large file bytes do not pass through this endpoint or the Vercel gateway.

### `POST /api/v1/documents/from-storage` and `POST /api/v1/videos/from-storage` — Phase 12

Starts ingestion from an authorized stored object reference.

```json
{
  "object_path": "documents/0123456789abcdef0123456789abcdef/policy.pdf"
}
```

The service resolves a matching unexpired, unconsumed upload intent, downloads the private object
with server credentials under the configured byte limit, verifies the exact authorized size, runs
the existing ingestion pipeline, and marks the intent consumed. Replay returns HTTP 409. Direct
multipart development endpoints remain disabled in production.

### `POST /api/v1/documents` — Implemented in Phase 4 for local development

Accepts one bounded `multipart/form-data` field named `file`. The file must have a `.pdf` extension,
an `application/pdf` media type, a PDF signature, and a readable, unencrypted structure within the
configured size/page limits. The endpoint returns HTTP 201 with trusted document metadata:

```json
{
  "document_id": "opaque_uuid",
  "filename": "synapse-policy.pdf",
  "page_count": 3,
  "chunk_count": 3,
  "checksum": "sha256_hex",
  "created_at": "2026-07-02T00:00:00Z",
  "ocr_required": false
}
```

Low/no-text PDFs return a successful record with `ocr_required=true` and `chunk_count=0`; OCR is not
started. Direct upload is disabled with HTTP 403 when `APP_ENV=production`.

### `GET /api/v1/documents` — Implemented in Phase 4

Returns `{"documents": [...]}` using the document metadata shape above. Embeddings, chunk text,
storage paths, and credentials are not exposed.

### `DELETE /api/v1/documents/{document_id}` — Implemented in Phase 4

Deletes the document's authoritative metadata, durable chunks/embeddings, and Chroma entries. It
returns HTTP 204 or a safe HTTP 404 when the identifier does not exist.

### `POST /api/v1/search/documents` — Hybrid retrieval in Phase 5

Performs query normalization, vector retrieval, BM25 retrieval, RRF, local CPU reranking, and bounded
context selection. `top_k` is optional (1–20), and results are capped by the configured final-context limit;
`document_ids` is an optional unique filter of at most 50 identifiers.

```json
{
  "query": "What is the refund policy?",
  "top_k": 3,
  "document_ids": ["opaque_uuid"]
}
```

```json
{
  "results": [
    {
      "text": "Bounded source text.",
      "document_id": "opaque_uuid",
      "filename": "synapse-policy.pdf",
      "page": 2,
      "chunk_id": "opaque_chunk_id",
      "similarity_score": 0.82
    }
  ],
  "inference_metadata": {
    "provider": "mock",
    "operation": "embed",
    "model": "mock-embedding-v1",
    "latency_ms": 0,
    "retry_count": 0,
    "token_usage": null
  }
}
```

All provenance fields are resolved from authoritative stored chunks, never accepted from model
output. The backward-compatible `similarity_score` field contains the bounded final relevance score
after Phase 5 selection; intermediate vector, BM25, RRF, and rerank scores are not exposed here.

### `POST /api/v1/debug/retrieval/documents` — Registered only with `DEBUG=true`

Accepts the document-search fields plus `mode: "vector_only" | "hybrid"`. Its response contains the
normalized query, mode, safe embedding metadata, and ranked `vector_candidates`, `bm25_candidates`,
`fused_candidates`, `reranked_candidates`, and `final_context`. Candidate records expose trusted
evidence identifiers, filename/page/chunk index, text, stage score, and rank; they never expose
embeddings, prompts, credentials, or private reasoning.

When `DEBUG=false` (the default), this route is not registered, returns HTTP 404, and does not appear
in OpenAPI. The regular search and chat responses never gain retrieval-debug fields.

### `POST /api/v1/videos` — Implemented in Phase 6 for local development

Accepts one bounded `multipart/form-data` field named `file`. The file must use `.mp4`, declare
`video/mp4` or `application/mp4`, contain an MP4 signature, and satisfy configured byte/duration
limits. Successful HTTP 201 responses include trusted video metadata, segment count, and
`ready|partial` processing state plus `completed|disabled|unavailable` visual/transcription states.
Direct upload returns HTTP 403 in production mode.

### `GET /api/v1/videos` — Implemented in Phase 6

Returns `{"videos": [...]}` with video metadata and processing/enrichment state. It never returns
binary content, embedding vectors, credentials, absolute artifact paths, or provider payloads.

### `POST /api/v1/search/videos` — Implemented in Phase 6

Accepts `{"query": "...", "top_k": 3}` and performs semantic retrieval over temporal segments.
Each result contains only repository-resolved provenance:

```json
{
  "results": [
    {
      "video_id": "video_opaque",
      "filename": "portfolio.mp4",
      "segment_id": "segment_opaque",
      "start_seconds": 30.0,
      "end_seconds": 60.0,
      "description": "Bounded transcript and visual evidence.",
      "score": 0.82
    }
  ],
  "inference_metadata": {
    "provider": "mock",
    "operation": "embed",
    "model": "mock-embedding-v1",
    "latency_ms": 0,
    "retry_count": 0,
    "token_usage": null
  }
}
```

### `GET /api/v1/ingestions/{ingestion_id}`

Returns `queued`, `validating`, `processing`, `indexing`, `ready`, `failed`, or `cancelled`, plus safe progress, stage timings, and a normalized failure when applicable.

### `GET /api/v1/sources`

Lists authorized source metadata and readiness. Binary content, embedding vectors, hidden object paths, and credentials are never returned.

### `GET /api/v1/sources/{source_id}`

Returns trusted display metadata, modality, ingestion status, version/checksum metadata safe for display, and bounded processing summaries.

## Chat and Streaming

### `POST /api/v1/chat/invoke` — Layered Sentinel workflow through Phase 9

Synchronously invokes the LangGraph workflow. `thread_id` is propagated for correlation only;
Phase 9 still has no checkpointer or conversation memory. Document-routed queries use hybrid
retrieval; video-routed queries use semantic temporal-segment retrieval; analytics queries use a
schema-constrained plan followed by deterministic execution over an uploaded CSV.

```json
{
  "message": "Find the refund policy in my documents.",
  "thread_id": "thread_opaque"
}
```

The safe response includes `request_id`, `thread_id`, `intent`, `route`, `final_response`, a
document or video citation array when evidence is retrieved, a validated Gen-UI array when a
material deterministic analytics visualization is available,
`guardrail_result`, public
errors, safe trace events, safe inference metadata, and a bounded `rewrite_count`. Each document
citation uses the retrieved `document_id`, `filename`, `page`, and `chunk_id`; the model cannot supply
those fields. Video citations analogously use trusted `video_id`, filename, `segment_id`, and
start/end seconds. The response excludes `user_query`, `draft_response`, retrieved context, tool
internals, prompts, credentials, and private reasoning.

`message` is trimmed and limited to 4,000 characters. `thread_id` is trimmed, limited to 128
characters, and restricted to letters, digits, `.`, `_`, `:`, and `-`. Unknown request fields fail
validation.

`guardrail_result` has this public shape:

```json
{
  "decision": "approve",
  "groundedness_score": 1.0,
  "citation_coverage": 1.0,
  "prompt_injection_detected": false,
  "schema_valid": true,
  "reasons": ["GUARDRAILS_PASSED"],
  "rewrite_required": false
}
```

`decision` is exactly `approve`, `rewrite`, or `block`; both scores are between zero and one.
Reasons are safe machine-readable codes and never prompts, model rationale, raw secrets, or private
reasoning. An input-blocked request returns a safe response with `intent: null`, `route: null`, empty
citations/Gen-UI, and no provider inference metadata because routing never ran.

### `POST /api/v1/chat/stream` — Implemented in Phase 10

The same strict JSON request accepted by `/invoke` produces `text/event-stream`. Browsers use a
streaming `fetch()` POST rather than native `EventSource`, because the request has a JSON body. The
endpoint is available directly on FastAPI and through the Express gateway at the same path.

FastAPI and the gateway return these headers:

```text
Content-Type: text/event-stream; charset=utf-8
Cache-Control: no-cache, no-transform
X-Request-ID: opaque_request_id
X-Correlation-ID: opaque_correlation_id
X-Accel-Buffering: no
```

Every domain event uses an SSE `id` equal to its positive monotonic `sequence`, an `event` equal to
its JSON `type`, and one strict JSON `data` object:

```text
id: 2
event: route.selected
data: {"schema_version":"1.0","request_id":"req_opaque","correlation_id":"corr_opaque","sequence":2,"type":"route.selected","route":"document_search"}
```

Implemented event types are:

- `request.started`: safe request/correlation/thread identifiers.
- `route.selected`: selected route only.
- `retrieval.started`: `document_search` or `video_search` tool name.
- `retrieval.completed`: tool, bounded candidate count, and stage latency.
- `generation.started`: selected route; no prompt or draft.
- `generation.token`: one ordered chunk from the final guardrail-checked response.
- `genui.created`: validated Gen-UI components only.
- `guardrail.completed`: public `GuardrailResult` and rewrite count.
- `response.completed`: final response, trusted citations, citation count, total latency, and rewrite
  count.
- `error`: normalized code/message/retryability without exception, prompt, or provider internals.

Heartbeat frames are SSE comments (`: heartbeat`) and contain no domain state. The FastAPI stream
has configurable total and heartbeat intervals, observes client disconnects, requests iterator
shutdown, and normalizes graph failures. The current provider contract returns complete text, so
token events are deliberately emitted only after Sentinel has accepted or replaced the final
response; unsafe drafts are never streamed.

The Express gateway accepts only this bounded JSON chat route. It performs Zod validation, generates
and propagates request/correlation IDs, applies an in-memory fixed-window rate limit, sets CORS and
security headers, enforces an upstream timeout, forwards the request, preserves SSE bytes, aborts
upstream work on client disconnect, and emits normalized errors for invalid JSON, upstream failure,
timeout, or premature disconnect. It contains no prompts, graph, retrieval, embedding, provider, or
agent code.

The gateway intentionally does not register document or video multipart upload routes. Existing
direct FastAPI uploads remain local-development endpoints. Production large binaries must use the
browser-to-object-storage signed-upload architecture and must not traverse a Vercel gateway.

For the Phase 15 production frontend, the gateway also exposes a fixed pass-through allowlist for
small JSON control reads: `GET /ready`, `GET /api/v1/system/ai-provider`,
`GET /api/v1/documents`, `GET /api/v1/videos`, `GET /api/v1/datasets`, and
`GET /api/v1/evaluations/summaries?limit=...`. Evaluation `limit` is validated as an integer from
1 through 100. These routes propagate request/correlation IDs, time out, normalize upstream errors,
and contain no AI or retrieval logic. They are not a generic proxy.

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

### `POST /api/v1/datasets` — Implemented in Phase 7 for local development

Accepts one bounded `multipart/form-data` field named `file`. The file must use `.csv`, declare an
allowed CSV/text media type, be UTF-8, and have unique non-empty headers with consistent row widths.
Byte, row, and column counts are configuration-bounded. The HTTP 201 response contains:

```json
{
  "dataset_id": "dataset_opaque",
  "filename": "regional-revenue.csv",
  "columns": [
    {"name": "region", "data_type": "string", "nullable": false},
    {"name": "revenue", "data_type": "number", "nullable": false}
  ],
  "row_count": 6,
  "checksum": "sha256_hex",
  "created_at": "2026-07-02T00:00:00Z"
}
```

Direct upload returns HTTP 403 in production mode.

### `GET /api/v1/datasets` — Implemented in Phase 7

Returns `{"datasets": [...]}` with trusted metadata only. Raw rows are not exposed by this route.

### `DELETE /api/v1/datasets/{dataset_id}` — Implemented in Phase 7

Deletes the local authoritative dataset or returns a safe HTTP 404.

### `POST /api/v1/analytics/execute` — Implemented in Phase 7

Executes one Pydantic-discriminated operation against an authoritative local dataset. A grouped
request is:

```json
{
  "dataset_id": "src_csv",
  "operation": {
    "operation": "group_by",
    "grouping_fields": ["region"],
    "aggregation": "sum",
    "aggregation_field": "revenue",
    "limit": 10
  }
}
```

The response always uses the deterministic result shape:

```json
{
  "summary": "Computed sum grouped by region: region=North, sum_revenue=200.75.",
  "columns": ["region", "sum_revenue"],
  "result_rows": [{"region": "North", "sum_revenue": 200.75}],
  "statistics": {"group_count": 1, "returned_rows": 1},
  "recommended_visualization": "bar_chart"
}
```

Allowed operation discriminators are `describe`, `count`, `sum`, `mean`, `min`, `max`, `group_by`,
`sort`, `top_n`, and `aggregation`. Every column must exist in the trusted schema; numeric functions
require numeric fields; grouping, aliases, directions, aggregation functions, and row limits are
validated. Unknown and extra fields fail schema validation. No field accepts Python, SQL,
JavaScript, shell commands, code, or a general expression language.

## Gen-UI Contract

Phase 8 implements a versioned discriminated union validated first with Pydantic and again with Zod
immediately before frontend rendering. The fixed allowlist is:

```text
text | metric | bar_chart | line_chart | pie_chart | table | citation_list | video_evidence
```

A representative `bar_chart` component is:

```json
{
  "version": "1.0",
  "type": "bar_chart",
  "title": "Revenue by Region",
  "data": [
    {"region": "North", "revenue": 120},
    {"region": "South", "revenue": 95}
  ],
  "config": {
    "xKey": "region",
    "yKey": "revenue"
  }
}
```

All components require `version: "1.0"` and their literal `type`. Component-specific contracts are:

- `text`: required bounded `text`.
- `metric`: required bounded `label` and finite numeric or safe string `value`; optional `unit`.
- `bar_chart` / `line_chart`: bounded row objects and `{xKey, yKey}`. Both keys must differ, exist
  in every row, and `yKey` must reference a finite number. Line charts require at least two rows.
- `pie_chart`: bounded rows and `{labelKey, valueKey}` with the same key/numeric rules.
- `table`: bounded unique `{key, label}` columns and rows containing every configured key.
- `citation_list`: bounded document/video citation display records.
- `video_evidence`: bounded trusted video/segment IDs, filename, description, and a valid increasing
  time range.

The response wrapper is `{"components": [...]}` with at most five components. Objects are strict:
unknown fields, unknown types/versions, invalid identifiers, malformed rows, blank/oversized text,
non-finite numbers, and invalid cross-field keys are rejected. HTML tags, script markup,
`javascript:` schemes, and event-handler syntax are rejected recursively.

For analytics, the proposed type must match `recommended_visualization`, data rows must exactly
equal deterministic executor output, table columns must exactly match result columns, and metric
label/value must exactly match the single deterministic value. Any structured-provider, schema, or
grounding failure returns the existing safe text answer with `genui: []`.

The frontend selects renderers only from a frozen registry keyed by the validated eight-value
discriminator. It never dynamically imports a component, evaluates JavaScript, invokes `eval` or
`Function`, or injects raw HTML. Invalid frontend payloads render caller-supplied safe text.

## Evaluation Contracts

### `GET /api/v1/evaluations/summaries?limit=10` — Implemented in Phase 13

Returns newest-first completed evaluation summaries, bounded to `1..100` and capped by
`EVALUATION_RECENT_LIMIT`. Each strict summary contains `run_id`, UTC `timestamp`, dataset/configuration
identity and SHA-256 fingerprint, retrieval modes, safe provider/model identifiers, and aggregate
retrieval/routing/generation/guardrail/system metrics. It never contains evaluation prompts,
answers, retrieved context, system prompts, chain-of-thought, or hidden reasoning.

### `POST /api/v1/evaluations/runs` — Planned

Remote evaluation execution is not exposed in Phase 13. Runs are initiated deliberately from the
AI-service CLI so expensive configured-provider use cannot be triggered from this unauthenticated
local-development API.

## Versioning and Compatibility

Public envelopes and Gen-UI payloads carry `schema_version`. Breaking contract changes require a new API or schema version and a decision-log entry. Provider SDK types, database documents, and LangGraph internal state are not public API contracts.
