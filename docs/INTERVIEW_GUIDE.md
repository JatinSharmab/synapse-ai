# Synapse Interview Guide

These answers are deliberately grounded in the code currently in this repository. They are intended as concise 30-90 second interview responses, not promises about infrastructure that is not deployed.

## Why LangGraph?

Synapse uses LangGraph because the chat request has explicit, inspectable stages rather than one opaque prompt: input guards, routing, one selected tool path, synthesis, and Sentinel validation. The graph in `ai-service/app/graph/` carries a typed `SynapseState`, conditionally routes to document, video, analytics, or direct-answer nodes, and makes the rewrite/termination behavior explicit. This is useful for a multimodal system because it exposes safe operational state - the selected route, tool status, citations, and guardrail decision - without exposing chain-of-thought.

## Why hybrid retrieval?

Hybrid retrieval combines strengths that matter for enterprise documents. `DocumentRagService` gets semantic candidates from Chroma and lexical candidates from `rank-bm25`, then `reciprocal_rank_fusion` combines rank positions and `LocalCoverageReranker` promotes terms, identifiers, and exact phrase matches. That is more robust when a question uses a policy number, exact product name, or wording that semantic embeddings might soften. The implementation is local and free-tier friendly; it does not depend on a paid reranking API.

## Why not vector search only?

Vector search is useful for meaning, but exact retrieval can suffer when a query contains a rare identifier, an acronym, a specific clause, or a verbatim phrase. Synapse therefore runs both vector and BM25 retrieval. The RRF implementation does not assume vector and BM25 scores are directly comparable, and the reranker checks lexical coverage and identifiers. This is a practical quality tradeoff, not a claim that hybrid retrieval is universally better for every corpus.

## Why ChromaDB?

Chroma is the active local vector index in Synapse because it supports the portfolio project's embedding-based document and temporal-video retrieval without requiring a paid hosted vector service. It is wrapped behind repository/service abstractions rather than spread through API routes. The code also recognizes that local Chroma files on Render are ephemeral: durable chunk text, metadata, and embeddings are persisted through the metadata repository so Chroma can be rebuilt on startup without re-embedding.

## How does PDF ingestion work?

The document ingestion service first validates the file rather than trusting a filename: extension, MIME information, PDF magic bytes, size/readability constraints, and extraction behavior are checked. PyMuPDF extracts text page by page. The text is normalized and chunked using heading, paragraph, and sentence boundaries before configured size and overlap limits are enforced. Every chunk receives provenance including document ID, filename, page number, chunk ID, checksum, token estimate, text, and creation time, then is embedded and indexed. A low-text PDF returns `ocr_required` rather than silently running OCR.

## How are citations generated?

Document and video retrieval objects keep their provenance through the graph. The document node provides actual chunk metadata, while the video node provides actual segment timestamps. The synthesizer builds citations from those retrieved records; it is not allowed to invent a filename, page, document ID, chunk ID, video ID, or timestamp. Sentinel's grounding guards then verify citation existence and citation-to-retrieved-context mapping before approving output. The tests include provenance and fabricated/nonexistent citation cases.

## How does video RAG work?

Synapse targets small MP4 portfolio videos. It validates the file and limits, reads metadata with `ffprobe`, and uses FFmpeg to extract a bounded set of representative keyframes. Optional vision descriptions and a transcription-provider abstraction contribute to timestamped temporal segments. Those segments have combined searchable text and provenance such as start/end seconds, video ID, filename, segment ID, and keyframe path. Video search retrieves segments and the frontend can seek the player to the returned start time.

## Why extract keyframes instead of every frame?

Analysing every video frame is expensive and mostly repetitive for a small demo video. The implementation uses configurable maximum-keyframe and interval/scene controls to choose representative frames. That limits CPU, disk, and optional vision-provider usage while retaining evidence linked to a time range. It is an explicit free-tier optimization, not a claim of exhaustive frame-level understanding. If vision is unavailable, ingestion continues with clearly marked partial enrichment.

## How does temporal retrieval work?

Video ingestion turns audio/transcript and optional visual descriptions into temporal segments rather than one monolithic video record. Each segment stores `start_seconds`, `end_seconds`, combined text, and source identifiers before it is embedded into the video collection. A search returns the matching segment with score and timestamp provenance. The UI's video-evidence component sets `video.currentTime` to the evidence start time, making the retrieval result directly inspectable by a user.

## How is CSV analytics kept safe?

The system does not give a model a general programming tool. Pydantic schemas define a limited set of analytical operations such as count, sum, mean, min, max, group-by, sort, top-N, and aggregation. The deterministic executor validates dataset columns, operation type, aggregation and grouping fields, and row limits, then computes the numerical result in application code. The model can help classify a question or summarize deterministic output, but it is not the source of truth for the calculation.

## Why not let the LLM execute arbitrary Python?

Allowing arbitrary model-generated Python would turn a natural-language request into code-execution risk: data access, file access, resource exhaustion, and behavior that is hard to audit or reproduce. Synapse deliberately has no Python shell, `eval`, or `exec` path. Its constrained operation schema is easier to validate and test, and it keeps the calculation deterministic. The tradeoff is narrower analytical expressiveness, which is appropriate for this portfolio's security boundary.

## What is structured Gen-UI?

Structured Gen-UI means the model can request presentation data, not frontend source code. Synapse supports a finite protocol: text, metric, bar/line/pie chart, table, citation list, and video evidence. The Python service validates it with Pydantic and the React app repeats validation with Zod. The frontend then maps an accepted type to a fixed component registry. This lets the UI show useful visual output while retaining a strong boundary between model data and executable application code.

## How do you protect Gen-UI from malicious output?

The protocol rejects arbitrary React, JSX, JavaScript, HTML, script tags, unknown component types, malformed data, and invalid chart keys. There are Pydantic and Zod schemas, a fixed renderer registry, and no dynamic import or `eval` based on model text. Sentinel also validates Gen-UI as an output guard. If any layer receives malformed data, the UI fails closed to safe text rather than trying to render untrusted markup. Tests cover unknown types, missing fields, malformed data, unsafe HTML/script attempts, and invalid chart keys.

## What is Sentinel?

Sentinel is Synapse's final guardrail stage, but it is not one giant generic prompt. It is organized into input guards, grounding guards, and output guards. It can approve a response, request a single rewrite, or block it. Input checks look for injection and dangerous instructions; grounding checks evidence and citations; output checks Gen-UI, length, unsafe markup, and secret-like patterns. That separation makes decisions more explainable and lets the system prefer deterministic checks where possible.

## How do you detect unsupported claims?

For grounded responses, Sentinel compares citations to the retrieved context and checks existence, source mapping, provenance, coverage, and relevance. A citation that points to a nonexistent page or chunk fails rather than becoming an authoritative-looking answer. The implementation also has deterministic unsupported-claim and evidence-coverage checks, with narrow structured semantic judgement available only when deterministic logic cannot resolve ambiguity. Adversarial tests cover fabricated citations, nonexistent page references, and unsupported factual claims.

## How do you prevent LangGraph loops?

The graph has explicit edges and a state field, `rewrite_count`. After synthesis, Sentinel either approves to END, blocks to END, or returns to synthesis only when a rewrite is warranted and the count is below one. The maximum rewrite count is one, so there is no open-ended self-correction cycle. Tests explicitly assert graph termination and that repeated Sentinel rewrite signals cannot loop indefinitely.

## Why SSE?

Server-Sent Events are a simple browser-friendly fit for one-way progress and answer streaming. Synapse sends typed operational events such as request started, selected route, retrieval completion, generation lifecycle, guardrail completion, and final completion. The gateway validates and forwards the request while FastAPI owns the AI work. SSE lets the UI show useful progress without pretending to reveal chain-of-thought. The implementation also handles request IDs, client/upstream disconnects, timeouts, cleanup, and normalized error events.

## How do you measure RAG quality?

Synapse has a version-controlled evaluation dataset and a reproducible Python CLI. It measures retrieval Recall@K, MRR, latency, and vector-only versus hybrid results. It also records route/tool accuracy and generation proxies such as groundedness, citation coverage, and answer relevance. These are practical internal evaluation signals, not a claim of comprehensive human evaluation. The runner persists summary metadata to Mongo when configured or to local JSON otherwise, excluding prompts and hidden reasoning.

## What is Recall@K?

Recall@K asks whether a relevant evidence item appears anywhere in the top K retrieval results. For example, if the expected PDF chunk/page is present in the top five candidates, that query counts as a Recall@5 success. It is useful in Synapse because an answer cannot be well grounded if the relevant source never reaches synthesis. Recall alone does not say whether the correct evidence was ranked first, which is why the project also tracks MRR.

## What is MRR?

Mean Reciprocal Rank measures how highly the first relevant result is ranked. For each query, it takes one divided by the rank of the first relevant item, then averages those values across the dataset. A relevant result at rank one earns 1.0, while rank five earns 0.2. In Synapse, MRR complements Recall@K: it indicates whether useful evidence is not only retrieved but surfaced early enough for the final context selection.

## How would this architecture scale?

The repository intentionally stays free-tier and single-service oriented today. A production evolution would move PDF/video ingestion into dedicated workers and task queues, add Redis for distributed rate limiting/caching, use managed vector/search infrastructure, implement identity and tenant isolation, centralize observability, and independently autoscale gateway/API workloads, potentially on Kubernetes. Those are future design directions only; Redis, queues, Kubernetes, autoscaling, enterprise SSO, and managed secrets are not currently deployed.

## What happens when Mistral reaches quota?

The Mistral provider uses configured request timeouts and retries transient network/server failures only. It handles 429 responses cleanly and avoids aggressive retries on quota errors. Credentials are environment-only and not logged. For development and tests, `AI_PROVIDER=mock` lets the application start without network access. A real quota exhaustion still limits Mistral-backed quality/features until quota is available; it is surfaced as a controlled provider/error condition rather than being hidden.

## What happens when Render restarts?

Render's free local filesystem is treated as ephemeral. `/health` returns quickly, while startup reconstruction runs without indefinitely blocking readiness. The service checks whether Chroma is absent or incomplete and, when durable metadata is configured, rebuilds the active index from persisted chunk/segment text, metadata, and stored embedding vectors. This avoids calling the embedding API solely because a Render instance restarted. Until rebuilding succeeds, `/ready` reports retrieval state rather than falsely claiming readiness.

## How is Chroma rebuilt?

The persistence abstraction stores enough durable information for every indexed item: source IDs, text, metadata/provenance, embedding vector, embedding model/version, checksum, and timestamp. On startup, the service checks Chroma's state. If the index is missing or incomplete, it loads durable records through the metadata repository and re-adds those existing vectors to Chroma. The rebuild path is tested using local/fake repositories, so unit tests do not need real MongoDB, Supabase, or an embedding API.

## Why MongoDB and Chroma together?

They have different responsibilities. Chroma is optimized here as the active vector retrieval index, while MongoDB is the optional durable metadata and embedding record store. Keeping durable text, provenance, and vectors in Mongo addresses the fact that free Render disk is not durable and allows an index rebuild without a fresh provider embedding call. The code also has local/test repository alternatives, so cloud credentials are not a test prerequisite.

## Why Supabase?

Supabase Storage is used as the planned private object store for PDFs and videos because it supports a browser-to-storage signed upload flow. That means large files do not traverse Vercel functions: the backend creates a signed URL using a server-side service credential, the browser uploads directly, and FastAPI ingests the stored object reference. The frontend receives no service-role key. Local direct upload remains useful for development, but production file upload is designed around object storage.

## What limitations exist in the free deployment?

The prepared free-tier path has cold starts, quotas, limited CPU/memory, ephemeral local disk, and restricted throughput. Chroma must rebuild after a restart, Mistral free mode can be quota limited, and video processing should remain small and bounded. The portfolio project also lacks authentication, RBAC, tenant isolation, malware scanning, distributed rate limits, centralized alerting, and enterprise audit retention. These limitations are documented rather than hidden, and the mock provider keeps local testing independent of external services.
