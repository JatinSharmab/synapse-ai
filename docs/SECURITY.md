# Synapse Security Review

**Reviewed:** 2026-07-12

**Scope:** Phase 14 production-readiness hardening

Synapse applies layered controls at the browser, Express gateway, FastAPI service, provider,
retrieval, and rendering boundaries. This review does not claim that the system is perfectly secure.
It records the current mitigations and the risks that still require deployment controls or future
product work.

## Primary Trust Boundaries

1. The browser is untrusted. It may submit malformed JSON, hostile filenames, untrusted files, or
   forged model-facing instructions.
2. The Express gateway is a transport boundary. It validates small JSON controls, rate-limits,
   assigns request IDs, applies HTTP headers, and proxies SSE; it owns no AI logic.
3. FastAPI is the application boundary. It validates files and schemas, runs constrained tools,
   owns orchestration, and normalizes failures.
4. Retrieved documents, transcripts, model output, MongoDB records, Chroma records, and provider
   responses are untrusted data until validated against their relevant schema and provenance.
5. MongoDB Atlas, Supabase, Mistral, and the deployment network are external systems. Their
   availability and account-level authorization cannot be established by application code alone.

## HTTP and API Controls

| Threat | Mitigation | Remaining limitation |
| --- | --- | --- |
| Malformed or oversized JSON | Gateway Zod schemas are strict; FastAPI uses bounded Pydantic models; Express limits JSON bodies to 16 KiB. FastAPI validation errors return a generic envelope and do not echo rejected input. | FastAPI remains directly reachable in local deployments and must also be protected by the production network/edge. Multipart parsing still occurs before domain validation. |
| Cross-origin requests | Gateway and FastAPI use exact configured origin allowlists. Origins must be plain HTTP(S) origins without credentials or paths; production requires HTTPS. Credentials are not enabled. | CORS is a browser policy, not authentication. Non-browser clients can call a public endpoint directly. |
| Browser injection and framing | Helmet protects the gateway. FastAPI adds `nosniff`, frame denial, no-referrer, restrictive permissions, no-store, and production CSP/HSTS headers. API docs are disabled in production. | Headers reduce browser attack surface but do not replace output encoding or authentication. HSTS is effective only after a correctly terminated HTTPS response reaches the browser. |
| Request flooding and provider-cost abuse | A fixed-window gateway limiter covers every `/api/v1` route and returns standard limit metadata. | The limiter is in memory and process-local, is not tenant-aware, and does not protect a separately exposed FastAPI origin. A distributed edge limiter is required for multi-instance production use. |
| Slow or unavailable upstreams | Gateway JSON and SSE proxy calls use an abortable total timeout. Mistral, Supabase, MongoDB, and FFmpeg/ffprobe have bounded timeouts. | Some provider SDK work runs in a worker thread and may finish after a client disconnect. There are no per-stage latency budgets or circuit breakers. |
| Client or upstream SSE disconnect | Both proxy layers monitor disconnects, abort/cancel upstream work where possible, close generators, emit typed safe errors when headers permit, and clear timers/listeners. | SSE replay/resumption is not persisted. Infrastructure proxy buffering and platform-specific connection limits need deployment verification. |
| Internal exception or credential disclosure | Expected domain/provider failures use normalized typed envelopes. Unexpected FastAPI and gateway failures return generic messages. Structured logs contain IDs, method/path, status, duration, and error type—not bodies, prompts, retrieved text, or exception messages. | Central log retention, access policy, redaction validation, alerting, and trace export are not implemented. Application libraries may still emit their own logs and must be configured by the operator. |
| Forged correlation identifiers or log injection | Incoming IDs accept only a bounded ASCII allowlist; otherwise the services generate UUIDs. Query strings and bodies are omitted from access logs. | IDs are diagnostic, not identity or authorization claims. |

## File and Object-Storage Controls

| Threat | Mitigation | Remaining limitation |
| --- | --- | --- |
| Extension/MIME spoofing | PDF, MP4, and CSV handlers require allowlisted extensions and MIME types. PDF and MP4 also check magic/container signatures; PyMuPDF and ffprobe must successfully parse the object. | MIME and magic validation do not detect malware, parser exploits, decompression bombs, or all malformed media. There is no antivirus/content-disarm service. |
| Oversized uploads | Configured byte, page, duration, row, column, and keyframe limits are validated before expensive processing where possible. Supabase downloads are streamed with a hard byte ceiling. | A direct multipart request may consume edge/server parser resources before application checks. Production should enforce matching limits at the CDN/load balancer and Supabase bucket. |
| Filename injection and traversal | Display names are reduced to safe basenames. Signed-upload filenames and stored references reject separators, dot paths, control/format characters, surrounding whitespace, and overlong names. Server-generated object paths use an asset namespace plus a random identifier. Local storage resolves paths and requires them to remain under its root. | Unicode confusables are not canonicalized. Filenames remain display metadata and should never be used as authorization identifiers. |
| Object replacement or arbitrary storage reference | Upload intents are server-generated, expiring, one-time records. Ingestion verifies the stored object's exact size and asset namespace before consuming the intent. Supabase is configured as a private bucket and the service-role key remains server-side. | There is no authenticated tenant owner on upload intents. Signed URL revocation and cleanup of abandoned objects/intents are not automated. |
| Video subprocess command injection | FFmpeg/ffprobe receive argument arrays with `shell=False`; paths are validated, subprocesses have timeouts, and return codes are checked. Failed ingestion removes staged video artifacts and logs cleanup failures without revealing paths. | FFmpeg processes complex untrusted codecs and is not OS-sandboxed. Production should use a patched binary, restricted worker identity, CPU/memory limits, and an isolated job environment. |
| CSV formula or arbitrary-code execution | CSV values are parsed as data. Analytics uses discriminated Pydantic operations and deterministic application code; column existence, grouping, aggregation fields, sort direction, and row limits are checked. There is no `eval`, `exec`, Python shell, SQL, or model-authored code execution. | Exporting results to spreadsheet software could still trigger formula interpretation unless a future export layer escapes dangerous cell prefixes. Very wide individual cells have no dedicated byte limit beyond total upload size. |

## AI, Retrieval, and Rendering Controls

| Threat | Mitigation | Remaining limitation |
| --- | --- | --- |
| Direct prompt injection | Sentinel input guards detect common instruction override, dangerous tool, and system-prompt extraction patterns. Queries have a maximum length. Detected severe input is blocked before useful output. | Pattern matching is not complete and can be bypassed by novel, multilingual, encoded, or indirect attacks. Authentication and abuse monitoring are still needed. |
| Indirect prompt injection in retrieved content | Synthesis prompts explicitly treat retrieved content as untrusted evidence, never instructions. Retrieval metadata is kept separate from operational prompts, and no retrieved content can create executable tools. | A model may still follow a sophisticated indirect injection. The current semantic fallback is not a formal information-flow control system. |
| Infinite graph rewrite loop | Sentinel is deterministic by default, rewrite count is capped at one, conditional edges terminate on approve/block, and LangGraph has a recursion limit. Regression tests assert termination. | A future graph modification can invalidate these properties; loop tests must remain mandatory. |
| Fabricated or mismatched citations | Citation identifiers are built from actual retrieval results. Guards require citation existence, map document/page/chunk or video/timestamp references back to retrieved context, and calculate evidence coverage/relevance. | Unsupported-claim detection is heuristic. A citation can be structurally valid while the evidence is weak or semantically misinterpreted. |
| Arbitrary UI code, script, or HTML | Gen-UI is a strict versioned Pydantic/Zod union. The frontend uses a fixed component registry, validates payloads before rendering, rejects markup/script patterns and unknown keys/types, and falls back to text. No dynamic model-selected imports, raw HTML rendering, or `eval` exist. | Text still depends on React's escaping behavior. Protocol changes require coordinated Python/TypeScript updates and adversarial regression tests. |
| Secret-like model output | Sentinel output guards reject script/HTML and common secret patterns before completion. Streaming emits chunks only from the final guarded response. | Regex-based secret detection has false positives and false negatives; it cannot know every organization-specific secret format. Provider-side retention is governed by the provider account agreement. |
| Mistral timeout, transient error, or quota exhaustion | The provider passes an explicit request timeout, disables SDK retries, applies only bounded retries to network/5xx failures, and never retries HTTP 429 quota/rate-limit responses aggressively. Errors are sanitized and keys use `SecretStr`. | Live Mistral behavior was not tested during this review. Account quotas, regional outages, model changes, and billing controls remain external dependencies. |

## Persistence and Deployment Controls

| Threat | Mitigation | Remaining limitation |
| --- | --- | --- |
| Render cold start or restart | `/health` is a fast liveness check. Chroma reconciliation runs as startup background work and `/ready` reports `starting`, `rebuilding`, `ready`, or `failed` without indefinitely blocking health probes. | Free instances can have material cold-start latency. Clients need bounded backoff and must distinguish liveness from readiness. |
| MongoDB unavailable | Connection selection and timeouts are bounded. Production configuration requires MongoDB. Readiness fails safely when durable records cannot be loaded; API exceptions are normalized. | There is no circuit breaker, queue, or automatic multi-region failover. A failed startup reconstruction currently needs an operator intervention/restart to retry. |
| Supabase unavailable | Requests have bounded timeouts, storage errors are normalized, downloads are size-limited, signed URLs are accepted only from the configured Supabase host, and the bucket is required to be private. | The app does not provision or audit bucket privacy/CORS. There is no background retry queue or automatic orphan cleanup. |
| Ephemeral or incomplete Chroma index | MongoDB stores text, provenance, embeddings, model/version, checksum, and timestamps. Startup compares durable and active IDs and rebuilds missing/stale namespaces without another embedding call. Readiness stays unavailable until reconciliation succeeds. | Chroma remains a single-instance active index. Rebuild duration grows with corpus size, and no distributed reconstruction lock is implemented. |
| Credential committed to source control | Runtime secrets come only from environment variables and secret fields are never returned by system APIs. `.env` and `.env.*` are ignored while examples are allowed. Common key/certificate/credential filenames and the observed root `password.txt` are ignored. A tracked-file scan found no likely live credential pattern. | Pattern scans cannot prove absence of secrets. The existing local `password.txt` was not read or deleted; its owner must decide whether it should be securely removed. Use a CI secret scanner and rotate any credential ever committed. |

## Deployment Requirements

- Keep FastAPI private behind the gateway or add equivalent edge authentication and rate limiting.
- Add authentication, tenant ownership, and authorization before storing real enterprise data.
- Configure only HTTPS production origins and keep the Supabase service-role key server-side.
- Enforce upload and request limits at the external edge as well as in application code.
- Run FFmpeg in a restricted worker/container and keep system and parser dependencies patched.
- Alert on readiness failures, sustained 429/5xx rates, reconstruction failures, and storage timeouts.
- Run secret scanning and dependency scanning in CI; immediately rotate any exposed credential.
