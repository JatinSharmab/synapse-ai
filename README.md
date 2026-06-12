# SYNAPSE — Enterprise AI Intelligence OS

Synapse is a portfolio-grade Enterprise AI Intelligence OS designed to demonstrate senior-level AI engineering. It will reason across PDF documents, video content, and CSV data while keeping answers grounded in traceable evidence.

> **Project status:** Phase 0 — architecture and engineering contracts only. No application services, endpoints, deployment, or infrastructure are implemented yet.

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

## Planned Monorepo

The target repository layout is documented here for orientation. Phase 0 creates only the files already present; the application directories below will be added in later, explicitly authorized phases.

```text
frontend/       React, TypeScript, Vite, Tailwind CSS, Recharts, SSE client
gateway/        Thin Node.js, TypeScript, Express API gateway
ai-service/     FastAPI, LangGraph, Mistral, ChromaDB, BM25, ingestion, evaluation
shared/         Cross-service contracts where appropriate
scripts/        Development and operational scripts
sample-data/    Safe demonstration data
docs/           Architecture, design, decisions, contracts, and build history
```

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

## Current Scope

Phase 0 intentionally contains documentation only. Setup commands, environment variables, and run instructions will be added when the corresponding services are implemented and verified.

