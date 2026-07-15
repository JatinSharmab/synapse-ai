# $0 Portfolio Deployment

This guide deploys the Phase 15 topology without creating paid resources:

```text
Browser -> Vercel frontend -> Vercel gateway -> Render FastAPI
   |                                      |-> MongoDB Atlas metadata/vectors
   `-> signed upload -> Supabase Storage  `-> ephemeral Chroma active index
                                             -> Mistral API
```

Free plans, quotas, product names, and dashboard labels can change. Confirm each provider still
offers the expected free option before creating a resource. Never add billing information merely
to follow this guide. This is a portfolio topology, not a claim of enterprise production capacity.

## Deployment order

1. Fork or push the repository to a Git provider supported by Render and Vercel.
2. Create the two Vercel project records so their stable production domains are known, but do not
   deploy them yet. Set `frontend/` as one Root Directory and `gateway/` as the other.
3. Create MongoDB Atlas and Supabase resources.
4. deploy the Render AI service.
5. configure and deploy the Vercel gateway.
6. configure and deploy the Vercel frontend.
7. update exact origins if a generated domain differs, then redeploy affected services.

No deployment command or manifest in this repository provisions a paid resource.

Official provider references: [Atlas free cluster setup](https://www.mongodb.com/docs/atlas/tutorial/deploy-free-tier-cluster/),
[Supabase private buckets](https://supabase.com/docs/guides/storage/serving/downloads),
[Supabase signed uploads](https://supabase.com/docs/reference/javascript/file-buckets-uploadtosignedurl),
[Render Blueprints](https://render.com/docs/blueprint-spec),
[Render Docker services](https://render.com/docs/docker),
[Vercel monorepo projects](https://vercel.com/docs/monorepos),
[Vercel Express](https://vercel.com/kb/guide/ship-a-express-app-on-vercel), and
[Vercel Vite SPA deployment](https://vercel.com/docs/frameworks/frontend/vite).

## 1. MongoDB Atlas Free

1. In Atlas, create a project and an `M0` free cluster in a region near the Render service.
2. Under **Database Access**, create a dedicated application database user with a generated strong
   password. Grant only read/write access to the `synapse` database.
3. Under **Network Access**, allow the outbound IP ranges shown for the Render service. If the free
   topology cannot provide a narrow stable range, document that limitation before using a broader
   allowlist; never use a broad rule for sensitive data.
4. Open **Connect > Drivers**, select Python, and copy the SRV connection string into Render's
   secret environment editor. Replace its password placeholder there, never in a file.
5. Use `synapse` as the database name. Collections are created by the repository adapter when the
   application first writes metadata.

Atlas stores document chunks, video segments, provenance, checksums, and embedding vectors. Those
vectors are the durable source used to reconstruct disposable Chroma collections.

## 2. Supabase Storage Free

1. Create a Supabase project on the free plan.
2. Open **Storage > New bucket** and create exactly `synapse-assets`.
3. Keep **Public bucket** disabled. Optionally set a bucket file-size limit no lower than the
   application's configured PDF/video limits and restrict MIME types to `application/pdf` and
   `video/mp4`.
4. Copy the project URL and server-side service-role key into Render's secret environment editor.
   The service-role key must never be stored in Vercel frontend variables or any `VITE_*` variable.
5. Test from the deployed frontend. The browser receives a time-limited upload URL, sends the file
   directly to Supabase, and returns only the generated object path to the gateway.

The service role creates signed upload URLs and downloads private objects for ingestion. The client
does not need the service-role key. Keep the bucket private even though individual upload URLs are
temporarily usable by their holder.

## 3. Render Free Web Service

The root [`render.yaml`](../render.yaml) and [`ai-service/Dockerfile`](../ai-service/Dockerfile)
define a Docker deployment. The image installs FFmpeg, runs as a non-root user, and starts with the
equivalent of:

```sh
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

1. In Render, choose **New > Blueprint**, connect the repository, and select `render.yaml`.
2. Confirm the service plan is **Free**, runtime is Docker, and health-check path is `/health`.
3. Supply every `sync: false` variable when prompted. Do not paste secrets into the blueprint.
4. After deployment, open `https://<render-domain>/health`; it should return HTTP 200 quickly.
5. Open `https://<render-domain>/ready`. HTTP 503 with `rebuilding` is expected briefly. HTTP 200
   means both document and video indexes are usable. A `failed` namespace requires log inspection.

### AI service environment

| Variable | Required | Secret | Purpose |
| --- | --- | --- | --- |
| `APP_ENV` | Yes | No | Must be `production`. |
| `APP_VERSION` | Yes | No | Public deployment version. |
| `AI_CORS_ORIGINS` | Yes | No | JSON list of exact HTTPS browser origins. |
| `AI_PROVIDER` | Yes | No | `mistral` for hosted inference; `mock` for a no-network demo. |
| `MISTRAL_API_KEY` | For Mistral | Yes | Mistral credential used only by FastAPI. |
| `MISTRAL_CHAT_MODEL` | Yes | No | Chat model identifier. |
| `MISTRAL_VISION_MODEL` | Yes | No | Vision model identifier. |
| `MISTRAL_EMBED_MODEL` | Yes | No | Embedding model identifier and rebuild compatibility marker. |
| `AI_REQUEST_TIMEOUT_SECONDS` | No | No | Per-provider request timeout. |
| `AI_MAX_TRANSIENT_RETRIES` | No | No | Bounded transient retries; quota errors are not retried aggressively. |
| `METADATA_BACKEND` | Yes | No | Must be `mongo` in production. |
| `MONGODB_URI` | Yes | Yes | Atlas SRV connection string. |
| `MONGODB_DATABASE` | Yes | No | Durable metadata database. |
| `MONGODB_CONNECT_TIMEOUT_SECONDS` | No | No | Bounded initial Mongo connection timeout. |
| `OBJECT_STORAGE_PROVIDER` | Yes | No | Must be `supabase` in production. |
| `SUPABASE_URL` | Yes | No | HTTPS Supabase project URL. |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Yes | Server-only private Storage credential. |
| `SUPABASE_BUCKET` | Yes | No | Must name the private `synapse-assets` bucket. |
| `SUPABASE_REQUEST_TIMEOUT_SECONDS` | No | No | Bounded Storage request timeout. |
| `UPLOAD_INTENT_TTL_SECONDS` | No | No | Upload authorization lifetime, at most two hours. |
| `CHROMA_PERSIST_PATH` | No | No | Ephemeral active-index location; never treat it as durable. |
| `CHROMA_DOCUMENT_COLLECTION` | No | No | Document collection name. |
| `CHROMA_VIDEO_COLLECTION` | No | No | Video collection name. |
| `VECTOR_TOP_K` | No | No | Dense retrieval candidate count. |
| `BM25_TOP_K` | No | No | Lexical retrieval candidate count. |
| `RERANK_TOP_K` | No | No | Local reranking candidate count. |
| `FINAL_CONTEXT_K` | No | No | Final synthesis context count. |
| `DOCUMENT_MAX_UPLOAD_BYTES` | No | No | PDF upload ceiling. |
| `MAX_VIDEO_SIZE_MB` | No | No | MP4 upload ceiling. |
| `MAX_VIDEO_DURATION_SECONDS` | No | No | MP4 duration ceiling. |
| `MAX_KEYFRAMES` | No | No | Maximum representative frames. |
| `KEYFRAME_INTERVAL_SECONDS` | No | No | Sampling interval control. |
| `VIDEO_SUBPROCESS_TIMEOUT_SECONDS` | No | No | FFmpeg/ffprobe timeout. |
| `VIDEO_VISION_ENABLED` | No | No | Enables optional vision enrichment. |
| `VIDEO_TRANSCRIPTION_ENABLED` | No | No | Enables configured transcription. |
| `TRANSCRIPTION_PROVIDER` | No | No | `disabled` or `mock` in this release. |
| `SSE_STREAM_TIMEOUT_SECONDS` | No | No | AI stream time limit. |
| `SSE_HEARTBEAT_SECONDS` | No | No | SSE keepalive interval. |
| `DEBUG` | Yes | No | Keep `false`; debug retrieval routes must remain absent. |

Render supplies `PORT`; do not create or hard-code it. The `.python-version` declares Python 3.11
for non-Docker tooling, while the Docker base image pins the hosted runtime family.

## 4. Vercel gateway project

1. Import the same repository into Vercel as a new project.
2. Set **Root Directory** to `gateway` and leave automatic framework detection enabled. The checked-in
   `vercel.json` declares Express, and `src/index.ts` default-exports the application.
3. Set the Production environment variables below, then deploy.
4. Confirm `https://<gateway-domain>/health` returns HTTP 200.
5. Confirm `https://<gateway-domain>/ready` eventually proxies an HTTP 200 readiness result.

| Variable | Required | Secret | Purpose |
| --- | --- | --- | --- |
| `AI_SERVICE_URL` | Yes | No | Exact HTTPS Render origin, without a path. |
| `FRONTEND_ORIGIN` | Yes | No | Exact HTTPS Vercel frontend origin. |
| `NODE_ENV` | Yes | No | Must be `production`. |
| `APP_VERSION` | Yes | No | Gateway health version. |
| `GATEWAY_UPSTREAM_TIMEOUT_MS` | No | No | Total upstream/SSE timeout; keep above AI stream timeout. |
| `GATEWAY_RATE_LIMIT_WINDOW_MS` | No | No | In-memory fixed-window length. |
| `GATEWAY_RATE_LIMIT_MAX` | No | No | Requests allowed per function instance/window. |

The gateway validates chat/upload control JSON, assigns request and correlation IDs, applies CORS,
security headers and lightweight rate limits, proxies typed SSE, and normalizes errors. Its route
allowlist has no generic raw PDF/video upload endpoint.

## 5. Vercel frontend project

1. Import the repository again as a separate Vercel project.
2. Set **Root Directory** to `frontend`. The checked-in `vercel.json` selects Vite and rewrites SPA
   navigation to `index.html`.
3. Add the production variable below and deploy.
4. If the production domain changes, update `FRONTEND_ORIGIN` on the gateway and
   `AI_CORS_ORIGINS` on Render, then redeploy both.

| Variable | Required | Secret | Purpose |
| --- | --- | --- | --- |
| `VITE_GATEWAY_URL` | Yes | No | Exact HTTPS gateway origin, without a path. |

Do not create frontend variables for Mistral, MongoDB, Supabase service-role credentials, or the
direct Render URL. Vite embeds `VITE_*` values in public JavaScript. Environment-variable changes
take effect only after a new frontend deployment.

## Production verification

Run these checks after all services are deployed:

1. Load the frontend in a private browser window. During a Render cold start, the status panel must
   show **Waking Synapse AI service...**, use the bounded readiness schedule, and eventually report
   **Systems ready**.
2. In browser developer tools, verify frontend API calls target the gateway domain. The only
   cross-origin binary request should target a signed Supabase URL.
3. Send a direct question and confirm ordered SSE activity reaches `response.completed` without
   exposing prompts or hidden reasoning.
4. Upload the sample PDF. Verify the network sequence is presign JSON -> Supabase upload -> stored
   object-reference JSON. Search for its known page content and inspect real citation provenance.
5. Restart the Render service. `/health` should stay independent of reconstruction, `/ready` should
   transition through rebuilding if necessary, and the same document should remain retrievable
   after Chroma is rebuilt from Atlas vectors without new embedding calls.
6. Upload a small MP4 within configured limits and confirm timestamped evidence retrieval. Vision
   enrichment may remain partial if disabled or quota-limited.
7. Confirm production direct multipart PDF/video routes return 403 and the gateway has no raw
   binary upload route. CSV upload remains a local-development capability in this release.

## Troubleshooting

### Render cold start

Open the Render `/health` URL once, then watch `/ready`. The frontend intentionally retries only a
bounded number of times with increasing delays. If health never answers, inspect Render deploy and
runtime logs. If health answers but readiness does not, inspect the reconstruction status and Mongo
connectivity rather than repeatedly refreshing the browser.

### Mistral HTTP 429

The provider surfaces a safe quota/rate-limit error and avoids aggressive quota retries. Wait for
the provider window to reset, verify the selected model is available to the account, or temporarily
set `AI_PROVIDER=mock` and redeploy for a deterministic portfolio demonstration. Never add the key
to frontend or gateway logs.

### MongoDB connection failure

Verify the Atlas cluster is active, database user is enabled, password is URL-encoded in the SRV
URI, database name matches, and Render outbound addresses are allowed. `/health` can remain 200
while `/ready` reports failure because liveness deliberately does not depend on Mongo.

### Supabase access failure

Verify the project URL, service-role key, exact private bucket name, file-size/MIME restrictions,
and that the signed URL has not expired. A browser upload failure occurs before ingestion; a server
download failure occurs after the object-reference request. Rotate a key immediately if it was
ever exposed to a browser, log, commit, or screenshot.

### SSE problem

Use `curl -N` against the gateway stream endpoint and check `Content-Type: text/event-stream`.
Compare gateway and AI timeouts, confirm Vercel and Render deployments are healthy, and use the
returned request/correlation IDs to align logs. Browser extensions and corporate proxies may buffer
streams; test in a private window and on another network before changing the protocol.

### CORS problem

Origins must match exactly, including scheme and hostname, with no path or trailing mismatch.
Set the frontend production origin in gateway `FRONTEND_ORIGIN`, then redeploy the gateway. Also
keep the same exact HTTPS origin in Render `AI_CORS_ORIGINS`. Preview deployments use different
origins and are intentionally not wildcarded; promote a stable production domain for testing.

### Chroma rebuild

Read `/ready` and identify whether documents or videos failed. Confirm Atlas contains durable
chunk/segment records with vectors and matching embedding metadata. Render disk content is
disposable; deleting or restarting a service may force reconciliation. Do not solve this by calling
the embedding API again—the startup service rebuilds from stored vectors.

### Frontend environment changes

Changing `VITE_GATEWAY_URL` in Vercel does not alter an already-built bundle. Trigger a new
production deployment, clear any stale service-worker/browser cache, and verify the compiled app's
network requests use the new origin.

## Remaining limitations

- Free compute sleeps, quotas, build minutes, storage, bandwidth, and database capacity are limited.
- The gateway rate limiter is per serverless instance and is not a distributed abuse-control layer.
- Authentication and tenancy are not implemented; do not upload private or regulated data.
- Chroma startup time grows with the durable corpus; `/ready` is the availability boundary.
- CSV production upload is not routed through Vercel and remains local-only.
- Monitoring, alerts, backups, disaster recovery, custom domains, and live provider failure drills
  remain operator responsibilities.
