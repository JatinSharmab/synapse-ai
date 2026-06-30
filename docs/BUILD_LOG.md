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

## Phase 4 — Citation-Grounded PDF Ingestion and Document RAG

**Date:** 2026-06-26  
**Status:** Complete

### Delivered

- Added strict local PDF validation for filename extension, `application/pdf` media type, PDF
  signature, upload size, readability, encryption state, and page count.
- Added page-aware PyMuPDF extraction, whitespace/hyphen normalization, and removal of repeated short
  page-edge boilerplate while preserving page boundaries.
- Added semantic-aware chunking that prefers heading, paragraph, and sentence boundaries before a
  word-boundary fallback for oversized sentences. Maximum, minimum, and overlap token estimates are
  configurable; chunks never span pages.
- Added typed document, chunk, stored-vector, and retrieval models. Every chunk records trusted
  document ID, filename, page number, chunk ID/index, text, token estimate, checksum, and UTC creation
  time.
- Added a typed metadata-repository abstraction with in-memory and atomic JSON snapshot adapters.
- Added a typed vector-store abstraction and ChromaDB adapter using caller-supplied embeddings,
  cosine distance, local persistence, explicit provenance metadata, and no Chroma embedding function.
- Added index reconstruction from persisted vectors without repeating embedding-provider calls.
- Added the local-development document upload/list/delete APIs and dense document-search API.
  Production-mode direct upload is explicitly disabled.
- Added `ocr_required=true` handling for PDFs with little/no extractable text; no OCR provider is
  invoked automatically.
- Connected the LangGraph Document Search node to the real retriever and supplied bounded retrieved
  context to Synthesizer. Citations are constructed deterministically from authoritative retrieval
  metadata, never model-authored location fields.
- Connected `LLMProvider.embed()` to chunk indexing and query embedding. Tests remain deterministic
  and network-free through a normalized hashed-token Mock embedding.
- Added a generated three-page synthetic PDF with known page-specific facts, plus a transparent
  regeneration script.
- Added Phase 4 environment settings, dependencies, API/architecture documentation, and ADR-013.

### Verification

- Valid PDF upload returns trusted metadata and persists page-aware chunks.
- Corrupt PDFs, wrong extensions/media types, and non-PDF data masquerading as PDF are rejected.
- Low/no-text PDFs return `ocr_required=true` with no chunks and no automatic OCR.
- Chunk tests verify semantic boundaries, configured bounds, overlap, required metadata, checksums,
  stable global indexes, and page provenance.
- Dense retrieval deterministically returns the fixture's refund policy from page 2 with its actual
  document ID, filename, chunk ID, and similarity score.
- A document-routed graph invocation terminates with the retrieved answer and the same trusted page-2
  citation metadata.
- Deletion removes both the document listing and its searchable vector entries.
- `ruff check --no-cache app tests ../scripts/generate_sample_pdf.py` passed.
- `ruff format --no-cache --check app tests ../scripts/generate_sample_pdf.py` passed for 59 files.
- Strict `mypy` passed across 58 application and test source files.
- `AI_PROVIDER=mock pytest -p no:cacheprovider` passed all 24 AI-service tests.
- Root npm lint and TypeScript typechecks passed.
- The gateway health smoke test passed (1 test), and frontend/gateway production builds passed.

### Resolved During Verification

- The first expanded test run exposed `zip(..., strict=True)` on adjacent chunk pairs, which must
  differ in length by one. It was corrected to `strict=False`; the full suite then passed.
- The first Mock embedding ranked an unrelated page for a graph query. Stopword filtering and a
  larger deterministic hashed-token vector improved the offline semantic proxy; retrieval now
  selects the known page-2 policy fixture reproducibly.
- Chroma's SQLite persistence could not create files under the workspace in this sandbox. Safe local
  defaults were moved under the operating-system temporary directory and remain fully configurable
  with `DOCUMENT_METADATA_PATH` and `CHROMA_PERSIST_PATH`.
- NumPy 2.5's installed type stubs use Python 3.12 type-alias syntax while this project typechecks a
  Python 3.11 floor. Mypy skips only third-party Chroma/NumPy implementation imports; all Synapse
  application and test sources remain strict.
- The final fixture-generator lint initially reported three overlong strings and one formatting
  difference. The source was reformatted, and both final Ruff checks passed.
- A two-run fixture hash check found that PyMuPDF regenerated internal file identifiers. Reproducible
  save mode and `no_new_id` were enabled so repeated generation produces the same PDF hash.
- Chroma emits one upstream Python 3.14 deprecation warning for `asyncio.iscoroutinefunction`; it was
  reported and not suppressed.
- Git status/diff inspection remained unavailable because Git rejected the workspace ownership as
  unsafe. No global Git configuration was changed to bypass that safety check.

### Deferred by Design

- OCR execution and OCR-provider integration
- BM25, Reciprocal Rank Fusion, and reranking
- Video ingestion/retrieval and deterministic CSV analytics execution
- MongoDB, Supabase object storage, authentication, persistent thread memory, and production upload
  orchestration
- Original PDF binary persistence, distributed transactions, and multi-process concurrency for the
  local JSON metadata adapter
- Gen-UI, semantic Sentinel checks, evaluations, streaming, and deployment
- Live Mistral retrieval verification, which requires a user-provided API key, network access, and
  quota

## Phase 5 — Hybrid Document Retrieval and Offline Evaluation

**Date:** 2026-06-28  
**Status:** Complete

### Delivered

- Added deterministic Unicode/whitespace query normalization and bounded removal of request/source
  scaffolding before retrieval. Query rewriting uses no LLM call.
- Retained Chroma cosine retrieval and added Apache-licensed `rank-bm25` 0.2.2 lexical retrieval over
  authoritative stored chunks with shared query/corpus preprocessing.
- Added deterministic Reciprocal Rank Fusion with `k=60`, combining ranks rather than incomparable
  vector and BM25 score scales.
- Added a CPU-only local reranker using query-term coverage, exact identifier coverage, phrase
  presence, and normalized RRF position. No paid API or runtime model download is used.
- Added bounded context selection that de-duplicates chunk IDs and requires complete trusted
  document/page provenance before synthesis.
- Added typed internal retrieval-stage records for `vector_candidates`, `bm25_candidates`,
  `fused_candidates`, `reranked_candidates`, and `final_context`.
- Added `POST /api/v1/debug/retrieval/documents`, conditionally registered only with `DEBUG=true`.
  With the default false value it returns 404, is absent from OpenAPI, and regular search/chat
  responses do not expose debug state.
- Added typed `VECTOR_TOP_K`, `BM25_TOP_K`, `RERANK_TOP_K`, and `FINAL_CONTEXT_K` settings with safe
  bounds and final-context/rerank consistency validation.
- Added explicit `vector_only` and `hybrid` search modes for evaluation while keeping hybrid as the
  normal document-search and LangGraph path.
- Added the versioned `document-retrieval.v1.json` dataset with query, relevant filename, page, and
  global chunk index labels.
- Added offline Recall@K and Mean Reciprocal Rank evaluation support plus a runnable comparison CLI.
- Updated the AI design, system architecture, API contracts, README, sample-data guide, and ADR-014.

### Verification

- BM25 tests prove an exact `ORION-30` identifier ranks above generic refund content.
- RRF tests prove a candidate appearing in both ranked lists outranks single-list candidates.
- Reranking tests prove exact identifier coverage can promote a lower-fused candidate.
- Debug-route tests prove the endpoint and OpenAPI path are absent when disabled and all five stages
  are returned when enabled.
- Public search tests prove retrieval-debug fields do not leak into normal responses.
- The versioned evaluation dataset loads and runs both retrieval modes against trusted chunk labels.
- Final offline evaluation at K=3: vector-only Recall@3 `1.0`, MRR `1.0`; hybrid Recall@3 `1.0`, MRR
  `1.0`. The small exact-match fixture does not demonstrate a metric delta, and no gain is claimed.
- `ruff check --no-cache app tests ../scripts/generate_sample_pdf.py` passed.
- `ruff format --no-cache --check app tests ../scripts/generate_sample_pdf.py` passed for 72 files.
- Strict mypy passed across 71 application and test source files.
- `AI_PROVIDER=mock pytest -p no:cacheprovider` passed all 30 AI-service tests.
- Root npm lint and TypeScript typechecks passed.
- The gateway health smoke test passed (1 test), and frontend/gateway production builds passed.

### Resolved During Verification

- The first dependency install was blocked from reaching PyPI inside the sandbox. It was rerun with
  explicit network permission and installed only the declared free `rank-bm25` package.
- The host environment defines `DEBUG=release`, which initially caused Pydantic collection errors.
  Debug parsing now fails closed: only explicit `1`, `true`, `yes`, or `on` values enable the route.
- The first Ruff check found three overlong lines and six formatting differences. Ruff could not
  write formatter changes in the sandbox, so the exact formatting fixes were applied explicitly;
  final lint and format checks passed.
- Chroma continues to emit one upstream Python 3.14 deprecation warning for
  `asyncio.iscoroutinefunction`; it remains visible and unsuppressed.

### Deferred by Design

- Learned cross-encoder/FlashRank reranking and local model artifact management
- Persistent/cached BM25 indexes for corpora beyond the current portfolio-scale local repository
- Larger and adversarial retrieval evaluation datasets capable of measuring statistically useful
  vector-versus-hybrid differences
- OCR execution, video retrieval, analytics execution, authentication, hosted metadata/object
  storage, thread memory, Gen-UI, streaming, and deployment
- Live Mistral evaluation, which requires a user-provided API key, network access, and quota

## Phase 6 — Multimodal Video Ingestion and Semantic Retrieval

**Date:** 2026-06-30  
**Status:** Complete

### Delivered

- Added strict MP4 filename/media-type/signature/size validation plus trusted ffprobe stream,
  duration, dimensions, audio-presence, and container validation.
- Added safe FFmpeg/ffprobe execution using generated storage paths, explicit argument lists,
  `shell=False`, subprocess timeouts, return-code checks, and derived-output validation.
- Added bounded interval-based representative keyframe selection controlled by
  `MAX_VIDEO_SIZE_MB`, `MAX_VIDEO_DURATION_SECONDS`, `MAX_KEYFRAMES`, and
  `KEYFRAME_INTERVAL_SECONDS`. The implementation does not analyze every frame.
- Connected optional `LLMProvider.describe_image()` enrichment with at most one call per selected
  keyframe. The first vision failure stops additional vision calls and yields a persisted partial
  video instead of aborting ingestion.
- Added a typed `TranscriptionProvider` boundary with disabled and deterministic offline Mock
  providers. Optional mono 16 kHz PCM extraction occurs only when transcription is enabled and an
  audio stream exists; no paid transcription dependency is required.
- Added typed video records and temporal segments carrying video/segment IDs, trusted filename,
  start/end seconds, transcript, visual description, combined text, relative keyframe reference,
  and safe embedding metadata.
- Added authoritative in-memory/atomic-JSON video repositories and a separate Chroma video-segment
  collection with index reconstruction from persisted embeddings.
- Added local-development `POST /api/v1/videos`, `GET /api/v1/videos`, and
  `POST /api/v1/search/videos` endpoints. Production direct upload is disabled.
- Connected LangGraph `video_search` to the real temporal retriever. Video contexts and citations
  now use repository-resolved IDs, filenames, segment IDs, and timestamp ranges; Mock synthesis
  consumes retrieved evidence without fabricating provenance.
- Added Phase 6 typed settings/environment examples, documentation, API contracts, and ADR-015.

### Verification

- Valid synthetic MP4-shaped test uploads use exactly three representative timestamps under the
  configured cap and produce three aligned segments.
- Segment tests verify timestamp boundaries, trusted filename/video identifiers, keyframe
  references, and embedding metadata.
- Semantic search and graph tests resolve search results/citations back to authoritative temporal
  records.
- Vision-unavailable tests prove ingestion returns `partial`, transcription still completes, and
  no vision calls occur after the first failure.
- Validation tests reject non-MP4 data masquerading as MP4 and wrong extension/media types.
- Subprocess tests prove ffprobe receives an argument list, `shell=False`, a configured timeout, and
  rejects paths outside the video storage root.
- All Phase 6 tests use `MockProvider`, Mock transcription, and fake media processing; no test calls
  live Mistral, a paid transcription API, FFmpeg, or the internet.
- `ruff check --no-cache app tests ../scripts/generate_sample_pdf.py` passed.
- `ruff format --no-cache --check app tests ../scripts/generate_sample_pdf.py` passed for 87 files.
- Strict mypy passed across 86 application and test source files.
- `AI_PROVIDER=mock pytest -p no:cacheprovider` passed all 38 AI-service tests.
- Root npm lint and TypeScript typechecks passed.
- The gateway health smoke test passed (1 test), and frontend/gateway production builds passed.

### Resolved During Verification

- The workspace denies tool-created Ruff/Pytest cache directories, so checks use `--no-cache` and
  final tests use `-p no:cacheprovider`; failures remain visible.
- Ruff's formatter could inspect but not write workspace files under the sandbox. Its exact
  suggested formatting changes were applied explicitly and then rechecked.
- The first final mypy run found one missing return annotation on a test-only FastAPI factory. The
  annotation was added, and the second strict run passed all 86 checked source files.
- FFmpeg and ffprobe are not installed on the verification machine. The real subprocess adapter was
  validated with controlled subprocess tests, but end-to-end decoding of a real MP4 remains a
  required manual verification after installation.
- Git status/diff inspection remains unavailable because Git rejects the workspace ownership as
  unsafe. No global Git safety configuration was changed.

### Deferred by Design

- Content-aware scene detection and learned visual shot selection
- A live speech-to-text provider and production transcription queue
- Video hybrid lexical retrieval, temporal reranking, OCR, and broader multimodal evaluation
- Production object storage/signed uploads, distributed jobs, deletion API, and artifact lifecycle
- Analytics execution, authentication, persistent threads, Gen-UI, streaming, and deployment
