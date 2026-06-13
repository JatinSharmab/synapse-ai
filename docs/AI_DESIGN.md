# AI System Design

## Status

This is the target AI design for future phases. Phase 0 implements none of the described pipelines.

## Design Goals

- Produce useful answers grounded in PDF pages, video timestamps, or deterministic CSV results.
- Preserve provenance from ingestion through the final response.
- Keep all model output constrained, validated, and observable.
- Prefer deterministic logic for routing shortcuts, calculations, validation, and safety checks.
- Minimize provider calls and support network-free automated tests through mock providers.
- Avoid chain-of-thought collection or disclosure.

## Multimodal RAG

Synapse uses a shared evidence model across modality-specific ingestion and retrieval pipelines. A normalized evidence item includes a stable source ID, modality, display name, content excerpt or description, location metadata, retrieval scores, and version information. Location is page-based for PDFs, time-range-based for video, and operation/result-based for datasets.

### PDF Pipeline

1. Validate MIME type, extension, size, readability, encryption status, and page limits.
2. Extract text page-by-page with PyMuPDF.
3. Clean repeated headers/footers and malformed whitespace without losing page boundaries.
4. Create semantic chunks with controlled overlap.
5. Store each chunk with source ID, canonical filename from trusted metadata, page number, chunk ID, checksum, parser version, and embedding version.
6. Index embeddings in ChromaDB and lexical terms in BM25.
7. Persist sufficient chunk and embedding data in the durable repository for index reconstruction.

### Video Pipeline

1. Validate the stored MP4 object and inspect streams/duration with `ffprobe`.
2. Detect scene boundaries and sample representative keyframes with FFmpeg.
3. Generate concise vision descriptions for selected frames only.
4. Optionally transcribe audio when enabled and useful.
5. Combine aligned frame descriptions and transcript spans into temporal segments.
6. Store segment IDs, start/end timestamps, frame references, transcript references, checksums, model versions, and embeddings.

Analyzing every frame is explicitly out of scope. Sampling thresholds and per-video limits cap latency and API use.

### Hybrid Retrieval

For documents and videos, the query is searched through both dense vector retrieval and BM25 lexical retrieval. Ranked lists are combined using Reciprocal Rank Fusion:

```text
RRF_score(item) = sum(1 / (k + rank_in_list))
```

A lightweight, locally executable reranker then considers query-evidence relevance and diversity. Context selection enforces token limits, modality-aware diversity, source permissions, and provenance completeness. Missing provenance makes an item ineligible for grounded answer context.

## LangGraph State

The graph state will be a typed structure with reducers only where concurrent updates are intentional. A conceptual state is:

```text
request_id / correlation_id
query
conversation_summary
authorized_source_ids
available_modalities
route
route_confidence
tool_requests
tool_results
evidence[]
analytics_results[]
draft_answer
gen_ui_components[]
citations[]
sentinel_findings[]
sentinel_decision
rewrite_count (0 or 1)
safe_trace_events[]
metrics
public_error
```

Raw chain-of-thought is neither a state field nor an event. Tool results and evidence use typed domain models rather than free-form agent messages wherever possible.

## Router

The Router selects one of `document_search`, `video_search`, `data_analytics`, or `direct_answer`, with an option for a deliberately bounded multi-tool plan if a later phase explicitly authorizes it. It receives source availability, the user query, and safe conversation context.

Routing combines deterministic signals with structured model classification. Examples include explicit dataset operations, selected source types, and references to pages or timestamps. Its output is schema-validated and includes a route, confidence, brief safe rationale category, and typed tool parameters—not hidden reasoning.

## Document Search Tool

The tool accepts a normalized query, authorized document IDs, retrieval limits, and optional filters. It returns evidence items with trusted filenames, page numbers, text excerpts, retrieval scores, and chunk IDs. It cannot invent or rewrite provenance. Empty or weak retrieval is an explicit result that the Synthesizer must respect.

## Video Search Tool

The tool accepts a normalized query, authorized video IDs, retrieval limits, and optional time filters. It returns temporal evidence with trusted video names, start/end timestamps, segment descriptions, optional transcript excerpts, representative frame references, and scores. It never converts an approximate model guess into a precise timestamp.

## Data Analytics Tool

The analytics tool executes only a typed allowlist of operations over a validated CSV-backed dataset:

- `describe`
- `count`
- `sum`
- `mean`
- `min`
- `max`
- `group_by`
- `sort`
- `top_n`
- `aggregate`

An analytical request contains enumerated operations, validated column names, typed filters, sort direction, grouping fields, aggregation functions, and bounded row limits. The executor maps this request to controlled dataframe/library calls. It does not evaluate model-generated Python, SQL, expressions, shell commands, or dynamic imports.

All reported numbers come from the deterministic executor. The LLM may explain or format results, but must not recalculate them. The response retains the dataset ID, dataset version/checksum, operation specification, result values, and execution metadata as evidence.

## Synthesizer

The Synthesizer transforms tool results into a concise grounded answer and structured UI proposal. It receives only selected evidence and deterministic analytics results. Its structured output separates:

- natural-language answer;
- atomic citation references;
- allowed Gen-UI components;
- uncertainty or insufficient-evidence status;
- safe display metadata.

Instructions require it to abstain or qualify claims when evidence is insufficient. A Sentinel-requested rewrite includes specific structured findings and occurs at most once.

## Sentinel

Sentinel is a layered pipeline, not a single unconstrained LLM call.

### Input Checks

- query length and request-size limits;
- prompt-injection heuristics;
- suspicious instructions to reveal prompts, override policy, or invoke tools;
- source authorization and tool-parameter validation;
- dangerous or unsupported content patterns defined by product policy.

Retrieved content is treated as quoted evidence, not as executable instruction. Deterministic findings can reject or sanitize a request before orchestration.

### Grounding Checks

- every cited ID exists in the selected evidence set;
- document citations map to the trusted filename and page stored in provenance;
- video citations map to stored temporal segments;
- numerical claims map to deterministic analytics results;
- material factual claims have evidence coverage;
- cited context is relevant to the associated claim;
- unsupported claims are flagged.

Existence, mapping, schema, and numerical checks are deterministic. A structured semantic judge may assess relevance or entailment only when rules cannot decide, and must be isolated behind `LLMProvider` for mockable tests.

### Output Checks

- Pydantic Gen-UI validation;
- component count, text length, row count, and total output limits;
- allowlist enforcement for component and field types;
- rejection of HTML, scripts, event handlers, URLs with unsafe schemes, and executable content;
- accidental secret-pattern scanning and redaction/blocking;
- citation and evidence consistency after serialization.

### Decisions and Bounded Rewrite

Sentinel returns `approve`, `rewrite`, or `block` with machine-readable finding codes. `rewrite` is valid only when `rewrite_count == 0`; the graph increments the value before returning to Synthesizer. After one rewrite, Sentinel must approve, block, or issue a conservative insufficient-evidence response. It cannot loop again.

## Structured Generative UI

The model never produces React, JSX, JavaScript, or HTML. It proposes data matching a versioned discriminated union. Initial allowed component types are:

- `text`
- `metric`
- `bar_chart`
- `line_chart`
- `pie_chart`
- `table`
- `citation_list`
- `video_evidence`

Python validates the union with Pydantic v2 before an API response is emitted. Shared JSON examples/schema guide a matching Zod discriminated union in TypeScript. The frontend maps each valid type to a hard-coded, tested component registry. Unknown versions or types fail closed to a safe text representation or normalized error.

Chart and table data should reference deterministic analytics outputs where numbers are involved. Labels, series counts, row counts, URLs, and text sizes are bounded. Content is rendered as text by default and never injected as raw HTML.

## Citation Grounding

Each evidence item receives a server-generated stable ID. The Synthesizer cites those IDs, and the server resolves display fields from trusted provenance rather than accepting filenames, pages, or timestamps authored by the model.

A final claim-to-evidence map associates answer spans or claim IDs with evidence IDs. Grounding validation ensures referenced evidence exists, belongs to the current authorized request, and supports the same modality/location presented to the user. If retrieval returns no suitable evidence, the response must state that limitation instead of fabricating a citation.

## Evaluation

Evaluation runs against versioned fixtures and records configuration, dataset version, provider mode, and latency. Mock mode provides deterministic CI coverage; curated Mistral runs may be executed separately when quota is available.

### Retrieval

- Recall@K against labeled relevant evidence
- Mean Reciprocal Rank (MRR)
- retrieval latency by dense, lexical, fusion, rerank, and total stages

### Routing

- route accuracy
- tool-selection accuracy
- invalid or unnecessary tool-call rate

### Generation

- groundedness proxy from claim/evidence mapping
- citation coverage
- answer relevance proxy
- abstention correctness on insufficient evidence

### Guardrails

- prompt-injection detection precision/recall on a labeled suite
- unsupported-claim detection rate
- false-positive rate
- rewrite and block rates
- schema and unsafe-output rejection rate

### System

- total, retrieval, generation, and guardrail latency
- provider call count
- estimated input/output token usage
- ingestion throughput and failures
- error rate by public error code

Evaluation results must distinguish deterministic metrics from model-judge scores. Judge provider/model/version and rubric version must be recorded. Model-judge output is a signal, not proof of correctness.

## AI Observability and Streaming

SSE events will communicate lifecycle updates such as run accepted, route selected, tool started/completed, evidence available, answer delta, Sentinel decision, metrics summary, completion, and normalized error. Events contain safe operational data only. They must not reveal system prompts, hidden reasoning, secrets, or raw provider traces.

Metrics link stages through correlation and run IDs. Provider calls record model identifier, duration, success/failure, retry count, and estimated token usage while respecting data-redaction rules.

## Provider Abstractions and Mock Mode

`LLMProvider` encapsulates structured generation and any necessary semantic judgment. The Mistral implementation reads credentials from environment variables. The mock implementation returns deterministic, fixture-driven responses and never needs network access.

The runtime setting is planned as:

```text
AI_PROVIDER=mistral|mock
```

Comparable abstractions isolate metadata, object storage, vector search, and embeddings. Provider-specific models and SDK types should not leak into graph state or public contracts.

