# Synapse Testing Guide

Synapse tests are designed to run offline with `AI_PROVIDER=mock` and local/fake repositories. Unit
and integration tests must not require Mistral, MongoDB Atlas, Supabase, or another paid service.

## Prerequisites

- Node.js 20.19+ and npm 10+
- Python 3.11+
- The AI service development dependencies installed in `ai-service/.venv`
- FFmpeg/ffprobe only for manual real-video checks; automated tests use controlled test doubles

## Required Verification Commands

From `frontend/`:

```powershell
npm run lint
npm run typecheck
npm test
npm run build
```

From `gateway/`:

```powershell
npm run lint
npm run typecheck
npm test
npm run build
```

From `ai-service/`:

```powershell
.\.venv\Scripts\python.exe -m ruff check --no-cache app tests
.\.venv\Scripts\python.exe -m mypy --cache-dir "$env:TEMP\synapse-mypy-cache" app
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider
.\.venv\Scripts\python.exe -m pip check
```

The explicit temporary mypy cache is useful in restricted Windows workspaces where the repository
cache directory is not writable. It does not change type-check behavior.

## Coverage Map

| Area | Automated evidence |
| --- | --- |
| HTTP validation and error safety | Gateway schema/error tests and `test_security_hardening.py` verify strict requests, safe 422/500 bodies, safe IDs, exact CORS, and hardening headers. |
| SSE | Gateway and FastAPI streaming tests cover typed event forwarding, timeouts, early upstream failure, downstream disconnect, cleanup, and absence of hidden reasoning. |
| Files | Document/video/dataset tests cover MIME, signatures, corrupt and masquerading files, limits, provenance, safe subprocess calls, filenames, and failed-artifact cleanup. |
| Retrieval and citations | Document/video tests cover provenance; hybrid retrieval tests cover vector/BM25/RRF/reranking; guardrail tests reject fabricated/mismatched citations and unsupported claims. |
| AI orchestration | Routing, provider, graph, streaming, and adversarial guardrail tests use MockProvider and assert bounded rewrite termination. The Mistral adapter test verifies timeout propagation and no retry on 429 without making a network call. |
| Deterministic analytics | Analytics tests cover every allowed operation plus missing columns, invalid aggregation/grouping, limits, non-finite values, and the absence of executable-code tools. |
| Gen-UI | Python Pydantic and frontend Zod/registry tests cover valid types, missing/unknown fields, bad chart keys, script/HTML attempts, and fail-closed text rendering. |
| Persistence/readiness | Fake/local/Mongo-mock tests cover signed-upload intents, bounded objects, exact ID reconciliation, rebuild from stored embeddings, quick liveness, and readiness failure. |
| Evaluation | Reproducibility tests cover strict aggregate summaries, dataset checksum/configuration identity, metrics, and hidden-data rejection. |

## Secret and Ignore Checks

Run secret searches so only filenames—not matching secret contents—are printed. Adjust patterns to
your organization's credential formats.

```powershell
rg -l --hidden -g '!**/.git/**' -g '!**/node_modules/**' -g '!**/.venv/**' -g '!**/dist/**' -e 'sk-[A-Za-z0-9_-]{20,}' -e 'sb_secret_[A-Za-z0-9_-]{16,}' -e 'BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY' .
git check-ignore -v .env ai-service/.env
git ls-files -- .env ai-service/.env
```

Expected behavior: real `.env` files are ignored, `.env.example` files may be tracked, and `git
ls-files` prints no real environment file. Test fixtures can contain deliberately fake secret-like
strings to prove output guards; review matches by filename without pasting their contents into logs.

## Reproducible Evaluation

From `ai-service/`:

```powershell
.\.venv\Scripts\python.exe -m app.evaluation.run
```

Mock mode is the default. A configured live provider requires explicit opt-in and is not part of the
offline test baseline. Latency measurements are observations and should not be asserted as identical
across machines.

## Manual Production Checks

Automated tests do not establish the security of a real deployment. Before exposing production:

1. Confirm the FastAPI origin is private or independently protected and that only intended HTTPS
   origins receive CORS response headers.
2. Exercise browser-to-Supabase signed upload against a private `synapse-assets` bucket and confirm
   an expired, reused, wrong-size, or cross-namespace object is rejected.
3. Restart an ephemeral instance with an empty Chroma directory; verify `/health` stays fast,
   `/ready` reports rebuilding, and stored vectors restore retrieval without provider calls.
4. Simulate MongoDB, Supabase, and Mistral outages/429s; confirm bounded failures, safe responses,
   readiness state, and alerts.
5. Disconnect an SSE client during retrieval and generation behind the actual CDN/proxy; verify
   buffers, timers, sockets, and worker utilization recover.
6. Run malware scanning, dependency vulnerability scanning, and an authenticated penetration test
   appropriate to the final hosting environment.

## Phase 14 Verified Baseline

On 2026-07-12 the local baseline passed:

- Frontend: lint, strict typecheck, 20 tests, and Vite production build.
- Gateway: lint, strict typecheck, 16 integration tests, and TypeScript production build.
- AI service: Ruff, mypy, 109 tests in Mock mode, and `pip check`.
- Root npm production-dependency audit in offline lockfile mode: zero reported vulnerabilities.

This baseline is not a substitute for live cloud integration, platform configuration review, or an
ongoing CI security program.

