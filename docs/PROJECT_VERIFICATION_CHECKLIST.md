# Synapse Final Project Verification Checklist

Use this checklist before recording a demo, sharing the repository, or preparing the optional free-tier deployment. Do not treat unchecked cloud items as complete merely because local mock mode works.

## Repository and local setup

- [ ] Node.js is `>=20.19`, npm is `>=10`, and Python is `>=3.11`.
- [ ] FFmpeg and ffprobe are available on `PATH` before testing video ingestion.
- [ ] Dependencies are installed with `npm install` and `pip install -e ".[dev]"` in `ai-service`.
- [ ] `ai-service/.env` is based on `.env.example` and uses `AI_PROVIDER=mock` for an offline demo.
- [ ] No `.env` file, token, private key, service-role credential, or real connection string is staged for Git.

## Final automated verification

- [ ] `npm run lint` passes.
- [ ] `npm run typecheck` passes.
- [ ] `npm run test` passes.
- [ ] `npm run build` passes.
- [ ] `python -m ruff check --no-cache app tests` passes from `ai-service`.
- [ ] `python -m mypy app` passes from `ai-service`.
- [ ] `python -m pytest -p no:cacheprovider` passes from `ai-service`.
- [ ] `python -m pip check` reports no broken requirements.
- [ ] `python -m app.evaluation.run` completes in mock mode.

## Local service readiness

- [ ] FastAPI starts with `uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`.
- [ ] `GET http://localhost:8000/health` responds quickly.
- [ ] `GET http://localhost:8000/ready` accurately reports retrieval readiness/rebuild state.
- [ ] Express starts with `npm run dev:gateway` and `GET http://localhost:4000/health` succeeds.
- [ ] Vite starts with `npm run dev:frontend` and the workspace loads.
- [ ] The frontend system indicator accurately distinguishes reachable, warming, and unavailable services.

## Demo behavior

- [ ] A direct question returns a safe response and operational activity, with no hidden reasoning.
- [ ] A text-based PDF can be ingested and a known answer shows exact filename/page/chunk provenance.
- [ ] An image-only or near-empty PDF reports `ocr_required`; OCR is not unexpectedly invoked.
- [ ] A small MP4 processes within configured limits and video search returns start/end timestamp evidence.
- [ ] Opening video evidence seeks the player to the returned `start_seconds`.
- [ ] A supported CSV question performs a deterministic typed operation and validates requested columns.
- [ ] An unsupported CSV operation or missing column returns a controlled validation error.
- [ ] A valid Gen-UI chart/table renders; malformed or unknown Gen-UI falls back safely.
- [ ] An obvious prompt-injection request, fabricated citation, script attempt, and secret-like output are blocked or rewritten according to Sentinel behavior.
- [ ] SSE displays route/tool/guardrail lifecycle events and cleans up after a client disconnect.

## Evaluation and evidence

- [ ] The evaluation dataset remains version controlled and contains known relevant document/chunk/page references.
- [ ] Evaluation reports Recall@K, MRR, latency, route/tool metrics, generation proxies, guardrail metrics, and system metrics.
- [ ] The recent evaluation summary API/UI contains aggregates only, not prompts, chain-of-thought, or hidden traces.

## Optional deployment checks

- [ ] Vercel frontend has only `VITE_GATEWAY_URL`; it has no Mistral, MongoDB, or Supabase service-role secret.
- [ ] Gateway has `AI_SERVICE_URL`, `FRONTEND_ORIGIN`, and production `NODE_ENV` configured.
- [ ] Render uses `uvicorn app.main:app --host 0.0.0.0 --port $PORT` and does not assume a fixed port.
- [ ] MongoDB Atlas and Supabase values are configured only in server-side Render/gateway environments.
- [ ] Supabase bucket `synapse-assets` is private; browser uploads use signed URLs and the frontend never receives the service-role key.
- [ ] CORS permits only the deployed frontend origin.
- [ ] A cold start shows the frontend warming state without aggressive readiness polling.
- [ ] A restart rebuilds Chroma from durable stored vectors when Mongo persistence is configured.
- [ ] Mistral quota exhaustion, Mongo unavailability, Supabase failures, CORS errors, and SSE upstream errors are tested as visible, normalized failure modes.

## Final handoff

- [ ] README, deployment, security, testing, architecture, API contracts, and interview guide are current.
- [ ] `docs/BUILD_LOG.md` records the final verification commands and actual results.
- [ ] Known free-tier and security limitations are stated honestly in the README and SECURITY documentation.
