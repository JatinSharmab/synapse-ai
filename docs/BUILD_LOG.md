# Build Log

This log records completed project phases. Entries describe work actually performed, not planned features.

## Phase 0 — Architecture and Engineering Contracts

**Date:** 2026-06-12  
**Status:** Complete

### Delivered

- Established repository-wide agent and safety instructions.
- Defined the target monorepo and strict frontend, gateway, and AI-service boundaries.
- Documented the bounded LangGraph flow and one-rewrite Sentinel limit.
- Designed page-aware PDF RAG, sampled video RAG, hybrid retrieval, deterministic CSV analytics, citation grounding, structured Gen-UI, evaluation, safe observability, and streaming contracts.
- Separated the planned $0 portfolio topology from a conceptual production enterprise topology.
- Documented planned API and SSE contracts without implementing endpoints.
- Initialized the architecture decision log.

### Verification

- Confirmed Phase 0 contains only the eight requested Markdown files.
- Confirmed no frontend, gateway, AI-service, dependency, infrastructure, or runtime code was introduced.
- Confirmed Mermaid diagrams are included in the architecture document.

### Deferred by Design

- Application directory scaffolding
- Dependencies and lockfiles
- Runtime configuration and `.env.example` files
- Frontend, gateway, and AI-service implementation
- Database, object storage, and provider provisioning
- Automated tests and deployment verification

## Phase 1 — Runnable Monorepo Foundation

**Date:** 2026-06-15  
**Status:** Complete

### Delivered

- Created the required `frontend/`, `gateway/`, `ai-service/`, `shared/`, `scripts/`, and
  `sample-data/` directories.
- Added a private npm workspace with shared strict TypeScript compiler defaults and a lockfile.
- Added a professional React, TypeScript, Vite, and Tailwind development shell with
  shadcn-compatible component aliases and conventions.
- Added a thin Express gateway with Zod-validated environment configuration, CORS, Helmet, request
  logging, and `GET /health`.
- Added a FastAPI AI-service foundation with Pydantic v2 response models, typed Pydantic settings,
  Uvicorn support, OpenAPI, and `GET /health`.
- Added service-level `.env.example` files containing names only and a repository `.gitignore` that
  excludes secrets, dependencies, caches, build products, and local environments.
- Added backend health smoke tests, ESLint, strict TypeScript checks, Ruff, strict mypy, and pytest.
- Added installation, local development, endpoint, and quality-check instructions.

### Verification

- `npm run lint` passed for frontend and gateway.
- `npm run typecheck` passed for frontend and gateway.
- `npm run test` passed the gateway health/security smoke test.
- `npm run build` produced the frontend production bundle and compiled the gateway.
- `ruff check app tests` passed.
- `mypy app tests` passed in strict mode.
- `pytest` passed both AI-service health/OpenAPI smoke tests.
- Started the compiled gateway and Uvicorn AI service and confirmed both live `/health` responses.
- npm audit reported zero vulnerabilities at installation time.

### Resolved During Verification

- The sandbox blocked the initial npm registry request and Python virtual-environment creation; both
  were retried with explicit permission.
- Node's `os.userInfo()` fails in this Windows execution environment, which prevented `tsx` from
  launching tests. Gateway tests now compile with `tsc` and use Node's native test runner, avoiding
  the environment-specific failure.
- Python cache writes were denied inside the sandbox during the first parallel check. Final Ruff and
  mypy validation used writable temporary cache locations; pytest was run without its cache plugin.
- Corrected the Starlette test client dependency to `httpx2>=2,<3`, removing its deprecation warning.

### Deferred by Design

- MongoDB and all other persistence
- Authentication and authorization
- LangGraph, Mistral, RAG, ChromaDB, Supabase, agents, and Gen-UI
- Gateway proxying, correlation IDs, rate limiting, SSE, and normalized error middleware
- Final dashboard and product workflows
- Deployment configuration and cloud provisioning

## Phase 2 — Deterministic LangGraph Orchestration Core

**Date:** 2026-06-19  
**Status:** Complete

### Delivered

- Added LangGraph 1.2 with a strongly typed `SynapseState` and typed partial state updates.
- Organized the AI service into `api`, `agents`, `graph`, `models`, `schemas`, `services`, `tools`,
  and `core` layers.
- Implemented deterministic Router, Document Search, Video Search, Data Analytics, Direct Answer,
  Synthesizer, and Sentinel nodes.
- Implemented conditional routing from Router and a bounded Sentinel rewrite edge.
- Enforced a maximum `rewrite_count` of one and an invocation recursion limit of 12.
- Added deterministic placeholder tools that explicitly report unavailable future capabilities and
  never fabricate retrieved context, citations, timestamps, pages, or numerical results.
- Added `POST /api/v1/chat/invoke` with strict request validation and a safe state summary that omits
  user input, drafts, retrieved context, tool internals, prompts, and private reasoning.
- Refactored Phase 1 configuration and health schemas into the clean AI-service package structure.
- Added an executable LangGraph Mermaid diagram and updated architecture/API documentation.

### Verification

- Document, video, analytics, and direct queries route to their expected nodes.
- Complete invocations terminate with an approved or blocked final state.
- A short first draft triggers exactly one rewrite and then terminates.
- A second invalid draft blocks rather than requesting another rewrite.
- Unknown API request fields are rejected, and safe API summaries omit private/internal state.
- `ruff check app tests` passed.
- `ruff format --check app tests` passed for all 27 Python files.
- Strict `mypy app tests` passed across 27 source files.
- `pytest` passed all 11 AI-service tests.
- Existing npm lint, TypeScript checks, gateway smoke test, and production builds still pass.
- A live Uvicorn request routed a video query correctly and returned only the safe state summary.

### Resolved During Verification

- Replaced substring keyword routing with word-boundary matching after `summarize` incorrectly matched
  the analytics keyword `sum` in the first test run.
- Corrected one Ruff line-length violation and two strict mypy type errors found in the first check.
- The sandbox denied Ruff's initial cache and formatting writes; final checks used no cache or a
  writable temporary cache, and formatting was applied with explicit workspace permission.

### Deferred by Design

- Mistral and every other model provider
- Real document/video retrieval, embeddings, RAG, and ChromaDB
- Deterministic CSV execution beyond the placeholder graph node
- MongoDB, Supabase, checkpointers, and persistent thread memory
- Production citations, generated UI, semantic guardrails, evaluation, and streaming

## Phase 3 — Provider-Based LLM Inference

**Date:** 2026-06-24  
**Status:** Complete

### Delivered

- Added a typed `LLMProvider` abstraction for text generation, Pydantic structured generation,
  image description, embeddings, and credential-free provider information.
- Added a deterministic, network-free `MockProvider` that supports every provider operation and is
  used by all automated AI-service tests.
- Added a `MistralProvider` using the current Mistral Python SDK with native structured parsing,
  explicit request timeouts, safe response normalization, and token/latency/retry metadata.
- Disabled SDK-owned retries and added a small bounded adapter policy for connection failures,
  timeouts, and HTTP 5xx responses only. HTTP 429 quota/rate-limit responses return immediately and
  are not automatically retried.
- Added typed environment selection through `AI_PROVIDER=mistral|mock`, `SecretStr` credential
  handling, model identifiers, request timeout, and retry-count settings.
- Moved Router and Synthesizer instructions into dedicated prompt modules.
- Connected Router to Pydantic structured provider output and Synthesizer to provider text
  generation while retaining deterministic placeholder tools and deterministic Sentinel behavior.
- Extended the safe graph summary with provider, operation, model, latency, retry count, and token
  usage where available; prompts, credentials, input text, drafts, and private reasoning remain
  excluded.
- Added `GET /api/v1/system/ai-provider`, returning only provider name, model identifiers, and Mock
  status.
- Documented Mock/Mistral switching, environment variables, timeout/retry behavior, API changes, and
  the provider architecture decision.

### Verification

- Mock mode routes refund-policy, video-timestamp, regional-revenue, and RAG-definition queries to
  document, video, analytics, and direct-answer nodes respectively.
- Provider operation tests cover deterministic text generation, structured generation, vision
  description, and embeddings without internet access.
- Mock mode starts without a Mistral API key.
- The provider-status API returns only safe Mock configuration and does not expose a configured
  unused credential.
- A simulated Mock-provider quota failure returns a safe HTTP 429 envelope after one attempt.
- The graph still terminates, and Sentinel performs at most one rewrite cycle.
- `ruff check --no-cache app tests` passed.
- `ruff format --no-cache --check app tests` passed for all 42 Python files.
- Strict `mypy app tests` passed across 42 source files.
- `AI_PROVIDER=mock pytest -p no:cacheprovider` passed all 16 AI-service tests.
- Existing npm lint, TypeScript checks, gateway smoke test, and production builds passed.

### Resolved During Verification

- Ruff, pytest, and mypy could not write their default cache directories in this execution
  environment. Final checks used no-cache flags or a writable temporary mypy cache; no failure was
  hidden.
- The current Mistral 2.9 SDK exposes the client from `mistralai.client`; the adapter imports and
  types against the installed SDK surface and passed strict mypy validation.
- A combined repository check exceeded the execution yield window after frontend typechecking, so
  lint, typecheck, test, and build were rerun separately with explicit successful exit codes.
- Git status inspection was unavailable because Git rejected the workspace's ownership as unsafe;
  no Git configuration was modified to bypass that repository-level safety check.

### Deferred by Design

- Real document/video retrieval, RAG, chunking, BM25, vector search, and ChromaDB
- Database, object storage, authentication, persistence, and thread memory
- Connection of vision and embedding provider methods to ingestion or retrieval workflows
- Real analytics execution, production citations, Gen-UI, semantic Sentinel checks, evaluation, SSE,
  and deployment
- Live Mistral verification, which requires a user-provided API key, network access, and quota
