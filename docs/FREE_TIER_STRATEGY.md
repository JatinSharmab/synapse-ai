# Free-Tier Strategy

## Purpose

Synapse must be demonstrable for $0 while remaining honest about the operational limits of free services. This document explicitly separates the planned **Portfolio Demo Architecture** from a possible **Production Enterprise Architecture**. Nothing in the enterprise section is claimed to be implemented or deployed.

## Portfolio Demo Architecture

This is the target for the portfolio deployment, subject to provider availability and current free-tier terms at deployment time.

| Concern | Planned free-tier choice | Role | Known constraint |
|---|---|---|---|
| Web UI | Vercel Hobby | React/Vite static frontend | Hobby quotas and platform limits |
| API gateway | Separate Vercel project | Thin Express control/API and SSE proxy | Serverless duration, payload, and streaming constraints |
| AI service | Render Free Web Service | FastAPI, LangGraph, ingestion, retrieval, generation | Cold starts, sleep, limited CPU/RAM, ephemeral local disk |
| Metadata | MongoDB Atlas Free cluster | Durable metadata, provenance, chunks, embeddings/rebuild records | Storage, throughput, and connection limits |
| Object files | Supabase Storage Free | PDFs, videos, sampled frames, derived artifacts | Storage, bandwidth, and request quotas |
| LLM | Mistral free mode | Structured generation and selective semantic checks | Quota, rate limits, model availability |
| Offline fallback | In-process mock provider | Deterministic demos and automated tests | Not equivalent to live model quality |
| Vector search | ChromaDB in AI service | Dense index and retrieval | Ephemeral on Render; must be reconstructed |
| Lexical search | Local BM25 | Hybrid lexical retrieval | Memory/CPU constrained |
| Reranking | Lightweight local strategy | Improve ordering after RRF | Lower quality ceiling than large hosted rerankers |
| Observability | Structured logs and stored aggregate metrics | Safe traces, timings, usage estimates | Limited retention and analysis features |

### Data Durability on Ephemeral Compute

Render-local ChromaDB is a cache/index, not the durable source of truth. MongoDB must retain source metadata, provenance, cleaned chunk content, embedding vectors, embedding model/version, checksums, and collection/index version. Supabase retains original and approved derived objects.

At startup, the AI service will reconstruct missing Chroma collections from durable compatible embeddings. It must not spend Mistral quota recomputing embeddings that already exist and match the active embedding version. Index readiness is separate from process liveness so the system can report warm-up honestly.

### Upload Strategy

Production uploads follow this control flow:

```text
browser -> signed Supabase upload URL -> Supabase Storage
browser -> gateway metadata/control request -> AI service ingestion by object reference
```

The gateway does not proxy large PDF or video bodies through Vercel. Direct FastAPI multipart uploads may be offered only for local development, with explicit size limits.

### Staying Within Free Quotas

- Sample representative video scenes/keyframes rather than every frame.
- Make audio transcription optional and bounded.
- Cache versioned embeddings and rebuild local indexes from durable records.
- Limit upload size, pages, video duration, CSV rows/columns, query size, retrieval K, context size, output size, and provider calls.
- Use deterministic routing and guardrails before model calls where possible.
- Use BM25, RRF, and a lightweight local reranker rather than a paid reranking API.
- Default automated tests and a fallback demo path to `AI_PROVIDER=mock`.
- Surface quota/provider unavailability honestly instead of simulating a live provider result.

### Demo Limitations

This topology does not provide guaranteed uptime, autoscaling, durable local volumes, high ingestion concurrency, strong disaster recovery, enterprise identity, regional redundancy, contractual data residency, private networking, or an SLA. Cold starts and quota exhaustion are expected constraints. It is suitable for a portfolio demonstration and engineering evaluation, not enterprise production traffic.

## Production Enterprise Architecture

The following is a future design direction only. It is **not currently deployed, implemented, funded, or included in the free-tier commitment**.

A real enterprise deployment would choose components through security, compliance, scale, latency, residency, recovery, and cost review. It may require:

- highly available container or serverless compute with autoscaling and health-managed rollouts;
- durable managed vector storage or durable volumes with tested backup/restore;
- a durable job queue and separate workers for long-running ingestion;
- managed relational/document metadata storage with backups and point-in-time recovery;
- enterprise object storage with lifecycle policies, malware scanning, and regional controls;
- centralized secrets management and key rotation;
- SSO/RBAC, tenant isolation, audit logging, retention policies, and deletion workflows;
- private networking, WAF, egress controls, encryption-key governance, and vulnerability management;
- production monitoring, alerting, tracing, SLOs, load testing, and incident response;
- provider capacity agreements, fallback models, budget controls, and formal model-risk evaluation;
- multi-region recovery where justified by business requirements.

These capabilities may be paid and require the user's explicit approval before selection or implementation. No specific paid vendor is silently adopted by this architecture.

## Comparison

| Dimension | Portfolio Demo Architecture | Production Enterprise Architecture |
|---|---|---|
| Goal | Demonstrate AI engineering at $0 | Meet defined business SLOs and compliance needs |
| Availability | Best effort; cold starts expected | Designed and tested against explicit SLOs |
| Scale | Small curated demos, bounded ingestion | Capacity planned for measured workloads |
| Vector durability | Reconstruct ephemeral Chroma from durable records | Durable, backed-up, highly available vector layer |
| Background work | In-process/bounded execution where platform permits | Durable queue, workers, retries, dead-letter handling |
| Security | Baseline validation, secrets, signed URLs, least access | Enterprise IAM, audit, network controls, governance |
| Observability | Structured safe logs and core metrics | Centralized traces, alerts, SLOs, long retention |
| Recovery | Rebuild indexes; free-service limitations | Tested backup, restore, and disaster recovery |
| Cost | Designed for $0 within quotas | Costed and approved against requirements |
| Current status | Planned for later phases | Conceptual only; not deployed |

## Cost-Control Decision Gate

Before adding any paid infrastructure, the team must record an architecture decision describing the need, free alternatives considered, expected cost, operational impact, data implications, and rollback path. Implementation requires explicit user approval.

Prohibited without that approval include OpenAI API, Anthropic API, Pinecone, Weaviate Cloud, Redis Cloud, Kafka services, Kubernetes platforms, AWS paid services, paid LangSmith, paid reranking APIs, and paid vector databases.

## Verification Before Deployment

Free-tier offerings and limits can change. A deployment phase must verify current provider terms, regions, quotas, inactivity behavior, streaming compatibility, and data-retention terms before claiming the $0 topology works. Phase 0 makes no such deployment claim.

