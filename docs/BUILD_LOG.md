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
