# SYNAPSE — Enterprise AI Intelligence OS

Synapse is a portfolio-grade Enterprise AI Intelligence OS designed to demonstrate senior-level AI engineering. It will reason across PDF documents, video content, and CSV data while keeping answers grounded in traceable evidence.

> **Project status:** Phase 15 — prepared for the documented $0 portfolio deployment topology.
> Deployment descriptors, production browser routing, direct-to-Supabase uploads, bounded Render
> cold-start handling, and exact operator setup are included. No cloud resources are created by the
> repository; see `docs/DEPLOYMENT.md` and `docs/SECURITY.md` before publishing a deployment.

## Intended Capabilities

- Multimodal retrieval-augmented generation for documents and video
- Hybrid retrieval using dense search, BM25, Reciprocal Rank Fusion, and lightweight reranking
- LangGraph orchestration with bounded routing, synthesis, and guardrail transitions
- Mistral integration behind a replaceable provider interface
- Offline-capable mock provider for tests and portfolio demonstrations
- Deterministic, typed CSV analytics without arbitrary code execution
- Citation-grounded answers and timestamped video evidence
- Schema-constrained generative UI rendered through a fixed component registry
- Layered Sentinel input, grounding, and output guardrails
- Retrieval, routing, generation, guardrail, latency, and provider-usage evaluation
- Streaming inference with safe operational traces, never chain-of-thought

## Monorepo

Phase 15 preserves the AI-first product experience and production persistence. The frontend
provides an AI chat workspace, local knowledge library, source drawer, timestamped video evidence,
safe agent activity, Sentinel quality summaries, system readiness, and a fixed Recharts-backed
Gen-UI registry, plus an aggregate evaluation observatory. FastAPI still owns intelligence and the
gateway remains transport-only.

```text
frontend/       Responsive AI workspace, knowledge/evidence UI, strict SSE client, fixed Gen-UI
gateway/        Thin Express validation, IDs, rate limiting, and SSE proxy
ai-service/     FastAPI, LangGraph, PDF/video RAG, constrained CSV analytics, typed providers/API
shared/         Versioned implementation-neutral Zod Gen-UI contract
scripts/        Transparent fixture-generation automation
sample-data/    Curated PDF, CSV, and retrieval-evaluation fixtures
docs/           Architecture, design, decisions, contracts, and build history
```

## Prerequisites

- Node.js 20.19 or newer
- npm 10 or newer
- Python 3.11 or newer
- FFmpeg and ffprobe available on `PATH` for real MP4 ingestion

The validated environment used Node.js 24 and Python 3.14. The declared compatibility floor
remains Node.js 20.19 and Python 3.11.

## Installation

Install the frontend and gateway workspaces from the repository root:

```powershell
npm install
```

Create an isolated Python environment and install the AI service with development tools:

```powershell
cd ai-service
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
cd ..
```

On macOS or Linux, replace the Python executable path with `.venv/bin/python`.

Each service has an `.env.example` containing variable names only. All settings have safe local
defaults, so copying these files is optional. If overrides are needed, copy the relevant
example to `.env` and set local values; `.env` files are ignored by Git.

## Local Development

Run each service in a separate terminal from the repository root.

Frontend AI workspace:

```powershell
npm run dev:frontend
```

Thin gateway:

```powershell
npm run dev:gateway
```

AI service:

```powershell
cd ai-service
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Local URLs:

- Frontend: `http://localhost:5173`
- Gateway health: `http://localhost:4000/health`
- AI service health: `http://localhost:8000/health`
- AI retrieval readiness: `http://localhost:8000/ready`
- AI service OpenAPI: `http://localhost:8000/docs`
- Active AI provider: `http://localhost:8000/api/v1/system/ai-provider`
- Documents API: `http://localhost:8000/api/v1/documents`
- Videos API: `http://localhost:8000/api/v1/videos`
- Datasets API: `http://localhost:8000/api/v1/datasets`
- Analytics API: `http://localhost:8000/api/v1/analytics/execute`
- Gateway chat stream: `http://localhost:4000/api/v1/chat/stream`
- Direct AI chat stream: `http://localhost:8000/api/v1/chat/stream`
- Recent evaluation summaries: `http://localhost:8000/api/v1/evaluations/summaries`

Run the reproducible, network-free evaluation suite from `ai-service/`:

```powershell
.\.venv\Scripts\python.exe -m app.evaluation.run
```

By default it uses Mock mode and saves summaries to `EVALUATION_SUMMARY_PATH` (an OS-temporary JSON
file by default), or MongoDB when `METADATA_BACKEND=mongo`. Use `--provider configured` only when you
intentionally want the configured provider and accept its network/quota use.

Both health endpoints return `service`, `status`, `version`, and `environment`. AI `/ready` separately
reports document/video index reconstruction and returns 503 until both retrieval namespaces are usable.

In Vite development, `/ai-local` proxies local knowledge-library and readiness calls directly to
FastAPI at `http://127.0.0.1:8000`. Override that development target with `AI_SERVICE_DEV_URL`.
Production browser requests use only `VITE_GATEWAY_URL`; they never receive a direct AI-service URL
or a server credential. `VITE_ENABLE_LOCAL_UPLOADS=false` hides local direct upload actions.
Production builds disable direct binary uploads regardless of that flag.

Upload the deterministic sample PDF and search it:

```powershell
curl.exe -X POST http://localhost:8000/api/v1/documents `
  -F "file=@sample-data/documents/synapse-policy.pdf;type=application/pdf"

$searchBody = @{ query = "What is the refund policy?"; top_k = 3 } | ConvertTo-Json
Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8000/api/v1/search/documents `
  -ContentType "application/json" `
  -Body $searchBody
```

Invoke the graph after uploading the document:

```powershell
$body = @{
  message = "Find the refund policy in my documents."
  thread_id = "local-thread"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8000/api/v1/chat/invoke `
  -ContentType "application/json" `
  -Body $body
```

The response is a safe state summary containing route, final response, trusted document citations,
guardrail result, bounded rewrite count, operational trace, and safe model/latency/token metadata.
It excludes the user query, draft response, tool internals, prompts, credentials, and private
reasoning. Citation filenames, document IDs, pages, and chunk IDs are copied from retrieval records,
never generated by the model.

Stream through the complete React-facing gateway path:

```powershell
$streamBody = '{"message":"Explain what RAG means.","thread_id":"local-stream"}'
curl.exe -N -X POST http://localhost:4000/api/v1/chat/stream `
  -H "Content-Type: application/json" `
  -H "Accept: text/event-stream" `
  --data $streamBody
```

The gateway requires `AI_SERVICE_URL` only when the AI service is not at
`http://127.0.0.1:8000`. `GATEWAY_UPSTREAM_TIMEOUT_MS`, `GATEWAY_RATE_LIMIT_WINDOW_MS`, and
`GATEWAY_RATE_LIMIT_MAX` provide bounded transport controls. FastAPI uses
`SSE_STREAM_TIMEOUT_SECONDS` and `SSE_HEARTBEAT_SECONDS`.

By default, local document metadata and Chroma data are written beneath the operating system's
temporary directory. Set `DOCUMENT_METADATA_PATH` and `CHROMA_PERSIST_PATH` in `ai-service/.env` for
a stable local location. Direct multipart upload is a bounded development endpoint and returns 403
when `APP_ENV=production`.

For production, set `METADATA_BACKEND=mongo`, `MONGODB_URI`, `MONGODB_DATABASE`,
`OBJECT_STORAGE_PROVIDER=supabase`, `SUPABASE_URL`, and `SUPABASE_SERVICE_ROLE_KEY` on the AI service.
Create a private Supabase bucket named `synapse-assets` and allow the deployed frontend origin in
Storage CORS. Never prefix the service-role variable with `VITE_` or configure it in the frontend.
The browser obtains a short-lived URL from the gateway, uploads PDF/MP4 bytes directly to Supabase,
and sends only the generated object path back through the gateway. Mongo persists the original
embedding vectors and metadata needed to rebuild Chroma without another embedding-provider call.

Local videos use the same development-only upload boundary. `MAX_VIDEO_SIZE_MB`,
`MAX_VIDEO_DURATION_SECONDS`, `MAX_KEYFRAMES`, and `KEYFRAME_INTERVAL_SECONDS` bound processing and
vision usage. `FFMPEG_PATH` and `FFPROBE_PATH` can point to explicit executables. Vision and
transcription are opt-in with `VIDEO_VISION_ENABLED` and `VIDEO_TRANSCRIPTION_ENABLED`; Mock
transcription is available through `TRANSCRIPTION_PROVIDER=mock`. Uploaded videos and derived
keyframes are stored below `VIDEO_STORAGE_PATH`, while authoritative metadata is stored at
`VIDEO_METADATA_PATH`.

Upload a small local MP4 and search its temporal segments:

```powershell
curl.exe -X POST http://localhost:8000/api/v1/videos `
  -F "file=@C:\path\to\portfolio.mp4;type=video/mp4"

$videoSearch = @{ query = "What happened near the product demonstration?"; top_k = 3 } |
  ConvertTo-Json
Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8000/api/v1/search/videos `
  -ContentType "application/json" `
  -Body $videoSearch
```

Upload the deterministic CSV fixture and execute a typed grouped aggregation:

```powershell
$dataset = curl.exe -s -X POST http://localhost:8000/api/v1/datasets `
  -F "file=@sample-data/datasets/regional-revenue.csv;type=text/csv" |
  ConvertFrom-Json

$analyticsBody = @{
  dataset_id = $dataset.dataset_id
  operation = @{
    operation = "group_by"
    grouping_fields = @("region")
    aggregation = "sum"
    aggregation_field = "revenue"
    limit = 10
  }
} | ConvertTo-Json -Depth 5

Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8000/api/v1/analytics/execute `
  -ContentType "application/json" `
  -Body $analyticsBody
```

CSV ingestion is bounded by `DATASET_MAX_UPLOAD_BYTES`, `DATASET_MAX_ROWS`, and
`DATASET_MAX_COLUMNS`; output is bounded by `ANALYTICS_MAX_RESULT_ROWS`. The only accepted analytics
operations are the Pydantic-discriminated schemas documented in the API contract. There is no
Python, SQL, shell, expression, `eval`, or `exec` execution path.

Gen-UI responses use `version: "1.0"` and exactly one of `text`, `metric`, `bar_chart`,
`line_chart`, `pie_chart`, `table`, `citation_list`, or `video_evidence`. Unknown fields/types,
invalid chart keys, malformed rows, non-finite values, HTML, scripts, event handlers, and unsafe
schemes are rejected. Analytics chart/table/metric data must exactly equal the deterministic tool
result or the backend returns only the safe text answer. The frontend validates unknown payloads
again with Zod before selecting a renderer from its frozen registry.

Hybrid-stage limits are configured with `VECTOR_TOP_K`, `BM25_TOP_K`, `RERANK_TOP_K`, and
`FINAL_CONTEXT_K`. Retrieval diagnostics are off by default. Setting `DEBUG=true` registers
`POST /api/v1/debug/retrieval/documents`; when false, the route is absent, returns 404, and is not
listed in OpenAPI.

## AI Provider Modes

Mock mode is the default and requires neither credentials nor network access:

```text
AI_PROVIDER=mock
```

To use Mistral, create `ai-service/.env` from `ai-service/.env.example` and set:

```text
AI_PROVIDER=mistral
MISTRAL_API_KEY=your-local-secret
MISTRAL_CHAT_MODEL=mistral-small-latest
MISTRAL_VISION_MODEL=mistral-small-latest
MISTRAL_EMBED_MODEL=mistral-embed
AI_REQUEST_TIMEOUT_SECONDS=30
AI_MAX_TRANSIENT_RETRIES=2
```

The `.env` file is ignored by Git. Mistral mode fails startup with a safe configuration error when
the API key is absent. Provider calls use a configured timeout, retry only connection/timeouts and
server failures, and do not automatically retry HTTP 429 quota/rate-limit responses.

## Quality Commands

From the repository root:

```powershell
npm run lint
npm run typecheck
npm run test
npm run build
```

From `ai-service/`:

```powershell
.\.venv\Scripts\python.exe -m ruff check app tests
.\.venv\Scripts\python.exe -m mypy app tests
.\.venv\Scripts\python.exe -m pytest
```

Run the versioned offline retrieval comparison from `ai-service/`:

```powershell
$env:AI_PROVIDER="mock"
.\.venv\Scripts\python.exe -m app.evaluation.cli
```

It reports Recall@K and MRR separately for `vector_only` and `hybrid` retrieval.

Automated tests explicitly run in Mock mode and require no provider network, external database,
object store, or Mistral credentials after dependencies are installed. Tests use an in-memory
metadata repository and an ephemeral Chroma client.

## Planned Deployment Profile

The portfolio demonstration is designed to remain operable at zero cost using Vercel Hobby for the frontend and gateway, Render Free Web Service for the AI service, MongoDB Atlas Free for metadata, Supabase Storage Free for objects, Mistral free mode, and local ChromaDB reconstructed from durable records after ephemeral restarts.

This is intentionally different from a production enterprise topology. See [Free-Tier Strategy](docs/FREE_TIER_STRATEGY.md) for the explicit boundary and limitations.

## Documentation Map

- [Architecture](docs/ARCHITECTURE.md) — service boundaries, data flows, deployment, and trust boundaries
- [AI Design](docs/AI_DESIGN.md) — multimodal RAG, LangGraph state, agents, grounding, Gen-UI, and evaluation
- [Free-Tier Strategy](docs/FREE_TIER_STRATEGY.md) — demo architecture versus a future enterprise architecture
- [API Contracts](docs/API_CONTRACTS.md) — planned transport and domain contracts
- [Decisions](docs/DECISIONS.md) — architecture decision log
- [Build Log](docs/BUILD_LOG.md) — phase-by-phase implementation record
- [Agent Instructions](AGENTS.md) — mandatory rules for future coding work

## Non-Goals

- A generic MERN CRUD application
- Arbitrary LLM-generated code execution
- Arbitrary React, JavaScript, or HTML generation
- Unbounded autonomous agent loops
- Chain-of-thought exposure
- Paid infrastructure without explicit approval
- Claims of production or enterprise deployment during the portfolio phase

## Current Scope and Phase Boundary

Phase 10 supports typed SSE lifecycle and response events through the React → Express → FastAPI
path. Generation chunks are emitted only after the completed response passes Sentinel; the current
provider interface does not yet expose native token callbacks. The gateway intentionally has no
upload proxy: local FastAPI multipart routes remain development-only, while production large-file
uploads still require browser-to-object-storage signed URLs. Authentication, persistent threads,
resume/replay storage, production deployment, and the final dashboard remain out of scope.
