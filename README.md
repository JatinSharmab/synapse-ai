# SYNAPSE — Enterprise AI Intelligence OS

Synapse is a portfolio-grade Enterprise AI Intelligence OS designed to demonstrate senior-level AI engineering. It will reason across PDF documents, video content, and CSV data while keeping answers grounded in traceable evidence.

> **Project status:** Phase 2 — deterministic LangGraph orchestration core. The typed graph, safe
> invoke endpoint, frontend shell, and backend health endpoints run locally; model providers,
> retrieval, persistence, and cloud infrastructure are not connected.

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

Phase 2 establishes the service boundaries and deterministic orchestration without implementing
model-backed generation, retrieval, or persistence.

```text
frontend/       React, TypeScript, Vite, Tailwind CSS development shell
gateway/        Thin Express, TypeScript, Zod, CORS, Helmet gateway foundation
ai-service/     FastAPI, Pydantic v2, LangGraph orchestration, typed API and health
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

Both health endpoints return `service`, `status`, `version`, and `environment`.

Invoke the deterministic Phase 2 graph:

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
rewrite count, and operational trace. It excludes the user query, draft response, tool internals, and
private reasoning.

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

These checks require no AI provider, database, object store, or network access after dependencies are
installed.

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

Phase 2 intentionally stops at deterministic routing, placeholder capability nodes, synthesis,
Sentinel decisions, safe tracing, and a bounded LangGraph rewrite path. MongoDB, authentication,
Mistral, real RAG, embeddings, ChromaDB, Supabase, persistent threads, and Gen-UI generation are not
implemented.
