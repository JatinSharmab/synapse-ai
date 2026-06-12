# Synapse Agent Instructions

These instructions apply to the entire repository. Every coding agent must read this file and the relevant documents in `docs/` before modifying the project.

## Product Boundary

Synapse is an Enterprise AI Intelligence OS portfolio project. Its primary engineering value belongs in the Python AI service: multimodal retrieval, constrained analytics, orchestration, grounding, guardrails, evaluation, and observability. Do not turn it into a generic CRUD dashboard.

## Mandatory Working Rules

1. Read `AGENTS.md` before modifying code.
2. Read the architecture documents relevant to the requested work.
3. Work only on the phase explicitly requested by the user.
4. Do not implement future phases without permission.
5. Do not introduce paid services or dependencies that require a paid hosted service.
6. Never expose or commit credentials. Keep `.env`, API keys, passwords, tokens, and service keys out of source control. Example environment files contain variable names and safe placeholders only.
7. Maintain strong typing across Python, TypeScript, API payloads, state, and configuration.
8. Add tests for meaningful backend and AI behavior when application code is introduced.
9. Never claim a test passed unless it was actually executed and passed.
10. Never hide, suppress, or silently ignore failures.
11. Update `docs/BUILD_LOG.md` after every completed phase.
12. Record architecture-changing decisions in `docs/DECISIONS.md`.
13. Never expose chain-of-thought. Expose only safe operational traces such as selected route, tool status, evidence identifiers, timings, retry count, and validation results.
14. Prefer AI-engineering depth over unnecessary frontend or gateway complexity.

## Architectural Guardrails

- Keep `gateway/` thin. It may validate, rate-limit, add correlation IDs, apply HTTP security, proxy requests, proxy SSE, and normalize transport errors. It must not contain prompts, agents, embeddings, retrieval, Mistral integration, or analytics logic.
- Keep AI logic in `ai-service/` behind typed provider and repository interfaces.
- Never allow an LLM to generate and execute arbitrary Python, SQL, shell commands, JavaScript, JSX, or HTML.
- Gen-UI output is data, not executable code. Validate it with Pydantic in Python and Zod in TypeScript, then render it through a fixed frontend registry.
- Numerical answers must come from deterministic, constrained analytical operations.
- Grounded document and video answers must use evidence returned by retrieval. Never invent filenames, page numbers, timestamps, or source identifiers.
- Sentinel may request at most one synthesis rewrite. Graphs must have explicit termination conditions and no uncontrolled loops.
- Support `AI_PROVIDER=mistral|mock`; tests must be able to run without network access.
- Large production uploads must use browser-to-object-storage signed URLs. Do not route large binaries through Vercel serverless functions.
- Preserve the free-tier deployment constraint unless the user explicitly approves a change.

## Required Task Handoff

End every Codex task with these exact headings:

- FILES CREATED
- FILES MODIFIED
- COMMANDS EXECUTED
- TESTS EXECUTED
- TEST RESULTS
- KNOWN LIMITATIONS
- MANUAL ACTIONS REQUIRED FROM ME

Use `None` where a section has no entries. Include failures and unverified assumptions.

