# SYNAPSE — Enterprise AI Intelligence OS

Synapse is a portfolio-grade Enterprise AI Intelligence OS designed to demonstrate senior-level AI engineering. It will reason across PDF documents, video content, and CSV data while keeping answers grounded in traceable evidence.

> **Project status:** Phase 3 — provider-based LLM inference. The typed graph uses either a
> deterministic offline Mock provider or Mistral for structured routing and synthesis. Retrieval,
> persistence, and cloud infrastructure are not connected.

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

Phase 3 adds a typed, replaceable model-provider boundary while retaining the Phase 2 graph and
deterministic Sentinel. It does not implement retrieval or persistence.

```text
frontend/       React, TypeScript, Vite, Tailwind CSS development shell
gateway/        Thin Express, TypeScript, Zod, CORS, Helmet gateway foundation
ai-service/     FastAPI, Pydantic v2, LangGraph, Mistral/Mock providers, typed API
shared/         Reserved for implementation-neutral, versioned contracts
scripts/        Reserved for transparent repository automation
sample-data/    Reserved for curated, non-sensitive fixtures
docs/           Architecture, design, decisions, contracts, and build history
```

## Prerequisites

- Node.js 20.19 or newer
- npm 10 or newer
- Python 3.11 or newer

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

Frontend development shell:

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
- AI service OpenAPI: `http://localhost:8000/docs`
- Active AI provider: `http://localhost:8000/api/v1/system/ai-provider`

Both health endpoints return `service`, `status`, `version`, and `environment`.

Invoke the Phase 3 graph:

```powershell
$body = @{
  message = "Summarize page 4 of the PDF document"
  thread_id = "local-thread"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8000/api/v1/chat/invoke `
  -ContentType "application/json" `
  -Body $body
```

The response is a safe state summary containing route, final response, guardrail result, bounded
rewrite count, operational trace, and safe model/latency/token metadata. It excludes the user query,
draft response, tool internals, prompts, credentials, and private reasoning.

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

Automated tests explicitly run in Mock mode and require no database, object store, provider network,
or Mistral credentials after dependencies are installed.

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

Phase 3 intentionally stops at provider-backed structured routing and synthesis, safe inference
metadata, deterministic placeholder capability nodes and Sentinel decisions, and a bounded
LangGraph rewrite path. The provider interface exposes text generation, structured generation,
vision description, and embeddings, but only routing and synthesis are connected. MongoDB,
authentication, real RAG, ChromaDB, Supabase, persistent threads, and Gen-UI are not implemented.
