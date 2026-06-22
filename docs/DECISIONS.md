# Architecture Decisions

This is a lightweight architecture decision record (ADR) log. New architecture-changing choices must be recorded here with context, alternatives, consequences, and status. Accepted decisions remain in the log even if later superseded.

## Decision Index

| ID | Decision | Status | Date |
|---|---|---|---|
| ADR-001 | AI-first monorepo with strict service boundaries | Accepted | 2026-06-12 |
| ADR-002 | Bounded LangGraph orchestration with one Sentinel rewrite | Accepted | 2026-06-12 |
| ADR-003 | Hybrid retrieval with provenance-first evidence | Accepted | 2026-06-12 |
| ADR-004 | Constrained deterministic analytics instead of code execution | Accepted | 2026-06-12 |
| ADR-005 | Schema-constrained Gen-UI | Accepted | 2026-06-12 |
| ADR-006 | Free-tier portfolio topology with reconstructable Chroma | Accepted | 2026-06-12 |
| ADR-007 | Replaceable providers and mandatory mock AI mode | Accepted | 2026-06-12 |
| ADR-008 | Direct-to-object-storage production uploads | Accepted | 2026-06-12 |
| ADR-009 | Safe operational traces without chain-of-thought | Accepted | 2026-06-12 |
| ADR-010 | Independent Phase 1 workspaces and application factories | Accepted | 2026-06-15 |
| ADR-011 | Deterministic Phase 2 graph with bounded rewrites | Accepted | 2026-06-19 |
| ADR-012 | Provider-backed inference with explicit retry ownership | Accepted | 2026-06-24 |

## ADR-001 — AI-First Monorepo with Strict Service Boundaries

**Status:** Accepted  
**Context:** The portfolio must demonstrate applied AI engineering without becoming a generic full-stack CRUD project.  
**Decision:** Use a monorepo with planned `frontend/`, `gateway/`, `ai-service/`, `shared/`, `scripts/`, `sample-data/`, and `docs/` areas. Put prompts, orchestration, retrieval, analytics, providers, evaluation, and guardrails exclusively in the Python AI service. Keep the Node gateway transport-only and the frontend presentation-only.  
**Consequences:** AI behavior has a clear owner and can be tested independently. Some contracts must be represented in both Pydantic and Zod and checked for drift.

## ADR-002 — Bounded LangGraph Orchestration with One Sentinel Rewrite

**Status:** Accepted  
**Context:** Agent workflows need correction paths without runaway loops.  
**Decision:** Route through Document Search, Video Search, Data Analytics, or Direct Answer, then Synthesizer and Sentinel. Allow at most one Sentinel-directed rewrite. A subsequent failure terminates as blocked or conservative insufficient evidence.  
**Consequences:** Latency and provider usage are bounded. The graph must carry and test an explicit `rewrite_count` invariant.

## ADR-003 — Hybrid Retrieval with Provenance-First Evidence

**Status:** Accepted  
**Context:** Dense retrieval can miss exact terms, lexical retrieval can miss semantic matches, and generated citation locations are unsafe.  
**Decision:** Combine Chroma dense results and BM25 lexical results with Reciprocal Rank Fusion, then apply lightweight reranking and context selection. Require trusted page or timestamp provenance on every eligible evidence item.  
**Consequences:** Retrieval has more moving parts and needs separate evaluation, but improves robustness and makes citation validation deterministic.

## ADR-004 — Constrained Deterministic Analytics Instead of Code Execution

**Status:** Accepted  
**Context:** Executing model-generated Python creates unacceptable security and correctness risk; LLM arithmetic is unreliable.  
**Decision:** Expose a typed allowlist of describe, count, sum, mean, min, max, group-by, sort, top-N, and aggregation operations. Execute them through controlled library calls and use their results as the sole source for numerical claims.  
**Consequences:** The analytics surface is intentionally narrower but safe, reproducible, and testable.

## ADR-005 — Schema-Constrained Gen-UI

**Status:** Accepted  
**Context:** Arbitrary generated React/HTML creates injection, reliability, and maintainability problems.  
**Decision:** The model may emit only a versioned discriminated union of approved component data. Validate with Pydantic and Zod and render through a fixed frontend registry.  
**Consequences:** UI generation is predictable and safe. New visual forms require an explicit schema and registry change.

## ADR-006 — Free-Tier Portfolio Topology with Reconstructable Chroma

**Status:** Accepted  
**Context:** The demo must run for $0, while Render-local storage is ephemeral.  
**Decision:** Plan for Vercel Hobby, Render Free, MongoDB Atlas Free, Supabase Storage Free, Mistral free mode, and local ChromaDB. Persist enough versioned chunks and embeddings in durable storage to rebuild Chroma without repeating embedding calls.  
**Consequences:** Startup may require index warm-up, and MongoDB capacity constrains demo scale. This is not represented as an enterprise production deployment.

## ADR-007 — Replaceable Providers and Mandatory Mock AI Mode

**Status:** Accepted  
**Context:** Free-model quota and network access cannot be assumed in demos or automated tests.  
**Decision:** Isolate AI calls behind provider interfaces and support `AI_PROVIDER=mistral|mock`. The mock must be deterministic and network-free. Use comparable repository/provider abstractions for metadata, object storage, and vectors.  
**Consequences:** Provider behavior can be tested and replaced, at the cost of additional interface and contract-test work.

## ADR-008 — Direct-to-Object-Storage Production Uploads

**Status:** Accepted  
**Context:** Vercel serverless functions are a poor path for large PDFs and videos.  
**Decision:** Upload production binaries from the browser using short-lived signed Supabase upload authorization, then send only object references and control metadata through the gateway to the AI service. Allow bounded direct FastAPI upload only for local development.  
**Consequences:** Upload authorization and ownership validation become first-class security concerns, while the gateway remains small and deployment-safe.

## ADR-009 — Safe Operational Traces Without Chain-of-Thought

**Status:** Accepted  
**Context:** The UI needs agent activity and observability, but hidden reasoning may contain sensitive data and must not be exposed.  
**Decision:** Stream structured events for route selection, tool lifecycle, evidence IDs, validations, timings, provider usage, rewrite count, and status. Do not collect or return chain-of-thought, hidden prompts, or raw provider traces.  
**Consequences:** Debugging depends on strong structured telemetry rather than reasoning transcripts, which improves safety and forces explicit instrumentation.

## ADR-010 — Independent Phase 1 Workspaces and Application Factories

**Status:** Accepted  
**Context:** Phase 1 needs a runnable monorepo foundation while preserving service isolation and making
backend health behavior easy to test without network access or long-lived processes.  
**Decision:** Manage the frontend and gateway as private npm workspaces with a shared strict TypeScript
base configuration. Manage the AI service independently through `pyproject.toml` and a local virtual
environment. Build the Express and FastAPI services through application factories that accept typed
runtime configuration. Expose unversioned `GET /health` endpoints as process-liveness probes.  
**Alternatives:** A single cross-language task runner, container-first development, and module-level
configuration were considered unnecessary for the Phase 1 scope.  
**Consequences:** Each service can run and test independently, backend tests remain deterministic, and
the gateway stays free of AI dependencies. Developers run three local processes, and cross-service
contract generation remains deferred until shared domain contracts exist.

## ADR-011 — Deterministic Phase 2 Graph with Bounded Rewrites

**Status:** Accepted  
**Context:** The orchestration topology and safety invariants need executable proof before connecting
model providers, retrieval, databases, or persistence.  
**Decision:** Implement the Phase 2 workflow with LangGraph `StateGraph`, a fully initialized typed
state, pure deterministic nodes, conditional router and Sentinel edges, no checkpointer, and no model
calls. Sentinel may increment `rewrite_count` from zero to one exactly once; another invalid draft is
blocked. The invocation service also uses a recursion limit of 12.  
**Alternatives:** Hand-written control flow would be simpler but would not validate the intended
LangGraph architecture. Adding a checkpointer or provider was rejected as future-phase scope.  
**Consequences:** Routing and termination are deterministic, fast, and network-free after installation.
`thread_id` is correlation data only, placeholder tools return explicit not-implemented results, and
the implementation does not yet demonstrate retrieval or model quality.

## ADR-012 — Provider-Backed Inference with Explicit Retry Ownership

**Status:** Accepted  
**Context:** Phase 3 needs real Mistral inference without coupling graph nodes to an SDK, leaking
credentials, making tests network-dependent, or multiplying automatic retries during quota events.  
**Decision:** Define one typed `LLMProvider` boundary for text, structured, vision, and embedding
operations. Inject the selected provider into Router and Synthesizer; keep Sentinel deterministic.
Use native Pydantic structured output for routing. Default to a deterministic Mock provider and
require it for automated tests. In the Mistral adapter, disable SDK retry behavior and own a bounded
retry policy that retries only connection/timeouts and HTTP 5xx failures. Return HTTP 429 without an
automatic quota retry. Expose credential-free provider identity and safe inference metadata.  
**Alternatives:** Calling the SDK directly from nodes was rejected because it would leak provider
types into orchestration. Retrying all failures was rejected because 4xx failures require caller or
quota changes. A model-backed Sentinel was rejected because it is outside Phase 3 and weakens the
existing deterministic termination invariant.  
**Consequences:** Provider selection is testable and Mock mode starts without credentials or network
access. The adapter has additional normalization code, and live Mistral behavior requires a user
supplied API key and available quota. Vision and embedding methods exist but remain disconnected
until retrieval phases are authorized.

## ADR Template

```text
## ADR-NNN — Title

Status: Proposed | Accepted | Superseded by ADR-NNN | Rejected
Date: YYYY-MM-DD
Context: What problem or constraint requires a decision?
Decision: What was chosen?
Alternatives: What credible options were considered?
Consequences: What improves, what becomes harder, and what must be tested?
```
