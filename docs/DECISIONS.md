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
| ADR-013 | Provenance-first local PDF RAG with reconstructable vectors | Accepted | 2026-06-26 |
| ADR-014 | Rank-fused local hybrid retrieval with debug-gated diagnostics | Accepted | 2026-06-28 |
| ADR-015 | Bounded temporal video RAG with degradable enrichment | Accepted | 2026-06-30 |
| ADR-016 | Closed typed analytics plans with deterministic numeric authority | Accepted | 2026-07-02 |
| ADR-017 | Dual-validated data-only Gen-UI with a fixed renderer registry | Accepted | 2026-07-03 |
| ADR-018 | Layered deterministic Sentinel with narrow semantic escalation | Accepted | 2026-07-05 |
| ADR-019 | Post-guardrail typed SSE through a transport-only gateway | Accepted | 2026-07-06 |
| ADR-020 | Answer-first responsive workspace with local-only binary ingestion | Accepted | 2026-07-08 |
| ADR-021 | Durable Mongo vectors with disposable Chroma and direct Supabase uploads | Accepted | 2026-07-09 |

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
supplied API key and available quota. Phase 4 subsequently connected embeddings to document
ingestion and retrieval; vision remains disconnected until a video phase is authorized.

## ADR-013 — Provenance-First Local PDF RAG with Reconstructable Vectors

**Status:** Accepted  
**Context:** Phase 4 needs useful local PDF retrieval and citation provenance without introducing the
planned hosted metadata/object stores, expensive OCR, or later hybrid-ranking features. Chroma is an
index and must not become the authority for user-visible filenames or page locations.  
**Decision:** Validate and parse PDFs with PyMuPDF, retain page boundaries, and chunk by headings,
paragraphs, and sentences before applying bounded overlap. Persist document records, complete chunk
metadata, and embeddings through a typed repository; index caller-supplied vectors through a typed
Chroma adapter. Resolve every vector match back through the repository before constructing evidence
or citations. Use a JSON repository and persistent Chroma client locally, in-memory/ephemeral
adapters in tests, and rebuild a missing index from persisted embeddings at startup. Mark low/no-text
PDFs `ocr_required=true` without invoking OCR. Implement dense search only in this phase.  
**Alternatives:** Chroma-only metadata was rejected because it weakens provenance authority and
reconstruction. Fixed-character chunking was rejected because it ignores document structure.
Automatic OCR and BM25/RRF/reranking were rejected as explicit future-phase scope.  
**Consequences:** Local ingestion, retrieval, deletion, and graph citations are deterministic and
network-free in Mock mode. The JSON adapter is single-process development storage rather than a
transactional production database, original binaries are not retained, and hybrid relevance work
remains deferred.

## ADR-014 — Rank-Fused Local Hybrid Retrieval with Debug-Gated Diagnostics

**Status:** Accepted  
**Context:** Dense retrieval can recover semantic similarity but may miss rare exact identifiers;
lexical retrieval has the opposite tradeoff. Phase 5 must improve candidate coverage without paid
reranking APIs, network-dependent tests, incomparable-score arithmetic, or provenance drift.  
**Decision:** Normalize/rewrite queries deterministically, retrieve independent Chroma cosine and
`rank-bm25` lists, combine ranks with RRF (`k=60`), rerank the fused pool with a deterministic
CPU-only term/identifier/phrase coverage scorer, and select a bounded de-duplicated final context.
Carry authoritative `DocumentChunk` records through every stage. Support explicit `vector_only` and
`hybrid` evaluation modes with Recall@K and MRR. Register the stage-debug HTTP router only when
`DEBUG=true`; never add stage data to normal search/chat responses.  
**Alternatives:** Adding cosine and BM25 scores directly was rejected because their scales are not
comparable. FlashRank was considered but rejected for this phase because even a small cross-encoder
adds model artifact/download management and weakens offline reproducibility. Paid Cohere, Voyage,
Pinecone, and similar APIs were rejected by the free/local constraint.  
**Consequences:** Exact and semantic candidate paths complement each other, evaluation can compare
them honestly, and CI remains network-free after installation. BM25 is rebuilt per request and the
local reranker is a relevance heuristic rather than a learned cross-encoder; larger corpora will
need indexing/caching and broader evaluation before production claims.

## ADR-015 — Bounded Temporal Video RAG with Degradable Enrichment

**Status:** Accepted  
**Context:** Phase 6 needs useful timestamp retrieval for small portfolio MP4s without every-frame
analysis, mandatory paid transcription, uncontrolled vision spend, unsafe media subprocesses, or
model-authored timestamps. Local metadata must remain authoritative even when Chroma returns a
candidate or vision enrichment is temporarily unavailable.  
**Decision:** Validate bounded MP4 uploads, inspect streams through ffprobe, and sample at a
configurable interval up to `MAX_KEYFRAMES`. Invoke FFmpeg through explicit argument lists with
`shell=False`, generated in-root paths, timeouts, return-code checks, and output validation. Align
optional transcript spans and optional vision descriptions into typed temporal segments, persist
their metadata and embeddings through repository interfaces, and index a separate Chroma
collection. Resolve matches through the authoritative repository before exposing timestamps or
constructing graph citations. Stop vision enrichment after its first failure and persist the video
as `partial`; use disabled and deterministic Mock transcription providers so no paid service is
mandatory.  
**Alternatives:** Every-frame analysis was rejected for latency and provider cost. Content-aware
scene detection was deferred because interval sampling is more predictable for the bounded demo and
does not require decoding the entire video. Shell command construction was rejected due to path and
argument-injection risk. A mandatory cloud speech-to-text provider and model-generated timestamps
were rejected by the free/offline and provenance requirements.  
**Consequences:** Local ingestion has explicit cost ceilings, automated tests need neither FFmpeg
nor network access, and timestamp citations remain traceable. Real ingestion requires local FFmpeg
and ffprobe. Interval sampling can miss brief events between selected frames, Mock transcription is
not real speech recognition, and the JSON/artifact storage is a single-process development design.

## ADR-016 — Closed Typed Analytics Plans with Deterministic Numeric Authority

**Status:** Accepted  
**Context:** Phase 7 must answer natural-language questions over CSV data without allowing a model
to generate executable Python, SQL, shell commands, or general expressions. Column names,
aggregation fields, grouping fields, and output size are untrusted until resolved against the
uploaded dataset; generated numeric prose cannot be the source of truth.  
**Decision:** Parse bounded UTF-8 CSVs into authoritative raw rows plus an inferred
string/number/boolean schema. Expose a discriminated Pydantic operation union for `describe`,
`count`, `sum`, `mean`, `min`, `max`, `group_by`, `sort`, `top_n`, and multi-`aggregation`. Permit
the provider to return only an `AnalyticsPlan` containing a known dataset ID and one union member.
Revalidate every referenced column, numeric type, aggregation requirement, sort direction, alias,
and result limit against the repository. Dispatch to fixed executor methods and calculate through
`Decimal`; never expose a code/expression field, interpreter, SQL engine, dynamic import, `eval`, or
`exec`. Use the executor's deterministic summary directly for the graph draft rather than asking
the LLM to recalculate it.  
**Alternatives:** Model-generated Python and sandboxed notebooks were rejected because a sandbox is
not an authorization model and greatly expands the attack surface. Model-generated SQL was rejected
because Phase 7 has no database/query-policy boundary and arbitrary SQL is outside the allowed
operation set. Pandas query/eval strings and a general expression grammar were rejected because the
fixed portfolio operations need neither. LLM-authored final numbers were rejected because they
cannot be treated as deterministic evidence.  
**Consequences:** Analytics behavior is inspectable, offline-testable, and numerically grounded; the
same executor serves HTTP and LangGraph paths. The operation set intentionally lacks joins, filters,
derived formulas, date semantics, and large-data execution. CSV persistence remains a
single-process local JSON snapshot and should be replaced behind the repository interface for
production scale.

## ADR-017 — Dual-Validated Data-Only Gen-UI with a Fixed Renderer Registry

**Status:** Accepted  
**Context:** Phase 8 needs richer presentation without turning model output into executable frontend
code. Arbitrary React/JSX/JavaScript/HTML, dynamic imports, unsafe markup, unconstrained component
names, or model-modified analytics values would violate Synapse's execution and grounding
boundaries. Backend validation alone is insufficient because clients must treat all transport data
as untrusted.  
**Decision:** Define protocol `1.0` as equivalent strict Pydantic and Zod discriminated unions for
exactly `text`, `metric`, `bar_chart`, `line_chart`, `pie_chart`, `table`, `citation_list`, and
`video_evidence`. Forbid unknown fields/types/versions and bound components, rows, fields, text,
identifiers, citations, and video items. Require finite chart numbers, validate configured keys
against every row, and recursively reject HTML/script/event-handler content. Request structured UI
only for completed analytics results whose deterministic executor recommends a visualization.
Require proposal data and columns to exactly equal the deterministic result; otherwise return an
empty component list and preserve safe text. Validate again in Sentinel and with Zod immediately
before rendering. Select renderers only from a frozen, statically imported registry and never use
dynamic `import()`, `eval`, `Function`, or raw HTML injection.  
**Alternatives:** Model-generated JSX/React and sandboxed JavaScript were rejected because they make
untrusted text executable. A free-form JSON component name plus dynamic import was rejected because
validation would still permit arbitrary module selection. Backend-only validation was rejected
because transport and client code form a second trust boundary. Accepting model-generated analytics
data after schema validation was rejected because type safety does not prove numerical grounding.  
**Consequences:** Gen-UI is bounded, portable, testable offline, and fails closed at both boundaries.
Adding a component requires explicit Pydantic, Zod, renderer-registry, grounding, and test changes.
Phase 8 does not support custom code, arbitrary styling/actions, interactive callbacks, or
model-defined layouts, and the frontend remains a development shell rather than a final dashboard.

## ADR-018 — Layered Deterministic Sentinel with Narrow Semantic Escalation

**Status:** Accepted  
**Context:** Phase 9 must detect unsafe requests, fabricated provenance, unsupported claims, unsafe
output, malformed Gen-UI, and accidental secrets without concentrating unrelated policies in one
generic model prompt. Input rejection must happen before provider inference, while repairable answer
failures need a bounded correction path.  
**Decision:** Add a deterministic pre-router `InputGuard`, then run independent `GroundingGuard` and
`OutputGuard` stages after synthesis. Citation IDs and document/video locators must map exactly to
the current trusted context; explicit unknown citations/pages, missing evidence, analytics-result
mismatches, numeric contradictions, low coverage, and irrelevant context become machine-readable
findings. Output checks enforce length, Pydantic Gen-UI validation, markup/script rejection, and
secret-pattern blocking. Malformed Gen-UI is removed while safe text survives. Only an ambiguous
lexical-support band may call a dedicated structured semantic classifier with booleans and an enum;
it has no rationale field. Block critical findings immediately, allow one rewrite for repairable
findings, then terminate as blocked if the same safety requirement remains.  
**Alternatives:** One all-purpose Sentinel prompt was rejected because it mixes security policy,
provenance, schema validation, and semantic judgment in a hard-to-test black box. Model-only
citation validation was rejected because authoritative identifiers and locations are exactly
checkable. Unlimited or repeated repair was rejected because it can loop and increase cost.
Silently redacting provenance failures was rejected because it can make unsupported answers appear
grounded.  
**Consequences:** Unsafe input incurs no provider call, most guardrail behavior is offline-testable,
and public diagnostics contain only scores, booleans, and safe codes. Lexical coverage and secret
patterns remain conservative heuristics with possible false positives or negatives. The optional
semantic signal is not proof of truth and fails conservatively when unavailable.

## ADR-019 — Post-Guardrail Typed SSE Through a Transport-Only Gateway

**Status:** Accepted  
**Context:** Phase 10 needs incremental browser communication and operational activity without
exposing unsafe drafts, graph internals, private reasoning, or AI responsibilities in the gateway.
POST input, long-running inference, client/upstream disconnects, proxy buffering, and serverless
upload constraints require explicit transport boundaries.  
**Decision:** Add a strict versioned SSE event union owned by FastAPI and mirror it with Zod for the
React client. Project LangGraph state snapshots into safe lifecycle events, but release answer chunks
only from the final Sentinel-checked response. Carry monotonic SSE IDs plus request/correlation IDs;
use heartbeat comments, total timeouts, normalized errors, and disconnect-triggered iterator cleanup.
Use streaming `fetch()` in React for the JSON POST. Keep Express transport-only: validate with Zod,
generate/propagate IDs, rate-limit, apply security/CORS, enforce an upstream timeout, proxy SSE bytes,
abort upstream on downstream close, and normalize transport failures. Register no binary upload
proxy routes.  
**Alternatives:** Native `EventSource` was rejected for this endpoint because it cannot send the
required POST JSON body. Streaming provider drafts before Sentinel was rejected because unsafe or
secret-like content could escape before output validation. Reimplementing orchestration or parsing
semantic events in Express was rejected because the gateway must not own AI logic. Proxying PDF/MP4
uploads was rejected because production Vercel functions are not the large-binary data path.  
**Consequences:** The full React-to-AI path is typed, disconnect-aware, bounded, and testable in Mock
mode. Provider-native token timing is not yet available: token events chunk the safe final response.
The in-memory rate limiter is process-local, SSE replay is not persisted, and a blocking provider call
may finish after disconnect before its worker can observe the stop request.

## ADR-020 — Answer-First Responsive Workspace With Local-Only Binary Ingestion

**Status:** Accepted  
**Context:** Phase 11 must communicate an Enterprise AI Intelligence OS rather than a generic admin
dashboard. Answers, trusted provenance, operational execution, structured visual output, and
quality signals need a clear hierarchy across desktop, tablet, and mobile. The browser also needs a
useful local ingestion experience without violating the rule that production binaries bypass the
Express/Vercel gateway.  
**Decision:** Make the AI workspace the default product surface and organize the desktop experience
into navigation, answer, and evidence/execution zones. Collapse secondary panels below the answer on
tablet and into explicit mobile navigation/drawers on phones. Derive streaming labels and quality
values only from validated Phase 10 events. Keep the eight Gen-UI discriminators in a frozen static
registry and implement chart types with statically imported Recharts primitives. Seek video evidence
to repository-derived `start_seconds`. Use a Vite-only `/ai-local` proxy for bounded local FastAPI
health, listing, and multipart upload; disable direct upload in production builds.  
**Alternatives:** A metric-card admin dashboard was rejected because it makes AI interaction
secondary. Rendering invented demo analytics was rejected because the UI must not fabricate source
or quality data. Proxying binaries through Express was rejected by the production upload boundary.
Dynamic Gen-UI imports and model-authored markup remained prohibited.  
**Consequences:** The portfolio now demonstrates an answer-first multimodal workflow with honest
empty, loading, cold-start, partial, and unavailable states. Local uploads work without weakening the
gateway. Production still requires a future signed object-storage control flow. Recharts adds bundle
weight, so it is emitted as a dedicated build chunk; uploaded video playback URLs last only for the
current browser session because the local API exposes metadata rather than stored binaries.

## ADR-021 — Durable Mongo Vectors With Disposable Chroma and Direct Supabase Uploads

**Status:** Accepted
**Context:** Render free instances have ephemeral filesystems, while rebuilding embeddings after
every cold start would consume provider quota and delay useful retrieval. Production PDF/video
binaries also cannot safely traverse the Vercel gateway.
**Decision:** Treat MongoDB metadata records as the durable source of truth for chunk and segment
text, provenance, embedding vectors, provider/model identifiers, checksum, and timestamp. Treat
Chroma as a disposable active index and reconcile exact identifier sets in a background startup
task using stored vectors only. Keep `/health` independent and expose retrieval state at `/ready`.
Store original assets in a private `synapse-assets` Supabase bucket. Let the browser request a
short-lived signed URL through validated JSON, upload directly, then submit a server-generated
object path under a one-time durable upload intent. Keep the service-role key server-only.
**Alternatives:** Durable local Chroma on Render was rejected because the filesystem is ephemeral.
Re-embedding on startup was rejected for cost, latency, and model-drift reasons. Gateway multipart
proxying was rejected because serverless request limits make it unsuitable for large binaries.
**Consequences:** A cold instance can answer liveness probes immediately and becomes retrieval-ready
after reconstruction. Mongo storage grows with embedding vectors, the demo remains subject to free
tier limits, and operators must configure Mongo/Supabase networking, a private bucket, and CORS.
Tests use in-memory vectors, fake objects, and mongomock without cloud credentials.

## ADR-022 — Aggregate, Self-Hosted Evaluation Summaries

**Status:** Accepted  
**Date:** 2026-07-10  
**Context:** Phase 13 needs reproducible quality and latency evidence without paid observability
SaaS, and public metrics must not become a path for leaking benchmark prompts, retrieved context,
draft answers, system prompts, or private graph state. Remote evaluation execution would also let an
unauthenticated caller consume configured-provider quota.  
**Decision:** Run versioned fixtures explicitly through a local CLI, using Mock mode by default.
Measure the real retrieval service, graph, and layered guards but persist only strict aggregate
summaries with safe configuration/provider identity. Store them through a dedicated repository:
MongoDB when configured, atomic JSON otherwise, and in memory for tests. Expose only bounded recent
summaries over a read-only API; do not expose a remote run endpoint in this phase.  
**Alternatives:** Hosted LangSmith, Arize, or W&B were rejected because the product must remain
self-hosted and free-tier compatible. Persisting per-case prompts and answers was rejected because
aggregate portfolio evidence does not justify the privacy and prompt-disclosure risk. Triggering
configured-provider runs over HTTP was rejected until authentication and job controls exist.  
**Consequences:** CI and local runs are network-free and comparable by dataset/configuration
fingerprint, while Mongo supports durable production history. Timing values vary by machine and are
observations rather than deterministic assertions; richer per-case diagnosis remains CLI-local and
future authenticated scheduling is deferred.

## ADR-023 — Defense-in-Depth at Both HTTP Boundaries

**Status:** Accepted
**Date:** 2026-07-12
**Context:** The production-readiness review found that the gateway already applied core transport
controls, but upload-control routes were outside its rate limiter, JSON proxy failures could relay
upstream details, and direct FastAPI responses lacked a consistent CORS/header/logging boundary.
Validation errors could also include rejected input through FastAPI's default response.
**Decision:** Apply strict origin configuration and request/response hardening independently at the
gateway and AI service. Rate-limit every gateway API control route, use bounded safe request IDs,
emit body-free structured access/error events, abort JSON/SSE upstream work on timeout or disconnect,
and normalize upstream and unexpected failures without relaying bodies or exception messages. Keep
the gateway free of prompts and AI logic. Treat this application layer as defense in depth, not as a
replacement for identity, edge limits, private networking, or centralized monitoring.
**Alternatives:** Relying only on browser CORS and hosting defaults was rejected because FastAPI is
used directly in local workflows and platform defaults vary. Returning complete validation/provider
errors was rejected because submitted values and external response bodies can contain secrets.
Adding authentication or distributed infrastructure was rejected as a major feature outside Phase
14.
**Consequences:** Both services now have explicit, testable failure and header behavior; upload
controls share gateway abuse limits; diagnostics retain safe correlation metadata. Rate limiting is
still per process, direct FastAPI exposure still needs an edge control, and production log transport,
alerting, tenant authorization, and live cloud failure drills remain operator responsibilities.

## ADR-024 — Split Serverless Edge From Reconstructable AI Compute

**Status:** Accepted
**Date:** 2026-07-13
**Context:** The $0 portfolio target combines Vercel serverless projects with a stateful AI process
that needs FFmpeg, background Chroma reconstruction, long-lived inference streams, and credentials
for MongoDB, Supabase, and Mistral. A production Vite build also cannot rely on its development-only
`/ai-local` proxy, and raw PDF/video bodies must not traverse Vercel Functions.
**Decision:** Deploy frontend and gateway as separate Vercel projects, default-export the thin
Express application from `src/index.ts`, and route production browser control traffic exclusively
through `VITE_GATEWAY_URL`. Limit gateway JSON forwarding to explicit typed routes and keep SSE as
the sole streamed route. Deploy FastAPI in a non-root Python 3.11 Docker image on Render with FFmpeg
and a `$PORT`-driven command. Keep Atlas vectors durable, Chroma disposable, and Supabase uploads
browser-direct through server-authorized signed URLs. Poll `/ready` with a bounded increasing delay
and keep `/health` dependency-free.
**Alternatives:** A single Vercel application was rejected because Python media/reconstruction work
does not fit the thin serverless boundary. Direct browser calls to Render were rejected because
they duplicate public control origins and bypass gateway transport controls. Proxying binary files
through Vercel and treating Render disk as durable remained prohibited. Unbounded wake polling was
rejected because it can amplify cold-start traffic.
**Consequences:** The checked-in manifests can be connected to free provider projects without
committing credentials or provisioning paid services. Operators must configure five providers,
exact origins, and secrets manually. Cold starts, free quotas, per-instance rate limits, ephemeral
indexes, and the absence of authentication remain explicit portfolio limitations.

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
